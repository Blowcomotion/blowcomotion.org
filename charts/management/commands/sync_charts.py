import logging
from datetime import datetime

from django.conf import settings
from django.core.management.base import BaseCommand

from blowcomotion.models import Chart, Instrument
from charts.drive_sync import (
    _get_drive_service,
    list_pdfs_in_folder,
    reconcile_file,
    resolve_drive_file,
)

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Auto-refresh charts from Google Drive (Exact and High confidence only)"

    def add_arguments(self, parser):
        parser.add_argument("--dry-run", action="store_true")
        parser.add_argument("--song-id", type=int)

    def handle(self, *args, **options):
        dry_run = options["dry_run"]
        song_id = options.get("song_id")

        if not getattr(settings, "GDRIVE_API_KEY", None):
            self.stderr.write("GDRIVE_API_KEY not configured in local.py")
            raise SystemExit(1)
        if not getattr(settings, "GDRIVE_CHARTS_FOLDER_ID", None):
            self.stderr.write("GDRIVE_CHARTS_FOLDER_ID not configured in local.py")
            raise SystemExit(1)

        instruments = list(Instrument.objects.all())
        charts_qs = Chart.objects.exclude(drive_file_id=None).select_related("song", "instrument", "pdf")
        if song_id:
            charts_qs = charts_qs.filter(song_id=song_id)

        songs_map = {}
        for chart in charts_qs:
            songs_map.setdefault(chart.song_id, (chart.song, []))
            songs_map[chart.song_id][1].append(chart)

        review_needed = 0
        service = _get_drive_service()

        for song_id_key, (song, song_charts) in songs_map.items():
            first_file_id = next((c.drive_file_id for c in song_charts if c.drive_file_id), None)
            if not first_file_id:
                continue

            try:
                meta = service.files().get(fileId=first_file_id, fields="parents", supportsAllDrives=True).execute()
                parents = meta.get("parents", [])
                if not parents:
                    logger.warning("No parent folder found for %s", song.title)
                    continue
                drive_files = list_pdfs_in_folder(parents[0])
            except Exception as e:
                self.stderr.write(f"Drive error for {song.title}: {e}")
                raise SystemExit(1)

            # Pre-group drive files by their resolved (inst_id_or_None, part, is_conductor) tuple.
            # If multiple files map to the same tuple, flag all as review-needed.
            tuple_map = {}
            for drive_file in drive_files:
                resolved = resolve_drive_file(drive_file, instruments)
                matched_inst = resolved.matched_inst
                part = resolved.part
                key = (matched_inst.id if matched_inst else None, part, resolved.is_conductor_chart)
                tuple_map.setdefault(key, []).append((drive_file, resolved.parsed, matched_inst, part, resolved.is_conductor_chart))

            for key, file_entries in tuple_map.items():
                if len(file_entries) > 1:
                    for drive_file, parsed, matched_inst, part, is_conductor_chart in file_entries:
                        review_needed += 1
                        logger.info(
                            "Multiple drive files map to same tuple %s — needs review: %s",
                            key,
                            drive_file["name"],
                        )
                    continue

                drive_file, parsed, matched_inst, part, is_conductor_chart = file_entries[0]
                if is_conductor_chart:
                    tuple_charts = [c for c in song_charts if c.is_conductor_chart]
                else:
                    tuple_charts = [
                        c for c in song_charts
                        if matched_inst and c.instrument_id == matched_inst.id and (c.part or "") == part
                    ]
                result = reconcile_file(drive_file, parsed, tuple_charts)

                if result.apply == "review":
                    # ponytail: charts with non-conforming part strings won't match the tuple
                    # filter and will appear as "New" here — creating a duplicate on the manual
                    # path. Normalize part strings via data migration before first sync if needed.
                    review_needed += 1
                    logger.info("Needs review: %s (%s)", drive_file["name"], result.reason)
                    continue

                if result.apply == "noop":
                    continue

                if dry_run:
                    self.stdout.write(f"[dry-run] would update: {drive_file['name']} ({result.reason})")
                    continue

                try:
                    chart = result.existing_chart
                    chart.drive_pdf_url = f"https://drive.google.com/file/d/{drive_file['id']}/view"
                    chart.drive_file_id = drive_file["id"]
                    chart.drive_modified_time = datetime.fromisoformat(
                        drive_file["modifiedTime"].replace("Z", "+00:00")
                    )
                    chart.save()
                    self.stdout.write(f"Updated: {drive_file['name']} ({result.reason})")
                except Exception as e:
                    logger.error("Failed to update %s: %s", drive_file["name"], e)

        if review_needed:
            self.stdout.write(
                f"{review_needed} chart(s) need manual review — use 'Import Charts from Drive' in the admin."
            )
