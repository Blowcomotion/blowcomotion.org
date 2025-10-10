import csv
import os
from datetime import date, datetime

from django.core.management.base import BaseCommand

from blowcomotion.models import Member


class Command(BaseCommand):
    help = "Export all members and their fields to a CSV file."

    def add_arguments(self, parser):
        parser.add_argument(
            "--output",
            dest="output_path",
            default="members_export.csv",
            help="Destination path for the exported CSV (default: ./members_export.csv)",
        )
        parser.add_argument(
            "--include-extra",
            action="store_true",
            help="Include human-readable helper columns such as primary instrument name and additional instruments.",
        )

    def handle(self, *args, **options):
        output_path = options["output_path"]
        include_extra = options["include_extra"]

        directory = os.path.dirname(os.path.abspath(output_path)) or "."
        os.makedirs(directory, exist_ok=True)

        members = Member.objects.all().order_by("last_name", "first_name", "id")
        if not members.exists():
            self.stdout.write(self.style.WARNING("No members found to export."))

        fields = Member._meta.concrete_fields
        field_names = [field.attname for field in fields]

        extra_headers = []
        if include_extra:
            extra_headers.extend([
                "primary_instrument_name",
                "additional_instruments",
            ])

        with open(output_path, "w", newline="", encoding="utf-8") as csvfile:
            writer = csv.writer(csvfile)
            writer.writerow(field_names + extra_headers)

            for member in members:
                row = [self._serialize(getattr(member, field.attname)) for field in fields]

                if include_extra:
                    primary_instrument_name = (
                        member.primary_instrument.name if member.primary_instrument else ""
                    )
                    additional_instruments = "; ".join(
                        instrument.instrument.name
                        for instrument in member.additional_instruments.all()
                    )
                    row.extend([
                        primary_instrument_name,
                        additional_instruments,
                    ])

                writer.writerow(row)

        self.stdout.write(
            self.style.SUCCESS(
                f"Export complete. {members.count()} members written to {output_path}"
            )
        )

    def _serialize(self, value):
        if value is None:
            return ""
        if isinstance(value, bool):
            return "YES" if value else "NO"
        if isinstance(value, (datetime, date)):
            return value.isoformat()
        return str(value)
