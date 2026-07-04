import logging
from datetime import date, timedelta

from django_ratelimit.decorators import ratelimit

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import get_user_model, login, views as auth_views
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import PasswordResetForm, SetPasswordForm
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Count
from django.shortcuts import get_object_or_404, redirect, render
from django.template.loader import render_to_string
from django.utils import timezone
from django.utils.decorators import method_decorator
from django.views.decorators.http import require_GET

from blowcomotion.member_auth import (
    _MemberEmail,
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
    InstrumentRentalRequestForm,
    MemberProfileForm,
    _yesno_to_bool,
)
from blowcomotion.models import (
    CustomImage,
    EmailChangeToken,
    InstrumentRentalRequestSubmission,
    LibraryInstrument,
    Member,
    MemberInstrument,
    PasswordSetToken,
    SiteSettings,
)
from blowcomotion.views import _validate_recaptcha
from instruments.patreon import check_patreon_membership

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
            "attendance_total": member.attendance_records.count(),
            "attendance_this_year": member.attendance_records.filter(
                date__year=date.today().year
            ).count(),
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
    member = request.user.member
    rental_requests = member.rental_requests.select_related("instrument")
    return render(request, "member/requests.html", {"member": member, "rental_requests": rental_requests})


ATTENDANCE_RATE_WEEKS = 12
ATTENDANCE_PAGE_SIZE = 50


def _count_tuesdays(start_date, end_date):
    """Count practice Tuesdays between two dates, inclusive."""
    count = 0
    current = start_date
    while current <= end_date:
        if current.weekday() == 1:  # Tuesday
            count += 1
        current += timedelta(days=1)
    return count


def _attendance_streaks(record_dates, today):
    """
    Compute (current_streak, longest_streak) in weeks. A week counts toward a
    streak if it has at least one attendance record; the current streak may
    anchor on this week or last week, since this week's practice may not have
    happened yet.
    """
    if not record_dates:
        return 0, 0

    def week_index(d):
        iso = d.isocalendar()
        # Ordinal of the ISO week's Monday // 7 gives a consecutive week number
        return date.fromisocalendar(iso[0], iso[1], 1).toordinal() // 7

    weeks = sorted({week_index(d) for d in record_dates})
    week_set = set(weeks)

    longest = run = 1
    for prev, cur in zip(weeks, weeks[1:]):
        run = run + 1 if cur == prev + 1 else 1
        longest = max(longest, run)

    this_week = week_index(today)
    if this_week in week_set:
        anchor = this_week
    elif this_week - 1 in week_set:
        anchor = this_week - 1
    else:
        return 0, longest

    current = 0
    while anchor in week_set:
        current += 1
        anchor -= 1
    return current, longest


@login_required
@require_GET
def attendance_view(request):
    if not hasattr(request.user, "member"):
        return redirect("/")
    member = request.user.member
    records = member.attendance_records.select_related("played_instrument").order_by("-date")

    today = date.today()
    stats = None
    record_dates = list(records.values_list("date", flat=True))
    if record_dates:
        window_start = today - timedelta(weeks=ATTENDANCE_RATE_WEEKS)
        window_count = sum(1 for d in record_dates if d >= window_start)
        effective_start = (
            max(window_start, member.join_date) if member.join_date else window_start
        )
        window_tuesdays = _count_tuesdays(effective_start, today)
        rate = (
            min(100, round(window_count / window_tuesdays * 100))
            if window_tuesdays
            else None
        )

        current_streak, longest_streak = _attendance_streaks(record_dates, today)

        stats = {
            "total": len(record_dates),
            "this_year": sum(1 for d in record_dates if d.year == today.year),
            "first_date": record_dates[-1],
            "last_date": record_dates[0],
            "window_count": window_count,
            "window_tuesdays": window_tuesdays,
            "window_weeks": ATTENDANCE_RATE_WEEKS,
            "rate": rate,
            "current_streak": current_streak,
            "longest_streak": longest_streak,
            "by_year": records.values("date__year")
            .annotate(count=Count("id"))
            .order_by("-date__year"),
            "instruments": records.filter(played_instrument__isnull=False)
            .values("played_instrument__name")
            .annotate(count=Count("id"))
            .order_by("-count", "played_instrument__name"),
        }

    paginator = Paginator(records, ATTENDANCE_PAGE_SIZE)
    page_obj = paginator.get_page(request.GET.get("page"))

    return render(request, "member/attendance.html", {
        "member": member,
        "stats": stats,
        "page_obj": page_obj,
    })


@login_required
@require_GET
def rental_request_detail(request, pk):
    if not hasattr(request.user, "member"):
        return redirect("/")
    rental_request = get_object_or_404(
        InstrumentRentalRequestSubmission.objects.select_related("instrument", "second_choice", "third_choice"),
        pk=pk,
        member=request.user.member,
    )
    return render(request, "member/rental_request_detail.html", {"rental_request": rental_request})


@login_required
def instrument_rental_request(request):
    if not hasattr(request.user, "member"):
        logger.info(f"User without member attribute attempted to access instrument rental request: {request.user}")
        return redirect("/")
    member = request.user.member
    site_settings = SiteSettings.for_request(request)

    if not site_settings.instrument_rental_policy:
        return render(request, "member/instrument_rental_request.html", {
            "member": member,
            "rental_not_configured": True,
            "include_form_js": True,
        })

    missing = [
        label
        for label, val in [
            ("name", member.full_name),
            ("email", member.email),
            ("phone", member.phone),
            ("street address", member.address),
            ("city", member.city),
            ("state", member.state),
            ("zip code", member.zip_code),
            ("country", member.country),
        ]
        if not val
    ]
    if missing:
        messages.warning(
            request,
            f"Please add your {', '.join(missing)} before requesting an instrument rental.",
        )
        return redirect("member-profile")

    if request.method == "POST":
        is_valid_captcha, captcha_error = _validate_recaptcha(request)
        if not is_valid_captcha:
            form = InstrumentRentalRequestForm()
            return render(request, "member/instrument_rental_request.html", {
                "member": member,
                "form": form,
                "policy_text": site_settings.instrument_rental_policy,
                "recaptcha_error": captcha_error,
                "include_form_js": True,
            })
        form = InstrumentRentalRequestForm(request.POST)
        if form.is_valid():
            instrument = form.cleaned_data["instrument"]
            second_choice = form.cleaned_data.get("second_choice")
            third_choice = form.cleaned_data.get("third_choice")
            available = instrument.library_inventory.filter(
                status=LibraryInstrument.STATUS_AVAILABLE
            ).count()
            is_waitlist = available == 0

            submission = InstrumentRentalRequestSubmission.objects.create(
                member=member,
                name=member.full_name,
                email=member.email,
                phone=member.phone or "",
                address=member.address or "",
                instrument=instrument,
                second_choice=second_choice,
                third_choice=third_choice,
                is_waitlist=is_waitlist,
                message=form.cleaned_data.get("notes") or "",
                policy_acknowledged=True,
                status=InstrumentRentalRequestSubmission.STATUS_PENDING,
            )

            # Validate Patreon membership for the submitting member.
            # Runs after save so the submission always exists regardless of API outcome.
            patreon_result = check_patreon_membership(member.email)
            submission.patreon_validated = patreon_result["is_active"] if patreon_result is not None else None
            submission.patreon_pledge_cents = patreon_result["pledge_cents"] if patreon_result is not None else None
            submission.patreon_last_charge_date = patreon_result["last_charge_date"] if patreon_result is not None else None
            submission.patreon_last_charge_status = patreon_result["last_charge_status"] if patreon_result is not None else None
            submission.patreon_patron_since = patreon_result["patron_since"] if patreon_result is not None else None
            submission.patreon_lifetime_cents = patreon_result["lifetime_cents"] if patreon_result is not None else None
            submission.save(update_fields=["patreon_validated", "patreon_pledge_cents", "patreon_last_charge_date", "patreon_last_charge_status", "patreon_patron_since", "patreon_lifetime_cents"])

            # Cache Patreon result on the Member so bulk operations can skip the API.
            if patreon_result is not None:
                from django.utils import timezone
                member.patreon_is_active = patreon_result["is_active"]
                member.patreon_pledge_cents = patreon_result["pledge_cents"]
                member.patreon_last_charge_date = patreon_result["last_charge_date"]
                member.patreon_last_charge_status = patreon_result["last_charge_status"]
                member.patreon_patron_since = patreon_result["patron_since"]
                member.patreon_lifetime_cents = patreon_result["lifetime_cents"]
                member.patreon_last_synced = timezone.now()
                member.save(update_fields=["patreon_is_active", "patreon_pledge_cents", "patreon_last_charge_date", "patreon_last_charge_status", "patreon_patron_since", "patreon_lifetime_cents", "patreon_last_synced"])

            recipients = [
                r.strip()
                for r in (site_settings.instrument_rental_notification_recipients or "").split(",")
                if r.strip()
            ]
            if recipients:
                choices_text = f"1st choice: {instrument.name}"
                if second_choice:
                    choices_text += f"\n2nd choice: {second_choice.name}"
                if third_choice:
                    choices_text += f"\n3rd choice: {third_choice.name}"
                review_url = request.build_absolute_uri(f"/admin/rental-requests/{submission.pk}/")
                if patreon_result is not None and patreon_result["is_active"]:
                    patreon_line = "Patreon: ACTIVE PATRON (verified at submission)"
                elif patreon_result is not None:
                    patreon_line = (
                        "Patreon: NOT FOUND or INACTIVE — please verify Patreon membership "
                        "before assigning an instrument."
                    )
                else:
                    patreon_line = "Patreon: not checked (API not configured or unavailable)"
                manager_body = (
                    f"Instrument Rental Request [PENDING]\n\n"
                    f"Member: {member.full_name}\n"
                    f"Email: {member.email}\n"
                    f"Phone: {member.phone or 'not provided'}\n"
                    f"Address: {member.address or 'not provided'}\n"
                    f"{choices_text}\n"
                    f"Notes: {submission.message or '—'}\n"
                    f"{patreon_line}\n\n"
                    f"Review and approve/deny:\n{review_url}\n"
                )
                _MemberEmail(
                    subject=f"Instrument Rental Request — {member.full_name} ({instrument.name})",
                    body=manager_body,
                    from_email=settings.FROM_EMAIL,
                    to=recipients,
                ).send(fail_silently=True)

            if member.email:
                pending_body = render_to_string(
                    "emails/instrument_rental_request_pending.txt",
                    {
                        "member": member,
                        "instrument": instrument,
                        "second_choice": second_choice,
                        "third_choice": third_choice,
                        "notes": submission.message,
                        "contact_emails": site_settings.instrument_rental_notification_recipients,
                    },
                )
                _MemberEmail(
                    subject=f"Your instrument rental request — {instrument.name}",
                    body=pending_body,
                    from_email=settings.FROM_EMAIL,
                    to=[member.email],
                ).send(fail_silently=True)

            return render(request, "member/instrument_rental_request.html", {
                "member": member,
                "submitted": True,
                "is_waitlist": is_waitlist,
                "instrument": instrument,
                "include_form_js": True,
            })

        return render(request, "member/instrument_rental_request.html", {
            "member": member,
            "form": form,
            "policy_text": site_settings.instrument_rental_policy,
            "include_form_js": True,
        })

    form = InstrumentRentalRequestForm()
    return render(request, "member/instrument_rental_request.html", {
        "member": member,
        "form": form,
        "policy_text": site_settings.instrument_rental_policy,
        "include_form_js": True,
    })


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
