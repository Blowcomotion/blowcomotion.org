import logging
from datetime import timedelta

from django_ratelimit.decorators import ratelimit

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import get_user_model, login, views as auth_views
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import PasswordResetForm, SetPasswordForm
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.utils.decorators import method_decorator

from blowcomotion.member_auth import (
    create_member_user,
    ensure_set_password_flow,
    needs_set_password,
    send_email_change_confirmation,
    send_set_password_email,
    send_signup_invite_email,
)
from blowcomotion.member_forms import (
    ALLERGEN_CHOICES,
    DIETARY_CHOICES,
    SHIRT_SIZE_CHOICES,
    GetAccessForm,
    MemberProfileForm,
    _yesno_to_bool,
)
from blowcomotion.models import (
    CustomImage,
    EmailChangeToken,
    Member,
    MemberInstrument,
    PasswordSetToken,
)
from blowcomotion.views import _validate_recaptcha

logger = logging.getLogger(__name__)
User = get_user_model()

TOKEN_EXPIRY_HOURS = 24


# ── Login ──────────────────────────────────────────────────────────────────────

class MemberLoginView(auth_views.LoginView):
    template_name = "member/login.html"

    def post(self, request, *args, **kwargs):
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

@method_decorator(
    ratelimit(key="ip", rate="10/h", method="POST", block=True),
    name="dispatch",
)
class MemberPasswordResetView(auth_views.PasswordResetView):
    template_name = "member/password_reset.html"
    email_template_name = "member/password_reset_email.txt"

    def post(self, request, *args, **kwargs):
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
        except (Member.DoesNotExist, Member.MultipleObjectsReturned):
            logger.debug(f"Password reset attempted for non-member or ambiguous email: {email}")
            return redirect("password_reset_done")

        if needs_set_password(member):
            ensure_set_password_flow(member, f"{self.request.scheme}://{self.request.get_host()}")
            logger.info(f"Sent set-password email (via reset flow) for member {member.pk}")
            return redirect("password_reset_done")

        self.from_email = settings.FROM_EMAIL
        return super().form_valid(form)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["include_form_js"] = True
        return ctx


# ── Get Access ─────────────────────────────────────────────────────────────────

@ratelimit(key="ip", rate="10/h", method="POST", block=True)
def get_access_view(request):
    if request.method == "POST":
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
                if needs_set_password(member):
                    ensure_set_password_flow(member, f"{request.scheme}://{request.get_host()}")
                    logger.info(f"Get-access: sent set-password email to member {member.pk}")
                else:
                    reset_form = PasswordResetForm({"email": email})
                    if reset_form.is_valid():
                        reset_form.save(
                            request=request,
                            use_https=request.is_secure(),
                            from_email=settings.FROM_EMAIL,
                            email_template_name="member/password_reset_email.txt",
                        )
                    logger.info(f"Get-access: sent reset email to member {member.pk}")
            except Member.DoesNotExist:
                send_signup_invite_email(email, f"{request.scheme}://{request.get_host()}")
            except Member.MultipleObjectsReturned:
                logger.warning(f"Get-access: ambiguous email match for {email}, no email sent")
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


# ── Member Portal ──────────────────────────────────────────────────────────────

@login_required
def member_home(request):
    return redirect("member-profile")


@login_required
def profile_view(request):
    if not hasattr(request.user, "member"):
        return redirect("/")
    member = request.user.member
    original_email = member.email  # snapshot before form validation mutates member in place

    def _profile_context(form):
        return {
            "form": form,
            "member": member,
            "include_form_js": True,
            "shirt_size_choices": SHIRT_SIZE_CHOICES,
            "dietary_choices": DIETARY_CHOICES,
            "allergen_choices": ALLERGEN_CHOICES,
        }

    if request.method == "POST":
        is_valid_captcha, captcha_error = _validate_recaptcha(request)
        if not is_valid_captcha:
            form = MemberProfileForm(request.POST, request.FILES, instance=member)
            ctx = _profile_context(form)
            ctx["recaptcha_error"] = captcha_error
            return render(request, "member/profile.html", ctx)
        form = MemberProfileForm(request.POST, request.FILES, instance=member)
        if form.is_valid():
            instance = form.save(commit=False)
            new_email = form.cleaned_data.get("email") or ""
            email_changed = new_email and new_email != original_email

            if email_changed:
                instance.email = original_email  # hold until confirmed

            photo = form.cleaned_data.get("profile_photo")
            old_image = instance.image if photo else None
            if photo:
                img = CustomImage(
                    title=f"{instance.first_name} {instance.last_name} profile photo",
                    file=photo,
                )
                img.save()
                instance.image = img

            # Save health & preferences fields manually (JSON/nullable-bool don't
            # round-trip cleanly through ModelForm; mirrors the signup handler)
            instance.shirt_size = request.POST.get("shirt_size") or ""
            instance.dietary_preferences = request.POST.getlist("dietary_preferences")
            instance.dietary_other = request.POST.get("dietary_other") or ""
            instance.has_allergies = _yesno_to_bool(request.POST.get("has_allergies"))
            instance.allergens = request.POST.getlist("allergens")
            instance.allergens_other = request.POST.get("allergens_other") or ""
            instance.has_epipen = _yesno_to_bool(request.POST.get("has_epipen"))
            instance.allergy_details = request.POST.get("allergy_details") or ""
            instance.medical_notes = request.POST.get("medical_notes") or ""

            instance.save(sync_go3=False)

            if old_image:
                old_image.delete()

            # Rebuild additional instruments
            member.additional_instruments.all().delete()
            for instrument in form.cleaned_data.get("additional_instruments", []):
                MemberInstrument.objects.create(member=member, instrument=instrument)

            instance.save_revision(user=request.user, log_action="wagtail.edit", clean=False)

            if email_changed:
                send_email_change_confirmation(member, new_email, f"{request.scheme}://{request.get_host()}")
                messages.success(
                    request,
                    f"Profile saved. A confirmation email has been sent to {new_email}.",
                )
            else:
                messages.success(request, "Profile saved.")
            return redirect("member-profile")
        return render(request, "member/profile.html", _profile_context(form))

    form = MemberProfileForm(instance=member)
    return render(request, "member/profile.html", _profile_context(form))


@login_required
def requests_view(request):
    if not hasattr(request.user, "member"):
        return redirect("/")
    return render(request, "member/requests.html", {"member": request.user.member})


def confirm_email_view(request, token_uuid):
    try:
        token = EmailChangeToken.objects.get(uuid=token_uuid)
    except EmailChangeToken.DoesNotExist:
        return render(request, "member/confirm_email_result.html", {"invalid": True})

    if token.used:
        return render(request, "member/confirm_email_result.html", {"invalid": True})

    expiry = token.created_at + timedelta(hours=TOKEN_EXPIRY_HOURS)
    if timezone.now() > expiry:
        return render(request, "member/confirm_email_result.html", {"expired": True})

    member = token.member
    new_email = token.new_email

    with transaction.atomic():
        member.email = new_email
        member.pending_email = None
        member.save(update_fields=["email", "pending_email"], sync_go3=False)
        token.used = True
        token.save(update_fields=["used"])
    # Member.save() email drift guard syncs User.email / User.username when "email" is in update_fields

    logger.info(f"Email confirmed for member {member.pk}: {new_email}")
    return render(request, "member/confirm_email_result.html", {"confirmed": True, "new_email": new_email})
