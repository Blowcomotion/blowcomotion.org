import logging
from datetime import timedelta

from django_ratelimit.decorators import ratelimit

from django.contrib.auth import login, views as auth_views
from django.contrib.auth.forms import PasswordResetForm, SetPasswordForm
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from blowcomotion.member_auth import create_member_user, send_set_password_email
from blowcomotion.member_forms import GetAccessForm
from blowcomotion.models import Member, PasswordSetToken
from blowcomotion.views import _validate_honeypot, _validate_recaptcha

logger = logging.getLogger(__name__)

TOKEN_EXPIRY_HOURS = 24


# ── Login ──────────────────────────────────────────────────────────────────────

class MemberLoginView(auth_views.LoginView):
    template_name = "member/login.html"

    def post(self, request, *args, **kwargs):
        if not _validate_honeypot(request):
            return redirect("/")
        is_valid, error = _validate_recaptcha(request)
        if not is_valid:
            form = self.get_form_class()()
            return render(request, self.template_name, {
                "form": form,
                "recaptcha_error": error,
                "include_form_js": True,
            })
        return super().post(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["include_form_js"] = True
        return ctx


# ── Set Password ───────────────────────────────────────────────────────────────

@ratelimit(key="ip", rate="10/h", method="POST", block=True)
def set_password_view(request, token_uuid):
    token = get_object_or_404(
        PasswordSetToken, uuid=token_uuid, used=False, superseded=False
    )
    expiry = token.created_at + timedelta(hours=TOKEN_EXPIRY_HOURS)
    if timezone.now() > expiry:
        return render(request, "member/set_password.html", {"expired": True})

    if request.method == "POST":
        if not _validate_honeypot(request):
            return redirect("/")
        is_valid, error = _validate_recaptcha(request)
        if not is_valid:
            form = SetPasswordForm(user=token.member.user)
            return render(request, "member/set_password.html", {
                "form": form, "token": token,
                "recaptcha_error": error, "include_form_js": True,
            })
        form = SetPasswordForm(user=token.member.user, data=request.POST)
        if form.is_valid():
            form.save()
            token.used = True
            token.save(update_fields=["used"])
            member = token.member
            if not member.is_active:
                member.is_active = True
                member.save(update_fields=["is_active"], sync_go3=False)
                logger.info(f"Reactivated member {member.pk} via set-password flow")
            login(request, member.user, backend="django.contrib.auth.backends.ModelBackend")
            logger.info(f"Member {member.pk} set password and logged in")
            return redirect("/member/profile/")
        return render(request, "member/set_password.html", {
            "form": form, "token": token, "include_form_js": True,
        })

    form = SetPasswordForm(user=token.member.user)
    return render(request, "member/set_password.html", {
        "form": form, "token": token, "include_form_js": True,
    })


# ── Password Reset ─────────────────────────────────────────────────────────────

class MemberPasswordResetView(auth_views.PasswordResetView):
    template_name = "member/password_reset.html"
    email_template_name = "registration/password_reset_email.html"  # Django default

    def post(self, request, *args, **kwargs):
        if not _validate_honeypot(request):
            return redirect("/")
        is_valid, error = _validate_recaptcha(request)
        if not is_valid:
            form = self.get_form_class()()
            return render(request, self.template_name, {
                "form": form, "recaptcha_error": error, "include_form_js": True,
            })
        return super().post(request, *args, **kwargs)

    def form_valid(self, form):
        email = form.cleaned_data["email"]
        try:
            member = Member.objects.get(email__iexact=email, is_active=True)
        except Member.DoesNotExist:
            # No active member — generic response, no email sent
            logger.debug(f"Password reset attempted for non-member email: {email}")
            return redirect("password_reset_done")

        if not member.user_id or not member.user.has_usable_password():
            # Member has no account or unusable password → send set-password email
            if not member.user_id:
                create_member_user(member)
            send_set_password_email(member, self.request)
            logger.info(f"Sent set-password email (via reset flow) for member {member.pk}")
            return redirect("password_reset_done")

        # Member has a usable-password User → use Django's built-in reset
        return super().form_valid(form)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["include_form_js"] = True
        return ctx


# ── Get Access ─────────────────────────────────────────────────────────────────

@ratelimit(key="ip", rate="10/h", method="POST", block=True)
def get_access_view(request):
    if request.method == "POST":
        if not _validate_honeypot(request):
            return redirect("/")
        is_valid, error = _validate_recaptcha(request)
        if not is_valid:
            form = GetAccessForm(request.POST)
            return render(request, "member/get_access.html", {
                "form": form, "recaptcha_error": error, "include_form_js": True,
            })
        form = GetAccessForm(request.POST)
        if form.is_valid():
            email = form.cleaned_data["email"]
            try:
                member = Member.objects.get(email__iexact=email)
                if not member.user_id or not member.user.has_usable_password() or not member.is_active:
                    # Inactive members always go through set-password so reactivation happens there
                    if not member.user_id:
                        create_member_user(member)
                    send_set_password_email(member, request)
                    logger.info(f"Get-access: sent set-password email to member {member.pk}")
                else:
                    # Active member with usable password → send standard reset email
                    reset_form = PasswordResetForm({"email": email})
                    if reset_form.is_valid():
                        reset_form.save(request=request, use_https=request.is_secure())
                    logger.info(f"Get-access: sent reset email to member {member.pk}")
            except Member.DoesNotExist:
                pass  # Generic response — no enumeration
            return render(request, "member/get_access.html", {
                "form": form, "sent": True,
            })
        return render(request, "member/get_access.html", {
            "form": form, "include_form_js": True,
        })

    form = GetAccessForm()
    return render(request, "member/get_access.html", {
        "form": form, "include_form_js": True,
    })


from datetime import timedelta

from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.utils import timezone

from blowcomotion.member_auth import send_email_change_confirmation
from blowcomotion.models import EmailChangeToken, MemberInstrument

User = get_user_model()


@login_required
def member_home(request):
    return redirect("member-profile")


@login_required
def profile_view(request):
    from blowcomotion.member_forms import MemberProfileForm
    member = request.user.member
    original_email = member.email  # snapshot before form validation mutates member in place

    if request.method == "POST":
        form = MemberProfileForm(request.POST, request.FILES, instance=member)
        if form.is_valid():
            instance = form.save(commit=False)
            new_email = form.cleaned_data.get("email") or ""
            email_changed = new_email and new_email != original_email

            if email_changed:
                instance.email = original_email  # hold until confirmed
            instance.save(sync_go3=False)

            # Rebuild additional instruments
            member.additional_instruments.all().delete()
            for instrument in form.cleaned_data.get("additional_instruments", []):
                MemberInstrument.objects.create(member=member, instrument=instrument)

            if email_changed:
                send_email_change_confirmation(member, new_email, request)
                messages.success(
                    request,
                    f"Profile saved. A confirmation email has been sent to {new_email}.",
                )
            else:
                messages.success(request, "Profile saved.")
            return redirect("member-profile")
        return render(request, "member/profile.html", {
            "form": form, "member": member, "include_form_js": True,
        })

    form = MemberProfileForm(instance=member)
    return render(request, "member/profile.html", {
        "form": form, "member": member, "include_form_js": True,
    })


@login_required
def requests_view(request):
    return render(request, "member/requests.html", {"member": request.user.member})


def confirm_email_view(request, token_uuid):
    from blowcomotion.models import EmailChangeToken
    try:
        token = EmailChangeToken.objects.get(uuid=token_uuid)
    except EmailChangeToken.DoesNotExist:
        return render(request, "member/confirm_email_result.html", {"invalid": True})

    if token.used:
        return render(request, "member/confirm_email_result.html", {"invalid": True})

    expiry = token.created_at + timedelta(hours=24)
    if timezone.now() > expiry:
        return render(request, "member/confirm_email_result.html", {"expired": True})

    member = token.member
    new_email = token.new_email

    member.email = new_email
    member.pending_email = None
    member.save(update_fields=["email", "pending_email"], sync_go3=False)

    token.used = True
    token.save(update_fields=["used"])

    if member.user_id:
        try:
            user = User.objects.get(pk=member.user_id)
            user.email = new_email
            user.username = new_email
            user.save(update_fields=["email", "username"])
        except User.DoesNotExist:
            pass

    logger.info(f"Email confirmed for member {member.pk}: {new_email}")
    return render(request, "member/confirm_email_result.html", {"confirmed": True, "new_email": new_email})
