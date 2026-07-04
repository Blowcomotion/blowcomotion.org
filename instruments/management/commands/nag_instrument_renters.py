import datetime
import re

from wagtail.models import Site

from django.conf import settings
from django.core.mail import send_mail
from django.core.management.base import BaseCommand

from blowcomotion.models import InstrumentRentalNagLog, LibraryInstrument, SiteSettings
from instruments.views import _build_nag_email


class Command(BaseCommand):
    help = "Send nag emails to instrument renters who are attendance-inactive or patreon-inactive"

    def add_arguments(self, parser):
        parser.add_argument("--dry-run", action="store_true", help="Print actions without sending emails or writing to DB")
        parser.add_argument(
            "--day-to-run",
            type=int,
            choices=range(7),
            help="Day of week to run (0=Monday, 6=Sunday)",
        )

    def handle(self, *args, **options):
        today = datetime.date.today()
        day_to_run = options["day_to_run"]
        if day_to_run is not None and today.weekday() != day_to_run:
            days = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
            self.stdout.write(self.style.WARNING(f"Intended to run on {days[day_to_run]} only. Exiting."))
            return

        dry_run = options["dry_run"]
        site_settings = self._get_site_settings()
        if not site_settings:
            return

        admin_recipients = self._parse_recipients(site_settings.instrument_rental_notification_recipients)
        if not admin_recipients and not dry_run:
            self.stdout.write(self.style.ERROR("No instrument_rental_notification_recipients configured. Exiting."))
            return

        site = Site.objects.filter(is_default_site=True).first() or Site.objects.first()
        base_url = site.root_url if site else "https://blowcomotion.org"

        patreon_url = site_settings.patreon_url or ""
        cutoff = today - datetime.timedelta(days=site_settings.attendance_cleanup_days)
        cooldown_days = site_settings.nag_cooldown_days

        instruments = LibraryInstrument.objects.filter(
            status=LibraryInstrument.STATUS_RENTED,
            member__isnull=False,
            member__email__isnull=False,
        ).exclude(member__email="").select_related("member", "instrument")

        nagged = []
        skipped_cooldown = 0

        for li in instruments:
            if li.last_nag_sent and (today - li.last_nag_sent).days < cooldown_days:
                skipped_cooldown += 1
                continue

            member = li.member
            reasons = []

            if not member.is_active or not member.last_seen or member.last_seen < cutoff:
                reasons.append("attendance")

            if not li.patreon_active:
                reasons.append("patreon")

            if not reasons:
                continue

            reason_str = "+".join(reasons)
            self._send_renter_nag(li, member, base_url, patreon_url, reasons, dry_run)

            if not dry_run:
                LibraryInstrument.objects.filter(pk=li.pk).update(last_nag_sent=today)
                InstrumentRentalNagLog.objects.create(
                    library_instrument=li,
                    member_name=member.full_name,
                    member_email=member.email,
                    reasons=reason_str,
                    sent_at=today,
                )

            nagged.append({"instrument": li, "member": member, "reasons": reasons})
            self.stdout.write(self.style.SUCCESS(f"Nagged {member.full_name} ({li.instrument.name}) — {reason_str}"))

        if nagged:
            self._send_admin_summary(nagged, skipped_cooldown, admin_recipients, today, dry_run)
        else:
            self.stdout.write(self.style.SUCCESS(f"Nothing to nag today ({skipped_cooldown} skipped by cooldown)."))

    def _send_renter_nag(self, li, member, base_url, patreon_url, reasons, dry_run):
        subject, message = _build_nag_email(li, member, base_url, patreon_url, reasons)
        if dry_run:
            self.stdout.write(self.style.NOTICE(f"[Dry Run] Would email {member.email}:\nSubject: {subject}\n{message}\n"))
        else:
            send_mail(subject, message, settings.FROM_EMAIL, [member.email], fail_silently=False)

    def _send_admin_summary(self, nagged, skipped_cooldown, recipients, today, dry_run):
        lines = [
            f"Instrument Rental Nag Summary — {today}",
            "=" * 50,
            "",
            f"Nag emails sent to {len(nagged)} renter(s):",
            "",
        ]
        for item in nagged:
            member = item["member"]
            reason_label = " + ".join(item["reasons"])
            last_seen_note = f", last seen {member.last_seen}" if member.last_seen and "attendance" in item["reasons"] else ""
            lines.append(f"  * {member.full_name} — {item['instrument'].instrument.name} (Reason: {reason_label}{last_seen_note})")
        lines += ["", f"Skipped (cooldown active): {skipped_cooldown} renter(s)"]
        message = "\n".join(lines)
        subject = f"Instrument Rental Nag Summary — {today}"

        if dry_run:
            self.stdout.write(self.style.NOTICE(f"[Dry Run] Admin summary:\nSubject: {subject}\n{message}"))
            return

        if recipients:
            send_mail(subject, message, settings.FROM_EMAIL, recipients, fail_silently=False)
            extra = getattr(settings, "FORM_TEST_EMAIL", None)
            if extra:
                send_mail(f"[COPY] {subject}", message, settings.FROM_EMAIL, [extra], fail_silently=False)

    def _get_site_settings(self):
        try:
            site = (
                Site.objects.filter(is_default_site=True).select_related("root_page").first()
                or Site.objects.select_related("root_page").first()
            )
            if not site:
                self.stdout.write(self.style.ERROR("No Site configured. Cannot load SiteSettings."))
                return None
            return SiteSettings.for_site(site)
        except Exception as exc:
            self.stdout.write(self.style.ERROR(f"Error retrieving SiteSettings: {exc}"))
            return None

    def _parse_recipients(self, raw):
        if not raw:
            return []
        return [r.strip() for r in re.split(r"[,\n]", raw) if r.strip()]
