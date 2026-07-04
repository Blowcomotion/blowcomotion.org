from django.core.management.base import BaseCommand
from django.utils import timezone

from blowcomotion.models import (
    InstrumentRentalRequestSubmission,
    LibraryInstrument,
    Member,
)
from instruments.patreon import MIN_RENTAL_PLEDGE_CENTS, fetch_all_members

_SUB_SAVE_FIELDS = [
    "patreon_validated",
    "patreon_pledge_cents",
    "patreon_last_charge_date",
    "patreon_last_charge_status",
    "patreon_patron_since",
    "patreon_lifetime_cents",
]

_MEMBER_SAVE_FIELDS = [
    "patreon_is_active",
    "patreon_pledge_cents",
    "patreon_last_charge_date",
    "patreon_last_charge_status",
    "patreon_patron_since",
    "patreon_lifetime_cents",
    "patreon_last_synced",
]


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
        self.stdout.write("Fetching Patreon member list...")
        all_members = fetch_all_members()

        if all_members is None:
            self.stdout.write(self.style.ERROR("Patreon API not configured or error fetching members."))
            return

        self.stdout.write(f"  {len(all_members)} Patreon members fetched.")
        dry_run = options["dry_run"]
        now = timezone.now()

        # --- update rental submissions ---
        qs = InstrumentRentalRequestSubmission.objects.select_related("member")

        if options["pending_only"]:
            qs = qs.filter(status=InstrumentRentalRequestSubmission.STATUS_PENDING)
        if options["unchecked_only"]:
            qs = qs.filter(patreon_validated__isnull=True)

        updated = skipped = 0

        for sub in qs:
            email = sub.member.email if sub.member else None
            if not email:
                self.stdout.write(self.style.WARNING(f"  #{sub.pk}: no email, skipping"))
                skipped += 1
                continue

            result = all_members.get(email.lower())
            if result is None:
                result = {"is_active": False, "pledge_cents": None, "last_charge_date": None,
                          "last_charge_status": None, "patron_since": None, "lifetime_cents": None}

            label = "ACTIVE" if result["is_active"] else "not active"
            self.stdout.write(f"  #{sub.pk} ({email}): {label}")

            if not dry_run:
                sub.patreon_validated = result["is_active"]
                sub.patreon_pledge_cents = result["pledge_cents"]
                sub.patreon_last_charge_date = result["last_charge_date"]
                sub.patreon_last_charge_status = result["last_charge_status"]
                sub.patreon_patron_since = result["patron_since"]
                sub.patreon_lifetime_cents = result["lifetime_cents"]
                sub.save(update_fields=_SUB_SAVE_FIELDS)

            updated += 1

        # --- update Member cache for every member with an email in the Patreon list ---
        member_updated = 0
        for member in Member.objects.exclude(email="").only("pk", "email", *_MEMBER_SAVE_FIELDS):
            result = all_members.get(member.email.lower())
            if result is None:
                continue  # only update members we found; leave unknown ones untouched

            if not dry_run:
                member.patreon_is_active = result["is_active"]
                member.patreon_pledge_cents = result["pledge_cents"]
                member.patreon_last_charge_date = result["last_charge_date"]
                member.patreon_last_charge_status = result["last_charge_status"]
                member.patreon_patron_since = result["patron_since"]
                member.patreon_lifetime_cents = result["lifetime_cents"]
                member.patreon_last_synced = now
                member.save(update_fields=_MEMBER_SAVE_FIELDS)
            member_updated += 1

        # --- sync LibraryInstrument.patreon_active from Member cache ---
        instrument_updated = 0
        for li in LibraryInstrument.objects.select_related("current_borrower__member"):
            borrower = getattr(li, "current_borrower", None)
            member = getattr(borrower, "member", None) if borrower else None
            if not member:
                continue

            result = all_members.get((member.email or "").lower())
            if result is None:
                continue

            new_active = (
                result["is_active"]
                and (result["pledge_cents"] or 0) >= MIN_RENTAL_PLEDGE_CENTS
            )
            if li.patreon_active != new_active:
                self.stdout.write(f"  instrument #{li.pk}: patreon_active {li.patreon_active} → {new_active}")
                if not dry_run:
                    li.patreon_active = new_active
                    li.save(update_fields=["patreon_active"])
                instrument_updated += 1

        suffix = " (dry run)" if dry_run else ""
        self.stdout.write(self.style.SUCCESS(
            f"Done{suffix}: {updated} submissions updated, {skipped} skipped, "
            f"{member_updated} members cached, {instrument_updated} instruments synced"
        ))
