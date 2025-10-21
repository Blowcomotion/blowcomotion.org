from django.core.management.base import BaseCommand
from django.db import transaction
from django.db.models import Prefetch

from blowcomotion.models import Member, MemberInstrument


class Command(BaseCommand):
    help = (
        "Promote the first additional instrument for each member to their primary instrument "
        "and remove the migrated additional instrument relationship."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Preview the changes without modifying the database.",
        )

    def handle(self, *args, **options):
        dry_run = options["dry_run"]

        members = (
            Member.objects.select_related("primary_instrument")
            .prefetch_related(
                Prefetch(
                    "additional_instruments",
                    queryset=MemberInstrument.objects.select_related("instrument").order_by(
                        "sort_order", "id"
                    ),
                )
            )
        )

        total_members = members.count()
        migrated_members = 0
        skipped_members = 0
        removed_relations = 0

        if dry_run:
            self.stdout.write(self.style.WARNING("Running in dry-run mode; no changes will be saved."))

        for member in members:
            additional_instruments = list(member.additional_instruments.all())

            if not additional_instruments:
                continue

            first_additional = next(
                (instrument for instrument in additional_instruments if instrument.instrument_id),
                None,
            )

            if not first_additional:
                continue

            member_name = self._member_name(member)

            if member.primary_instrument_id:
                skipped_members += 1
                self.stdout.write(
                    f"Skipping member {member.id} ({member_name}): already has primary instrument "
                    f"{member.primary_instrument.name}."
                )
                continue

            self.stdout.write(
                f"Migrating member {member.id} ({member_name}): primary instrument -> "
                f"{first_additional.instrument.name}"
            )

            if dry_run:
                migrated_members += 1
                removed_relations += 1
                continue

            with transaction.atomic():
                member.primary_instrument = first_additional.instrument
                member.save(update_fields=["primary_instrument"])
                first_additional.delete()

            migrated_members += 1
            removed_relations += 1

        summary = (
            "Processed {total} members. {migrated} migrated, {skipped} skipped, "
            "{removed} additional instrument relations removed."
        ).format(
            total=total_members,
            migrated=migrated_members,
            skipped=skipped_members,
            removed=removed_relations,
        )

        if dry_run:
            self.stdout.write(summary)
        else:
            self.stdout.write(self.style.SUCCESS(summary))

    @staticmethod
    def _member_name(member):
        preferred = getattr(member, "preferred_name", None)
        if preferred:
            return preferred
        parts = [member.first_name, member.last_name]
        return " ".join(part for part in parts if part)
