import logging
import os
import tempfile
from datetime import date, timedelta
from io import StringIO

from django import forms as django_forms
from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import permission_required
from django.core.mail import send_mail
from django.core.management import call_command
from django.core.paginator import Paginator
from django.db.models import Q
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.template.loader import render_to_string
from django.utils import timezone
from django.views.decorators.http import require_http_methods

from blowcomotion.models import (
    Instrument,
    InstrumentHistoryLog,
    InstrumentRentalNagLog,
    InstrumentRentalRequestSubmission,
    InstrumentStorageLocation,
    LibraryInstrument,
    Member,
    SiteSettings,
)
from instruments.forms import LibraryInstrumentRentForm, LibraryInstrumentReturnForm
from instruments.patreon import MIN_RENTAL_PLEDGE_CENTS, fetch_all_members
from members.auth import _MemberEmail

logger = logging.getLogger(__name__)

# Instrument Library Dashboard Views


@permission_required('blowcomotion.change_libraryinstrument', raise_exception=True)
def instrument_library_rented(request):
    instruments = (
        LibraryInstrument.objects.filter(status=LibraryInstrument.STATUS_RENTED)
        .select_related('instrument', 'member', 'storage_location')
        .order_by('instrument__name', 'serial_number')
    )
    return render(
        request,
        'instrument_library/list.html',
        {
            'page_title': 'Rented Instruments',
            'instruments': instruments,
        },
    )


@permission_required('blowcomotion.change_libraryinstrument', raise_exception=True)
def instrument_library_available(request):
    instruments = (
        LibraryInstrument.objects.filter(status=LibraryInstrument.STATUS_AVAILABLE)
        .select_related('instrument', 'member', 'storage_location')
        .order_by('instrument__name', 'serial_number')
    )
    return render(
        request,
        'instrument_library/list.html',
        {
            'page_title': 'Available Instruments',
            'instruments': instruments,
        },
    )


@permission_required('blowcomotion.change_libraryinstrument', raise_exception=True)
def instrument_library_needs_repair(request):
    instruments = (
        LibraryInstrument.objects.filter(
            status__in=[
                LibraryInstrument.STATUS_NEEDS_REPAIR,
                LibraryInstrument.STATUS_OUT_FOR_REPAIR,
            ]
        )
        .select_related('instrument', 'member', 'storage_location')
        .order_by('instrument__name', 'serial_number')
    )
    return render(
        request,
        'instrument_library/list.html',
        {
            'page_title': 'Instruments Needing Repair / Maintenance',
            'instruments': instruments,
        },
    )


GALLERY_PAGE_SIZE = 24


@permission_required('blowcomotion.change_libraryinstrument', raise_exception=True)
def instrument_library_gallery(request):
    instruments = (
        LibraryInstrument.objects.select_related('instrument', 'member', 'storage_location')
        .prefetch_related('photos__image')
        .order_by('instrument__name', 'serial_number')
    )

    status = request.GET.get('status', '')
    instrument_id = request.GET.get('instrument', '')
    storage_location_id = request.GET.get('storage_location', '')
    query = request.GET.get('q', '').strip()

    if status:
        instruments = instruments.filter(status=status)
    if instrument_id.isdigit():
        instruments = instruments.filter(instrument_id=instrument_id)
    if storage_location_id.isdigit():
        instruments = instruments.filter(storage_location_id=storage_location_id)
    if query:
        instruments = instruments.filter(
            Q(serial_number__icontains=query) | Q(instrument__name__icontains=query)
        )

    paginator = Paginator(instruments, GALLERY_PAGE_SIZE)
    page_obj = paginator.get_page(request.GET.get('page'))

    querystring = request.GET.copy()
    querystring.pop('page', None)
    querystring = querystring.urlencode()
    if querystring:
        querystring += '&'

    return render(
        request,
        'wagtailadmin/instrument_library_gallery.html',
        {
            'page_title': 'Instrument Gallery',
            'page_obj': page_obj,
            'status_choices': LibraryInstrument.STATUS_CHOICES,
            'instrument_choices': Instrument.objects.order_by('name'),
            'storage_location_choices': InstrumentStorageLocation.objects.order_by('name'),
            'selected_status': status,
            'selected_instrument': instrument_id,
            'selected_storage_location': storage_location_id,
            'query': query,
            'querystring': querystring,
        },
    )


@require_http_methods(["GET", "POST"])
def instrument_library_quick_rent(request):
    available_qs = LibraryInstrument.objects.filter(
        status=LibraryInstrument.STATUS_AVAILABLE
    ).select_related('instrument')
    rented_qs = LibraryInstrument.objects.filter(
        status=LibraryInstrument.STATUS_RENTED
    ).select_related('instrument', 'member')

    instrument_id = request.GET.get('instrument')
    initial_instrument = None
    if instrument_id:
        try:
            initial_instrument = available_qs.get(pk=instrument_id)
        except LibraryInstrument.DoesNotExist:
            messages.error(request, "That instrument is no longer available to rent.")
            return redirect('instrument_library_quick_rent')

    action = request.POST.get('action') if request.method == 'POST' else None

    rent_form = LibraryInstrumentRentForm(
        request.POST if action == 'rent' else None,
        instrument_queryset=available_qs,
        initial_instrument=initial_instrument,
    )
    return_form = LibraryInstrumentReturnForm(
        request.POST if action == 'return' else None,
    )

    if request.method == 'POST':
        if action == 'rent':
            if rent_form.is_valid():
                instrument = rent_form.cleaned_data['instrument']
                member = rent_form.cleaned_data['member']

                if instrument.status != LibraryInstrument.STATUS_AVAILABLE:
                    messages.error(request, "Instrument is no longer available to rent.")
                    rent_form.add_error('instrument', "Instrument is no longer available to rent.")
                else:
                    instrument.member = member
                    instrument.status = LibraryInstrument.STATUS_RENTED
                    instrument.rental_date = (
                        rent_form.cleaned_data['rental_date'] or timezone.localdate()
                    )
                    # TODO(#250): remove — agreement_signed_date dropped in rental v2
                    # instrument.agreement_signed_date = rent_form.cleaned_data[
                    #     'agreement_signed_date'
                    # ]
                    instrument.patreon_active = rent_form.cleaned_data['patreon_active']
                    instrument.patreon_amount = rent_form.cleaned_data['patreon_amount']
                    comments = rent_form.cleaned_data['comments']
                    if comments:
                        instrument.comments = comments

                    instrument.save()

                    # Update member's renting status
                    member.renting = True
                    member.save()

                    # TODO(#250): remove — LibraryInstrumentDocument dropped in rental v2
                    # rental_document = rent_form.cleaned_data.get('rental_document')
                    # if rental_document:
                    #     LibraryInstrumentDocument.objects.create(
                    #         library_instrument=instrument,
                    #         document=rental_document,
                    #         description=rent_form.cleaned_data.get('document_description', ''),
                    #     )

                    if comments:
                        InstrumentHistoryLog.objects.create(
                            library_instrument=instrument,
                            event_category=InstrumentHistoryLog.EVENT_RENTAL_NOTE,
                            event_date=timezone.localdate(),
                            notes=f"Rental notes: {comments}",
                            user=request.user,
                        )

                    messages.success(
                        request,
                        f"{instrument.instrument.name} rented to {member.full_name}.",
                    )
                    return redirect('instrument_library_quick_rent')

        elif action == 'return':
            if return_form.is_valid():
                instrument = return_form.cleaned_data['instrument']
                condition_notes = return_form.cleaned_data['condition_notes']
                previous_member = instrument.member

                if instrument.status != LibraryInstrument.STATUS_RENTED:
                    messages.error(request, "Instrument is not currently rented out.")
                    return_form.add_error('instrument', "Instrument is not currently rented out.")
                else:
                    instrument.status = LibraryInstrument.STATUS_AVAILABLE
                    instrument.member = None
                    instrument.rental_date = None
                    # instrument.agreement_signed_date = None  # TODO(#250): remove
                    instrument.patreon_active = False
                    instrument.patreon_amount = None
                    instrument.save()

                    # Update previous member's renting status if they have no other rentals
                    if previous_member:
                        still_renting = LibraryInstrument.objects.filter(
                            member=previous_member,
                            status=LibraryInstrument.STATUS_RENTED
                        ).exists()
                        if not still_renting:
                            previous_member.renting = False
                            previous_member.save()

                    if condition_notes:
                        InstrumentHistoryLog.objects.create(
                            library_instrument=instrument,
                            event_category=InstrumentHistoryLog.EVENT_RETURN_NOTE,
                            event_date=timezone.localdate(),
                            notes=f"Return notes: {condition_notes}",
                            user=request.user,
                        )

                    renter_display = (
                        previous_member.full_name if previous_member else 'previous renter'
                    )
                    messages.success(
                        request,
                        f"{instrument.instrument.name} returned from {renter_display}.",
                    )
                    return redirect('instrument_library_quick_rent')
            else:
                # Form validation failed - likely no instrument selected
                if 'instrument' in return_form.errors:
                    messages.error(
                        request,
                        "Please select an instrument to return by clicking the 'Return' button next to it in the 'Currently rented' list above."
                    )

    context = {
        'page_title': 'Instrument Library Quick Rent',
        'rent_form': rent_form,
        'return_form': return_form,
        'available_instruments': available_qs,
        'rented_instruments': rented_qs,
        'selected_instrument': initial_instrument,
    }

    return render(request, 'instrument_library/manage.html', context)


def export_library_instruments_csv(request):
    if not request.user.has_perm('blowcomotion.access_real_data_exports'):
        logger.warning("Unauthorized access attempt to export library instruments by user %s", request.user.username)
        return JsonResponse({'error': 'You do not have permission to access this feature'}, status=403)

    temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.csv')
    temp_path = temp_file.name
    temp_file.close()

    try:
        logger.info("Starting library instrument export by user %s", request.user.username)
        call_command(
            'export_library_instruments_to_csv',
            output_path=temp_path,
            stdout=StringIO(),
        )

    except Exception:
        logger.exception("Error during library instrument export by user %s", request.user.username)
        return JsonResponse({'error': 'Export failed. See server logs for details.'}, status=500)
    else:
        with open(temp_path, 'rb') as csv_file:
            csv_data = csv_file.read()

        timestamp = timezone.now().strftime('%Y%m%d-%H%M%S')
        filename = f'library_instruments_export_{timestamp}.csv'
        response = HttpResponse(csv_data, content_type='text/csv')
        response['Content-Disposition'] = f'attachment; filename="{filename}"'
        logger.info("Library instrument export completed successfully by user %s", request.user.username)
        return response
    finally:
        try:
            os.remove(temp_path)
        except OSError:
            logger.warning("Temporary file %s could not be removed after library instrument export", temp_path)


# ── Rental Request Admin Views ──────────────────────────────────────────────────


class RentalRequestReviewForm(django_forms.Form):
    unit = django_forms.ModelChoiceField(
        queryset=LibraryInstrument.objects.none(),
        required=False,
        empty_label="Select a unit to assign",
        label="Assign instrument unit",
    )
    message = django_forms.CharField(
        widget=django_forms.Textarea(attrs={"rows": 4}),
        label="Message to member",
        required=True,
    )

    def __init__(self, *args, submission=None, **kwargs):
        super().__init__(*args, **kwargs)
        if submission:
            choices = [submission.instrument]
            if submission.second_choice:
                choices.append(submission.second_choice)
            if submission.third_choice:
                choices.append(submission.third_choice)
            qs = LibraryInstrument.objects.filter(
                status=LibraryInstrument.STATUS_AVAILABLE,
                instrument__in=choices,
            ).select_related("instrument")
            self.fields["unit"].queryset = qs
            self.fields["unit"].label_from_instance = (
                lambda obj: f"{obj.instrument.name} — {obj.serial_number}"
            )


def _send_rental_approved_email(request, submission):
    if not (submission.member and submission.member.email):
        return
    site_settings = SiteSettings.for_request(request)
    body = render_to_string(
        "emails/instrument_rental_request_approved.txt",
        {
            "member": submission.member,
            "instrument": submission.instrument,
            "assigned_unit": submission.assigned_unit,
            "admin_message": submission.admin_message,
            "patreon_url": site_settings.patreon_url,
            "contact_emails": site_settings.instrument_rental_notification_recipients,
        },
    )
    _MemberEmail(
        subject=f"Your instrument rental request has been approved — {submission.instrument.name}",
        body=body,
        from_email=settings.FROM_EMAIL,
        to=[submission.member.email],
    ).send(fail_silently=True)


def _send_rental_denied_email(request, submission):
    if not (submission.member and submission.member.email):
        return
    site_settings = SiteSettings.for_request(request)
    body = render_to_string(
        "emails/instrument_rental_request_denied.txt",
        {
            "member": submission.member,
            "instrument": submission.instrument,
            "admin_message": submission.admin_message,
            "contact_emails": site_settings.instrument_rental_notification_recipients,
        },
    )
    _MemberEmail(
        subject=f"Your instrument rental request — {submission.instrument.name}",
        body=body,
        from_email=settings.FROM_EMAIL,
        to=[submission.member.email],
    ).send(fail_silently=True)


def _send_rental_returned_email(request, submission, condition_notes):
    site_settings = SiteSettings.for_request(request)
    admin_recipients = [
        e.strip()
        for e in (site_settings.instrument_rental_notification_recipients or "").split(",")
        if e.strip()
    ]
    ctx = {
        "member": submission.member,
        "instrument": submission.instrument,
        "assigned_unit": submission.assigned_unit,
        "condition_notes": condition_notes,
        "contact_emails": site_settings.instrument_rental_notification_recipients,
    }
    if submission.member and submission.member.email:
        body = render_to_string("emails/instrument_rental_request_returned.txt", ctx)
        _MemberEmail(
            subject=f"Your {submission.instrument.name} rental has been returned",
            body=body,
            from_email=settings.FROM_EMAIL,
            to=[submission.member.email],
        ).send(fail_silently=True)
    if admin_recipients:
        lines = [
            f"{submission.name} has returned {submission.assigned_unit or submission.instrument.name}.",
        ]
        if condition_notes:
            lines.append(f"\nCondition notes: {condition_notes}")
        _MemberEmail(
            subject=f"Instrument returned: {submission.instrument.name} — {submission.name}",
            body="\n".join(lines),
            from_email=settings.FROM_EMAIL,
            to=admin_recipients,
        ).send(fail_silently=True)


@permission_required('blowcomotion.change_libraryinstrument', raise_exception=True)
def rental_requests_dashboard(request):
    import re as _re

    from wagtail.models import Site

    from django.contrib import messages
    from django.db.models import Case, IntegerField, Value, When

    site_settings = _get_site_settings_for_view()
    today = date.today()
    site = Site.objects.filter(is_default_site=True).first() or Site.objects.first()
    base_url = site.root_url if site else "https://blowcomotion.org"
    patreon_url = (site_settings.patreon_url or "") if site_settings else ""
    cooldown_days = site_settings.nag_cooldown_days if site_settings else 7
    cleanup_days = site_settings.attendance_cleanup_days if site_settings else 90
    cutoff = today - timedelta(days=cleanup_days)
    raw_recipients = (site_settings.instrument_rental_notification_recipients or "") if site_settings else ""
    admin_recipients = [r.strip() for r in _re.split(r"[,\n]", raw_recipients) if r.strip()]

    if request.method == "POST":
        action = request.POST.get("action")

        if action == "refresh_patreon":
            from django.utils import timezone

            patreon_data = fetch_all_members()
            if patreon_data is None:
                messages.error(request, "Patreon API not configured or error fetching members.")
                return redirect("rental_requests_dashboard")

            now = timezone.now()
            _not_found = {"is_active": False, "pledge_cents": None, "last_charge_date": None,
                          "last_charge_status": None, "patron_since": None, "lifetime_cents": None}
            _sub_fields = ["patreon_validated", "patreon_pledge_cents", "patreon_last_charge_date",
                           "patreon_last_charge_status", "patreon_patron_since", "patreon_lifetime_cents"]
            _member_fields = ["patreon_is_active", "patreon_pledge_cents", "patreon_last_charge_date",
                               "patreon_last_charge_status", "patreon_patron_since", "patreon_lifetime_cents",
                               "patreon_last_synced"]

            updated = skipped = 0
            for sub in InstrumentRentalRequestSubmission.objects.select_related("member"):
                email = sub.member.email if sub.member else None
                if not email:
                    skipped += 1
                    continue
                result = patreon_data.get(email.lower(), _not_found)
                sub.patreon_validated = result["is_active"]
                sub.patreon_pledge_cents = result["pledge_cents"]
                sub.patreon_last_charge_date = result["last_charge_date"]
                sub.patreon_last_charge_status = result["last_charge_status"]
                sub.patreon_patron_since = result["patron_since"]
                sub.patreon_lifetime_cents = result["lifetime_cents"]
                sub.save(update_fields=_sub_fields)
                updated += 1

            for member in Member.objects.exclude(email="").exclude(email__isnull=True):
                result = patreon_data.get(member.email.lower())
                if result is None:
                    continue
                member.patreon_is_active = result["is_active"]
                member.patreon_pledge_cents = result["pledge_cents"]
                member.patreon_last_charge_date = result["last_charge_date"]
                member.patreon_last_charge_status = result["last_charge_status"]
                member.patreon_patron_since = result["patron_since"]
                member.patreon_lifetime_cents = result["lifetime_cents"]
                member.patreon_last_synced = now
                member.save(update_fields=_member_fields)

            for li in LibraryInstrument.objects.select_related("member"):
                member = li.member
                if not member:
                    continue
                result = patreon_data.get((member.email or "").lower())
                new_active = bool(result and result["is_active"] and (result["pledge_cents"] or 0) >= MIN_RENTAL_PLEDGE_CENTS)
                if li.patreon_active != new_active:
                    li.patreon_active = new_active
                    li.save(update_fields=["patreon_active"])

            msg = f"Patreon refresh: {updated} submissions updated, {len(patreon_data)} Patreon members fetched"
            if skipped:
                msg += f", {skipped} skipped (no email)"
            messages.success(request, msg)
            return redirect("rental_requests_dashboard")

        elif action == "nag_one":
            pk = request.POST.get("pk")
            sub = get_object_or_404(
                InstrumentRentalRequestSubmission,
                pk=pk,
                status=InstrumentRentalRequestSubmission.STATUS_APPROVED,
            )
            li = sub.assigned_unit
            if not li or not li.member or not li.member.email:
                messages.error(request, f"Cannot nag {sub.name}: no assigned unit or member email.")
                return redirect("rental_requests_dashboard")

            if li.status != LibraryInstrument.STATUS_RENTED:
                messages.error(request, f"Cannot nag {sub.name}: instrument is not currently rented.")
                return redirect("rental_requests_dashboard")

            if li.last_nag_sent and (today - li.last_nag_sent).days < cooldown_days:
                messages.warning(request, f"Nag not sent — {sub.name} is still in the cooldown period (last nag: {li.last_nag_sent}).")
                return redirect("rental_requests_dashboard")

            member = li.member
            reasons = []
            if not member.is_active or not member.last_seen or member.last_seen < cutoff:
                reasons.append("attendance")
            if sub.patreon_validated is not True:
                reasons.append("patreon")

            if not reasons:
                messages.warning(request, f"No nag reasons for {sub.name} — member appears active in attendance and Patreon.")
                return redirect("rental_requests_dashboard")

            # Atomic cooldown gate — prevents double-send on concurrent clicks
            claimed = LibraryInstrument.objects.filter(pk=li.pk).filter(
                Q(last_nag_sent__isnull=True) |
                Q(last_nag_sent__lte=today - timedelta(days=cooldown_days))
            ).update(last_nag_sent=today)
            if not claimed:
                messages.warning(request, f"Nag not sent — {sub.name} was already nagged (concurrent request).")
                return redirect("rental_requests_dashboard")

            subject, body = _build_nag_email(li, member, base_url, patreon_url, reasons)
            try:
                send_mail(subject, body, settings.FROM_EMAIL, [member.email], fail_silently=False)
            except Exception as exc:
                LibraryInstrument.objects.filter(pk=li.pk).update(last_nag_sent=li.last_nag_sent)
                messages.error(request, f"Failed to send nag email to {member.full_name}: {exc}")
                return redirect("rental_requests_dashboard")

            InstrumentRentalNagLog.objects.create(
                library_instrument=li,
                member_name=member.full_name,
                member_email=member.email,
                reasons="+".join(reasons),
                sent_at=today,
            )
            messages.success(request, f"Nag email sent to {member.full_name} ({li.instrument.name}) — {'+'.join(reasons)}.")
            return redirect("rental_requests_dashboard")

        elif action == "nag_all":
            candidates = _get_nag_all_candidates(cutoff)

            nagged = []
            failed = []
            skipped_cooldown = 0
            for candidate in candidates:
                li = candidate["instrument"]
                member = candidate["member"]
                reasons = candidate["reasons"]

                # Atomic cooldown gate — prevents double-send on concurrent clicks
                claimed = LibraryInstrument.objects.filter(pk=li.pk).filter(
                    Q(last_nag_sent__isnull=True) |
                    Q(last_nag_sent__lte=today - timedelta(days=cooldown_days))
                ).update(last_nag_sent=today)
                if not claimed:
                    skipped_cooldown += 1
                    continue

                subject, body = _build_nag_email(li, member, base_url, patreon_url, reasons)
                try:
                    send_mail(subject, body, settings.FROM_EMAIL, [member.email], fail_silently=False)
                except Exception as exc:
                    LibraryInstrument.objects.filter(pk=li.pk).update(last_nag_sent=li.last_nag_sent)
                    failed.append(f"{member.full_name} ({li.instrument.name}): {exc}")
                    continue

                InstrumentRentalNagLog.objects.create(
                    library_instrument=li,
                    member_name=member.full_name,
                    member_email=member.email,
                    reasons="+".join(reasons),
                    sent_at=today,
                )
                nagged.append({"instrument": li, "member": member, "reasons": reasons})

            if nagged or failed:
                summary_lines = [
                    f"Instrument Rental Nag Summary — {today}",
                    "=" * 50,
                    "",
                    f"Nag emails sent to {len(nagged)} renter(s):",
                    "",
                ]
                for item in nagged:
                    m = item["member"]
                    reason_label = " + ".join(item["reasons"])
                    last_seen_note = f", last seen {m.last_seen}" if m.last_seen and "attendance" in item["reasons"] else ""
                    summary_lines.append(f"  * {m.full_name} — {item['instrument'].instrument.name} (Reason: {reason_label}{last_seen_note})")
                if failed:
                    summary_lines += ["", f"Failed ({len(failed)}):"]
                    summary_lines.extend(f"  * {f}" for f in failed)
                summary_lines += ["", f"Skipped (cooldown active): {skipped_cooldown} renter(s)"]
                summary_body = "\n".join(summary_lines)
                summary_subject = f"Instrument Rental Nag Summary — {today}"
                if admin_recipients:
                    send_mail(summary_subject, summary_body, settings.FROM_EMAIL, admin_recipients, fail_silently=False)
                    extra = getattr(settings, "FORM_TEST_EMAIL", None)
                    if extra:
                        send_mail(f"[COPY] {summary_subject}", summary_body, settings.FROM_EMAIL, [extra], fail_silently=False)
                msg = f"Nag all: {len(nagged)} email(s) sent, {skipped_cooldown} skipped (cooldown)"
                if failed:
                    msg += f", {len(failed)} failed"
                messages.success(request, msg + ".")
            else:
                messages.info(request, f"Nag all: nothing to send ({skipped_cooldown} skipped by cooldown).")
            return redirect("rental_requests_dashboard")

        elif action == "delete":
            pk = request.POST.get("pk")
            sub = get_object_or_404(
                InstrumentRentalRequestSubmission,
                pk=pk,
                status=InstrumentRentalRequestSubmission.STATUS_DENIED,
            )
            name = sub.name
            sub.delete()
            messages.success(request, f"Deleted denied rental request from {name}.")
            return redirect("rental_requests_dashboard")

    submissions = list(
        InstrumentRentalRequestSubmission.objects.annotate(
            status_order=Case(
                When(status=InstrumentRentalRequestSubmission.STATUS_PENDING, then=Value(0)),
                default=Value(1),
                output_field=IntegerField(),
            )
        )
        .order_by("status_order", "-date_submitted")
        .select_related("member", "instrument", "second_choice", "third_choice", "assigned_unit",
                        "assigned_unit__member", "assigned_unit__instrument")
    )
    for sub in submissions:
        li = sub.assigned_unit
        sub.nag_in_cooldown = bool(
            sub.status == InstrumentRentalRequestSubmission.STATUS_APPROVED
            and li
            and li.last_nag_sent
            and (today - li.last_nag_sent).days < cooldown_days
        )
        nag_eligible = False
        if (sub.status == InstrumentRentalRequestSubmission.STATUS_APPROVED
                and li and li.member and li.member.email):
            m = li.member
            nag_eligible = (
                not m.is_active or not m.last_seen or m.last_seen < cutoff
                or sub.patreon_validated is not True
            )
        sub.nag_eligible = nag_eligible

    nag_all_preview = []
    sendable_lines = []
    for candidate in _get_nag_all_candidates(cutoff):
        li = candidate["instrument"]
        in_cooldown = bool(li.last_nag_sent and (today - li.last_nag_sent).days < cooldown_days)
        reason_label = " + ".join(candidate["reasons"])
        nag_all_preview.append({
            "member": candidate["member"],
            "instrument": li,
            "reasons": candidate["reasons"],
            "cta": _nag_cta_for_reasons(candidate["reasons"]),
            "in_cooldown": in_cooldown,
        })
        if not in_cooldown:
            sendable_lines.append(f"{candidate['member'].full_name} ({li.instrument.name}) — {reason_label}")

    if sendable_lines:
        nag_all_confirm_message = "Send nag emails to the following renters?\n\n" + "\n".join(sendable_lines)
    elif nag_all_preview:
        nag_all_confirm_message = "No emails will be sent — all eligible renters are currently in cooldown."
    else:
        nag_all_confirm_message = "No renters are currently eligible for a nag email."

    return render(request, "wagtailadmin/rental_requests_dashboard.html", {
        "submissions": submissions,
        "nag_all_preview": nag_all_preview,
        "nag_all_confirm_message": nag_all_confirm_message,
    })


@permission_required('blowcomotion.change_libraryinstrument', raise_exception=True)
def rental_request_review(request, pk):
    submission = get_object_or_404(InstrumentRentalRequestSubmission, pk=pk)
    form = RentalRequestReviewForm(submission=submission)

    if (
        request.method == "POST"
        and submission.status == InstrumentRentalRequestSubmission.STATUS_PENDING
    ):
        action = request.POST.get("action")
        form = RentalRequestReviewForm(request.POST, submission=submission)
        if form.is_valid():
            unit = form.cleaned_data.get("unit")
            message = form.cleaned_data["message"]
            if action == "approve":
                if not unit:
                    form.add_error("unit", "Please select a unit to assign for approval.")
                else:
                    submission.prior_storage_location = unit.storage_location
                    unit.member = submission.member
                    unit.status = LibraryInstrument.STATUS_RENTED
                    unit.rental_date = date.today()
                    unit.storage_location = None
                    unit.save()
                    if submission.member:
                        submission.member.renting = True
                        submission.member.save()
                    submission.status = InstrumentRentalRequestSubmission.STATUS_APPROVED
                    submission.admin_message = message
                    submission.assigned_unit = unit
                    submission.save()
                    _send_rental_approved_email(request, submission)
                    messages.success(request, f"Approved — {submission.name} has been notified.")
                    return redirect("rental_requests_dashboard")
            elif action == "deny":
                submission.status = InstrumentRentalRequestSubmission.STATUS_DENIED
                submission.admin_message = message
                submission.save()
                _send_rental_denied_email(request, submission)
                messages.success(request, f"Denied — {submission.name} has been notified.")
                return redirect("rental_requests_dashboard")

    return render(request, "wagtailadmin/rental_request_review.html", {
        "submission": submission,
        "form": form,
    })


@permission_required('blowcomotion.change_libraryinstrument', raise_exception=True)
def rental_request_return(request, pk):
    submission = get_object_or_404(
        InstrumentRentalRequestSubmission,
        pk=pk,
        status=InstrumentRentalRequestSubmission.STATUS_APPROVED,
    )
    unit = submission.assigned_unit
    if not unit or unit.status != LibraryInstrument.STATUS_RENTED:
        messages.error(request, "This instrument is not currently rented out.")
        return redirect("rental_request_review", pk=pk)

    if request.method == "POST":
        condition_notes = request.POST.get("condition_notes", "").strip()
        previous_member = unit.member

        unit.status = LibraryInstrument.STATUS_AVAILABLE
        unit.member = None
        unit.rental_date = None
        unit.patreon_active = False
        unit.patreon_amount = None
        unit.storage_location = submission.prior_storage_location
        unit.save()

        if submission.prior_storage_location is None:
            messages.warning(
                request,
                f"Instrument returned from {submission.name}, but no prior storage location was recorded. "
                "Please assign a storage location manually in Library Instruments.",
            )

        if previous_member:
            still_renting = LibraryInstrument.objects.filter(
                member=previous_member, status=LibraryInstrument.STATUS_RENTED
            ).exists()
            if not still_renting:
                previous_member.renting = False
                previous_member.save()

        if condition_notes:
            InstrumentHistoryLog.objects.create(
                library_instrument=unit,
                event_category=InstrumentHistoryLog.EVENT_RETURN_NOTE,
                event_date=timezone.localdate(),
                notes=f"Return notes: {condition_notes}",
                user=request.user,
            )

        submission.status = InstrumentRentalRequestSubmission.STATUS_RETURNED
        submission.save()

        _send_rental_returned_email(request, submission, condition_notes)

        messages.success(request, f"Instrument returned from {submission.name}.")
        return redirect("rental_requests_dashboard")

    return render(request, "wagtailadmin/rental_request_return.html", {
        "submission": submission,
    })


def _get_site_settings_for_view():
    from wagtail.models import Site
    site = Site.objects.filter(is_default_site=True).first() or Site.objects.first()
    if not site:
        return None
    return SiteSettings.for_site(site)


def _get_nag_all_candidates(cutoff):
    """Return the list of renters that 'Nag all eligible renters' would email right now.

    Read-only — does not touch cooldown state or send anything. Used both to build the
    confirmation preview shown before the bulk nag runs and, as the source of truth for
    eligibility/reasons, by the nag_all POST handler itself, so the preview can never
    drift from what actually gets sent.

    Each item: {"instrument": LibraryInstrument, "member": Member, "reasons": [...]}.
    "reasons" may include "attendance" and/or "patreon"; see _build_nag_email for how
    reasons map to the CTA included in the email.
    """
    instruments = LibraryInstrument.objects.filter(
        status=LibraryInstrument.STATUS_RENTED,
        member__isnull=False,
        member__email__isnull=False,
    ).exclude(member__email="").select_related("member", "instrument")

    candidates = []
    for li in instruments:
        member = li.member
        reasons = []
        if not member.is_active or not member.last_seen or member.last_seen < cutoff:
            reasons.append("attendance")
        if not li.patreon_active:
            reasons.append("patreon")
        if not reasons:
            continue
        candidates.append({"instrument": li, "member": member, "reasons": reasons})
    return candidates


def _nag_cta_for_reasons(reasons):
    """Return the nag email's call-to-action slug ('staying' or 'patreon-updated') for reasons.

    Single source of truth for the reason->CTA mapping, shared by _build_nag_email (which
    builds the actual confirm link) and the nag-all preview (which just labels it) so the
    two can't drift apart.
    """
    return "staying" if "attendance" in reasons else "patreon-updated"


def _build_nag_email(li, member, base_url, patreon_url, reasons):
    """Build (subject, message) for a rental nag email. reasons is a list of 'attendance'/'patreon'."""
    from django.core.signing import TimestampSigner
    token = TimestampSigner().sign(str(li.pk))
    first_name = member.first_name or member.full_name
    lines = [
        f"Hi {first_name},",
        "",
        f"We wanted to check in about the {li.instrument.name} you're renting from Blowcomotion.",
        "",
    ]
    if "attendance" in reasons:
        last_seen_str = str(member.last_seen) if member.last_seen else "unknown"
        lines += [
            f"We haven't seen you at rehearsal in a while (last seen: {last_seen_str}). We'd love to have you back!",
            "",
        ]
    if "patreon" in reasons:
        patreon_line = "Our records show your Patreon membership may not be current. Keeping it active helps us maintain the instrument library."
        if patreon_url:
            patreon_line += f" You can activate or renew at: {patreon_url}"
        lines += [patreon_line, ""]
    cta = _nag_cta_for_reasons(reasons)
    if cta == "staying":
        confirm_label = "I'll be back at rehearsal soon:"
    else:
        confirm_label = "I've updated my Patreon membership:"
    confirm_url = f"{base_url}/instrument-rental/{cta}/?t={token}"
    lines += [
        "Please let us know your plans:",
        "",
        confirm_label,
        confirm_url,
        "",
        "I'd like to return the instrument:",
        f"{base_url}/instrument-rental/return/?t={token}",
        "",
        "Start Wearing Purple,",
        "Blowcomotion",
    ]
    subject = "A note from Blowcomotion about your instrument rental"
    return subject, "\n".join(lines)


def instrument_rental_staying(request):
    from django.core.signing import TimestampSigner
    token = request.GET.get("t", "")
    try:
        signer = TimestampSigner()
        instrument_pk = signer.unsign(token, max_age=30 * 24 * 3600)
        li = LibraryInstrument.objects.select_related("member", "instrument").get(pk=instrument_pk)
    except Exception:
        return render(request, "instrument_rental_token_error.html", status=400)

    site_settings = _get_site_settings_for_view()
    if site_settings and li.member:
        raw = site_settings.instrument_rental_notification_recipients or ""
        recipients = [r.strip() for r in raw.replace("\n", ",").split(",") if r.strip()]
        if recipients:
            _MemberEmail(
                subject=f"Instrument Renter Confirmed: Returning to Rehearsal — {li.member.full_name}",
                body=(
                    f"Renter {li.member.full_name} confirmed they are returning to rehearsal soon.\n\n"
                    f"Instrument: {li.instrument.name}\n"
                    f"Serial: {li.serial_number}\n"
                    f"Member email: {li.member.email}"
                ),
                from_email=settings.FROM_EMAIL,
                to=recipients,
            ).send(fail_silently=True)

    return render(request, "instrument_rental_staying.html", {"instrument": li})


def instrument_rental_patreon_updated(request):
    from django.core.signing import TimestampSigner
    token = request.GET.get("t", "")
    try:
        signer = TimestampSigner()
        instrument_pk = signer.unsign(token, max_age=30 * 24 * 3600)
        li = LibraryInstrument.objects.select_related("member", "instrument").get(pk=instrument_pk)
    except Exception:
        return render(request, "instrument_rental_token_error.html", status=400)

    site_settings = _get_site_settings_for_view()
    if site_settings and li.member:
        raw = site_settings.instrument_rental_notification_recipients or ""
        recipients = [r.strip() for r in raw.replace("\n", ",").split(",") if r.strip()]
        if recipients:
            _MemberEmail(
                subject=f"Instrument Renter Confirmed: Patreon Updated — {li.member.full_name}",
                body=(
                    f"Renter {li.member.full_name} confirmed they have updated their Patreon membership.\n\n"
                    f"Instrument: {li.instrument.name}\n"
                    f"Serial: {li.serial_number}\n"
                    f"Member email: {li.member.email}"
                ),
                from_email=settings.FROM_EMAIL,
                to=recipients,
            ).send(fail_silently=True)

    return render(request, "instrument_rental_patreon_updated.html", {"instrument": li})


def instrument_rental_return(request):
    from django.core.signing import TimestampSigner
    token = request.GET.get("t", "")
    try:
        signer = TimestampSigner()
        instrument_pk = signer.unsign(token, max_age=30 * 24 * 3600)
        li = LibraryInstrument.objects.select_related("member", "instrument").get(pk=instrument_pk)
    except Exception:
        return render(request, "instrument_rental_token_error.html", status=400)

    site_settings = _get_site_settings_for_view()
    if site_settings and li.member:
        raw = site_settings.instrument_rental_notification_recipients or ""
        recipients = [r.strip() for r in raw.replace("\n", ",").split(",") if r.strip()]
        if recipients:
            _MemberEmail(
                subject=f"Instrument Return Request — {li.member.full_name}",
                body=(
                    f"Renter {li.member.full_name} would like to return their instrument — please follow up.\n\n"
                    f"Instrument: {li.instrument.name}\n"
                    f"Serial: {li.serial_number}\n"
                    f"Member email: {li.member.email}\n"
                    f"Member phone: {li.member.phone or 'N/A'}"
                ),
                from_email=settings.FROM_EMAIL,
                to=recipients,
            ).send(fail_silently=True)

    return render(request, "instrument_rental_return.html", {"instrument": li})
