import csv
import os

from django.core.management.base import BaseCommand

from blowcomotion.models import Chart


class Command(BaseCommand):
    help = "Export all charts and their fields to a CSV file."

    def add_arguments(self, parser):
        parser.add_argument(
            "--output",
            dest="output_path",
            default="charts_export.csv",
            help="Destination path for the exported CSV (default: ./charts_export.csv)",
        )

    def handle(self, *args, **options):
        output_path = options["output_path"]

        directory = os.path.dirname(os.path.abspath(output_path)) or "."
        os.makedirs(directory, exist_ok=True)

        charts = Chart.objects.all().select_related('song', 'instrument', 'pdf').order_by('song__title', 'instrument__name', 'part')
        if not charts.exists():
            self.stdout.write(self.style.WARNING("No charts found to export."))

        headers = [
            "id",
            "song_id",
            "song_title",
            "instrument_id",
            "instrument_name",
            "part",
            "pdf_id",
            "pdf_title",
        ]

        with open(output_path, "w", newline="", encoding="utf-8") as csvfile:
            writer = csv.writer(csvfile)
            writer.writerow(headers)

            for chart in charts:
                row = [
                    chart.id,
                    chart.song_id,
                    chart.song.title if chart.song else "",
                    chart.instrument_id,
                    chart.instrument.name if chart.instrument else "",
                    chart.part or "",
                    chart.pdf_id,
                    chart.pdf.title if chart.pdf else "",
                ]
                writer.writerow(row)

        self.stdout.write(
            self.style.SUCCESS(
                f"Export complete. {charts.count()} charts written to {output_path}"
            )
        )
