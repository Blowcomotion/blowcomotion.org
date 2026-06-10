import csv
import os

from django.core.management.base import BaseCommand

from blowcomotion.models import LibraryInstrument


class Command(BaseCommand):
    help = "Export all library instruments and their fields to a CSV file."

    def add_arguments(self, parser):
        parser.add_argument(
            "--output",
            dest="output_path",
            default="library_instruments_export.csv",
            help="Destination path for the exported CSV (default: ./library_instruments_export.csv)",
        )

    def handle(self, *args, **options):
        output_path = options["output_path"]

        directory = os.path.dirname(os.path.abspath(output_path)) or "."
        os.makedirs(directory, exist_ok=True)

        instruments = LibraryInstrument.objects.all().select_related(
            'instrument', 'member', 'storage_location'
        ).order_by('instrument__name', 'serial_number')
        
        if not instruments.exists():
            self.stdout.write(self.style.WARNING("No library instruments found to export."))

        headers = [
            "id",
            "instrument_id",
            "instrument_name",
            "status",
            "status_display",
            "serial_number",
            "member_id",
            "member_name",
            "rental_date",
            "agreement_signed_date",
            "acquisition_cost",
            "current_value",
            "replacement_cost",
            "patreon_active",
            "patreon_amount",
            "storage_location_id",
            "storage_location_name",
            "comments",
            "created_at",
            "updated_at",
        ]

        with open(output_path, "w", newline="", encoding="utf-8") as csvfile:
            writer = csv.writer(csvfile)
            writer.writerow(headers)

            row_count = 0
            for instrument in instruments:
                row = [
                    instrument.id,
                    instrument.instrument_id,
                    instrument.instrument.name if instrument.instrument else "",
                    instrument.status,
                    instrument.get_status_display(),
                    instrument.serial_number or "",
                    instrument.member_id if instrument.member_id else "",
                    instrument.member.full_name if instrument.member else "",
                    instrument.rental_date.isoformat() if instrument.rental_date else "",
                    instrument.agreement_signed_date.isoformat() if instrument.agreement_signed_date else "",
                    str(instrument.acquisition_cost) if instrument.acquisition_cost is not None else "",
                    str(instrument.current_value) if instrument.current_value is not None else "",
                    str(instrument.replacement_cost) if instrument.replacement_cost is not None else "",
                    "YES" if instrument.patreon_active else "NO",
                    str(instrument.patreon_amount) if instrument.patreon_amount is not None else "",
                    instrument.storage_location_id if instrument.storage_location_id else "",
                    instrument.storage_location.name if instrument.storage_location else "",
                    instrument.comments or "",
                    instrument.created_at.isoformat() if instrument.created_at else "",
                    instrument.updated_at.isoformat() if instrument.updated_at else "",
                ]
                writer.writerow(row)
                row_count += 1

        self.stdout.write(
            self.style.SUCCESS(
                f"Export complete. {row_count} library instruments written to {output_path}"
            )
        )
