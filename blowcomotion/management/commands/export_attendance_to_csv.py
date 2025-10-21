import csv
import os
from datetime import date, datetime

from django.core.management.base import BaseCommand, CommandError

from blowcomotion.models import AttendanceRecord


class Command(BaseCommand):
    help = "Export attendance records to a CSV file."

    def add_arguments(self, parser):
        parser.add_argument(
            "--output",
            dest="output_path",
            default="attendance_export.csv",
            help="Destination path for the exported CSV (default: ./attendance_export.csv)",
        )
        parser.add_argument(
            "--start-date",
            dest="start_date",
            help="Filter attendance records on or after this date (YYYY-MM-DD)",
        )
        parser.add_argument(
            "--end-date",
            dest="end_date",
            help="Filter attendance records on or before this date (YYYY-MM-DD)",
        )

    def handle(self, *args, **options):
        output_path = options["output_path"]
        start_date = self._parse_date(options.get("start_date")) if options.get("start_date") else None
        end_date = self._parse_date(options.get("end_date")) if options.get("end_date") else None

        directory = os.path.dirname(os.path.abspath(output_path)) or "."
        os.makedirs(directory, exist_ok=True)

        queryset = AttendanceRecord.objects.all().select_related(
            "member",
            "member__primary_instrument",
            "member__primary_instrument__section",
        ).order_by("date", "member__last_name", "member__first_name", "guest_name")

        if start_date:
            queryset = queryset.filter(date__gte=start_date)
        if end_date:
            queryset = queryset.filter(date__lte=end_date)

        headers = [
            "date",
            "member_id",
            "member_first_name",
            "member_last_name",
            "member_preferred_name",
            "member_gigomatic_username",
            "member_email",
            "member_phone",
            "member_is_active",
            "member_primary_instrument",
            "member_section",
            "guest_name",
            "notes",
            "created_at",
        ]

        record_count = queryset.count()
        if record_count == 0:
            self.stdout.write(self.style.WARNING("No attendance records found for the provided filters."))

        with open(output_path, "w", newline="", encoding="utf-8") as csvfile:
            writer = csv.writer(csvfile)
            writer.writerow(headers)

            for record in queryset.iterator(chunk_size=1000):
                member = record.member
                primary_instrument = getattr(member, "primary_instrument", None) if member else None
                section = getattr(primary_instrument, "section", None) if primary_instrument else None

                row = [
                    record.date.isoformat() if record.date else "",
                    member.id if member else "",
                    member.first_name if member else "",
                    member.last_name if member else "",
                    member.preferred_name if member else "",
                    member.gigomatic_username if member else "",
                    member.email if member else "",
                    member.phone if member else "",
                    "YES" if (member and member.is_active) else ("NO" if member else ""),
                    primary_instrument.name if primary_instrument else "",
                    section.name if section else "",
                    record.guest_name or "",
                    record.notes or "",
                    record.created_at.isoformat() if record.created_at else "",
                ]
                writer.writerow(row)

        summary = f"Export complete. {record_count} attendance records written to {output_path}"
        if start_date or end_date:
            summary += " ("
            summary += f"start_date={start_date.isoformat() if start_date else 'min'}"
            summary += ", "
            summary += f"end_date={end_date.isoformat() if end_date else 'max'}"
            summary += ")"
        self.stdout.write(self.style.SUCCESS(summary))

    def _parse_date(self, value):
        try:
            return datetime.strptime(value, "%Y-%m-%d").date()
        except ValueError as exc:
            raise CommandError(
                f"Invalid date '{value}'. Expected format is YYYY-MM-DD."
            ) from exc
