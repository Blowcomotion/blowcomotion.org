import csv
import os
from datetime import date, datetime

from django.core.management.base import BaseCommand

from blowcomotion.models import Instrument


class Command(BaseCommand):
    help = "Export all instruments and their fields to a CSV file."

    def add_arguments(self, parser):
        parser.add_argument(
            "--output",
            dest="output_path",
            default="instruments_export.csv",
            help="Destination path for the exported CSV (default: ./instruments_export.csv)",
        )
        parser.add_argument(
            "--include-extra",
            action="store_true",
            help="Include human-readable helper columns such as section name.",
        )

    def handle(self, *args, **options):
        output_path = options["output_path"]
        include_extra = options["include_extra"]

        directory = os.path.dirname(os.path.abspath(output_path)) or "."
        os.makedirs(directory, exist_ok=True)

        instruments = Instrument.objects.select_related("section", "image").order_by("section__name", "name")
        
        if not instruments.exists():
            self.stdout.write(self.style.WARNING("No instruments found to export."))
            return

        fields = Instrument._meta.concrete_fields
        field_names = [field.attname for field in fields]

        extra_headers = []
        if include_extra:
            extra_headers.extend([
                "section_name",
                "image_title",
            ])

        with open(output_path, "w", newline="", encoding="utf-8") as csvfile:
            writer = csv.writer(csvfile)
            writer.writerow(field_names + extra_headers)

            for instrument in instruments:
                row = [self._serialize(getattr(instrument, field.attname)) for field in fields]

                if include_extra:
                    section_name = instrument.section.name if instrument.section else ""
                    image_title = instrument.image.title if instrument.image else ""
                    
                    row.extend([
                        section_name,
                        image_title,
                    ])

                writer.writerow(row)

        self.stdout.write(
            self.style.SUCCESS(
                f"Export complete. {instruments.count()} instruments written to {output_path}"
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
