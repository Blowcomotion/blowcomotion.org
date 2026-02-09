import csv
import os
from datetime import date, datetime

from django.core.management.base import BaseCommand

from blowcomotion.models import LibraryInstrument


class Command(BaseCommand):
    help = "Export all rented instruments and their fields to a CSV file."

    def add_arguments(self, parser):
        parser.add_argument(
            "--output",
            dest="output_path",
            default="rented_instruments_export.csv",
            help="Destination path for the exported CSV (default: ./rented_instruments_export.csv)",
        )
        parser.add_argument(
            "--include-extra",
            action="store_true",
            help="Include human-readable helper columns such as instrument name, member name, and review status.",
        )

    def handle(self, *args, **options):
        output_path = options["output_path"]
        include_extra = options["include_extra"]

        directory = os.path.dirname(os.path.abspath(output_path)) or "."
        os.makedirs(directory, exist_ok=True)

        rented_instruments = LibraryInstrument.objects.filter(
            status=LibraryInstrument.STATUS_RENTED
        ).select_related("instrument", "member").order_by("instrument__name", "serial_number")
        
        if not rented_instruments.exists():
            self.stdout.write(self.style.WARNING("No rented instruments found to export."))
            return

        fields = LibraryInstrument._meta.concrete_fields
        field_names = [field.attname for field in fields]

        extra_headers = []
        if include_extra:
            extra_headers.extend([
                "instrument_name",
                "member_full_name",
                "member_email",
                "member_phone",
                "needs_review",
                "renter_inactive",
            ])

        with open(output_path, "w", newline="", encoding="utf-8") as csvfile:
            writer = csv.writer(csvfile)
            writer.writerow(field_names + extra_headers)

            for lib_instrument in rented_instruments:
                row = [self._serialize(getattr(lib_instrument, field.attname)) for field in fields]

                if include_extra:
                    instrument_name = lib_instrument.instrument_name
                    member_full_name = (
                        lib_instrument.member.full_name if lib_instrument.member else ""
                    )
                    member_email = (
                        lib_instrument.member.email if lib_instrument.member else ""
                    )
                    member_phone = (
                        lib_instrument.member.phone if lib_instrument.member else ""
                    )
                    needs_review = "YES" if lib_instrument.needs_review else "NO"
                    renter_inactive = "YES" if lib_instrument.renter_inactive else "NO"
                    
                    row.extend([
                        instrument_name,
                        member_full_name,
                        member_email,
                        member_phone,
                        needs_review,
                        renter_inactive,
                    ])

                writer.writerow(row)

        self.stdout.write(
            self.style.SUCCESS(
                f"Export complete. {rented_instruments.count()} rented instruments written to {output_path}"
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
