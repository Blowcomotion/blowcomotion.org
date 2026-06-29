import logging
from datetime import datetime

from wagtail.documents import get_document_model

from django.conf import settings
from django.core.files.base import ContentFile
from django.core.management.base import BaseCommand

from blowcomotion.drive_sync import (
    _download_pdf,
    _get_drive_service,
    _safe_delete_document,
    list_pdfs_in_folder,
    match_instrument,
    parse_filename,
    reconcile_file,
)
from blowcomotion.models import Chart, Instrument

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Auto-refresh charts from Google Drive (Exact and High confidence only)"

    def add_arguments(self, parser):
        parser.add_argument("--dry-run", action="store_true")
        parser.add_argument("--song-id", type=int)

    def handle(self, *args, **options):
        dry_run = options["dry_run"]
        song_id = options.get("song_id")

        if not getattr(settings, "GDRIVE_CHARTS_FOLDER_ID", None):
            self.stderr.write("GDRIVE_CHARTS_FOLDER_ID not configured in local.py")
            raise SystemExit(1)

        Document = get_document_model()
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
                meta = service.files().get(fileId=first_file_id, fields="parents").execute()
                parents = meta.get("parents", [])
                if not parents:
                    logger.warning("No parent folder found for %s", song.title)
                    continue
                drive_files = list_pdfs_in_folder(parents[0])
            except Exception as e:
                self.stderr.write(f"Drive error for {song.title}: {e}")
                raise SystemExit(1)

            for drive_file in drive_files:
                parsed = parse_filename(drive_file["name"])
                hint = "Conductor" if parsed.is_score else parsed.instrument_hint
                matched_inst, _ = match_instrument(hint, instruments) if hint else (None, "low")

                tuple_charts = [
                    c for c in song_charts
                    if matched_inst and c.instrument_id == matched_inst.id
                ]
                result = reconcile_file(drive_file, parsed, tuple_charts)

                if result.apply == "review":
                    review_needed += 1
                    logger.info("Needs review: %s (%s)", drive_file["name"], result.reason)
                    continue

                if result.apply == "noop":
                    continue

                if dry_run:
                    self.stdout.write(f"[dry-run] would update: {drive_file['name']} ({result.reason})")
                    continue

                try:
                    content = _download_pdf(drive_file["id"])
                    doc = Document(title=drive_file["name"])
                    doc.file.save(drive_file["name"], ContentFile(content), save=True)
                    chart = result.existing_chart
                    old_doc = chart.pdf
                    chart.pdf = doc
                    chart.drive_file_id = drive_file["id"]
                    chart.drive_modified_time = datetime.fromisoformat(
                        drive_file["modifiedTime"].replace("Z", "+00:00")
                    )
                    chart.save()
                    if old_doc:
                        _safe_delete_document(old_doc)
                    self.stdout.write(f"Updated: {drive_file['name']} ({result.reason})")
                except Exception as e:
                    logger.error("Failed to update %s: %s", drive_file["name"], e)

        if review_needed:
            self.stdout.write(
                f"{review_needed} chart(s) need manual review — use 'Import Charts from Drive' in the admin."
            )
