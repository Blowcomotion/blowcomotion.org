from django.core.management.base import BaseCommand

from blowcomotion.models import InstrumentRentalRequestSubmission
from blowcomotion.patreon_client import check_patreon_membership

_SAVE_FIELDS = ["patreon_validated", "patreon_pledge_cents", "patreon_last_charge_date", "patreon_last_charge_status", "patreon_patron_since", "patreon_lifetime_cents"]


class Command(BaseCommand):
    help = "Check rental requests against Patreon and update patreon detail fields"

    def add_arguments(self, parser):
        parser.add_argument(
            "--pending-only",
            action="store_true",
            help="Only check pending requests (default checks all statuses)",
        )
        parser.add_argument(
            "--unchecked-only",
            action="store_true",
            help="Only check requests where patreon_validated is None",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Print what would change without saving",
        )

    def handle(self, *args, **options):
        qs = InstrumentRentalRequestSubmission.objects.select_related("member")

        if options["pending_only"]:
            qs = qs.filter(status=InstrumentRentalRequestSubmission.STATUS_PENDING)

        if options["unchecked_only"]:
            qs = qs.filter(patreon_validated__isnull=True)

        if not qs.exists():
            self.stdout.write("No matching requests to check.")
            return

        updated = skipped = errors = 0

        for sub in qs:
            email = sub.member.email if sub.member else None
            if not email:
                self.stdout.write(self.style.WARNING(f"  #{sub.pk}: no email, skipping"))
                skipped += 1
                continue

            result = check_patreon_membership(email)

            if result is None:
                self.stdout.write(self.style.ERROR(f"  #{sub.pk} ({email}): API error or not configured"))
                errors += 1
                continue

            label = "ACTIVE" if result["is_active"] else "not active"
            self.stdout.write(f"  #{sub.pk} ({email}): {label}")

            if not options["dry_run"]:
                sub.patreon_validated = result["is_active"]
                sub.patreon_pledge_cents = result["pledge_cents"]
                sub.patreon_last_charge_date = result["last_charge_date"]
                sub.patreon_last_charge_status = result["last_charge_status"]
                sub.patreon_patron_since = result["patron_since"]
                sub.patreon_lifetime_cents = result["lifetime_cents"]
                sub.save(update_fields=_SAVE_FIELDS)

            updated += 1

        suffix = " (dry run)" if options["dry_run"] else ""
        self.stdout.write(
            self.style.SUCCESS(
                f"Done{suffix}: {updated} updated, {skipped} skipped, {errors} errors"
            )
        )
