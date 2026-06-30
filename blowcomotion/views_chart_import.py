import json
import logging
from datetime import datetime

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Max
from django.http import HttpResponseForbidden
from django.shortcuts import redirect, render
from django.utils import timezone

from blowcomotion.drive_sync import (
    _KEY_INSTRUMENT_MAP,
    ARCHIVE_FOLDERS,
    EXCLUDE_FOLDERS,
    list_pdfs_in_folder,
    list_song_folders,
    match_song,
    reconcile_file,
    resolve_drive_file,
)
from blowcomotion.models import Chart, Instrument, Song

logger = logging.getLogger(__name__)


def _admin_required(request):
    return request.user.is_active and request.user.has_perm("wagtailadmin.access_admin")


@login_required
def picker(request):
    if not _admin_required(request):
        return HttpResponseForbidden()

    folder_id = getattr(settings, "GDRIVE_CHARTS_FOLDER_ID", None)
    songs = list(Song.objects.all())
    folders = []

    if folder_id:
        last_imported_by_song = {
            row["song_id"]: row["last_imported"]
            for row in Chart.objects.values("song_id").annotate(last_imported=Max("drive_imported_at"))
        }
        raw = list_song_folders(folder_id)
        for f in raw:
            name = f["name"]
            if any(name.startswith(ex) for ex in EXCLUDE_FOLDERS):
                continue
            archived = any(name.startswith(ar) for ar in ARCHIVE_FOLDERS)
            matched_song, score = match_song(name, songs)
            if score < 0.6:
                matched_song = None
            last_imported = last_imported_by_song.get(matched_song.id) if matched_song else None
            folders.append({
                "id": f["id"],
                "name": name,
                "matched_song": matched_song,
                "match_score": score,
                "match_pct": round(score * 100),
                "archived": archived,
                "last_imported": last_imported,
            })

    return render(request, "chart_import/picker.html", {
        "folders": folders,
        "songs": songs,
    })


@login_required
def review(request):
    if not _admin_required(request):
        return HttpResponseForbidden()

    instruments = list(Instrument.objects.order_by("name"))

    if request.method == "POST":
        song_id = request.POST.get("song_id")
        folder_name = request.POST.get("folder_name", "").strip()
        if song_id == "new":
            song = Song.objects.create(title=folder_name)
        elif song_id:
            song = Song.objects.get(id=song_id)
        else:
            messages.error(request, "Please select a song.")
            return redirect("chart_import_picker")
        selected_rows = request.POST.getlist("rows")

        for idx in selected_rows:
            file_id = request.POST.get(f"row_{idx}_file_id")
            filename = request.POST.get(f"row_{idx}_filename")
            modified_str = request.POST.get(f"row_{idx}_modified")
            instrument_id = request.POST.get(f"row_{idx}_instrument_id")
            part = request.POST.get(f"row_{idx}_part", "")
            chart_id = request.POST.get(f"row_{idx}_chart_id")
            is_key = request.POST.get(f"row_{idx}_is_key") == "1"
            drive_pdf_url = f"https://drive.google.com/file/d/{file_id}/view"

            try:
                drive_time = datetime.fromisoformat(modified_str.replace("Z", "+00:00"))

                now = timezone.now()
                if is_key:
                    instrument_ids = request.POST.getlist(f"row_{idx}_instrument_ids")
                    for inst_id in instrument_ids:
                        Chart.objects.create(
                            song=song,
                            instrument=Instrument.objects.get(id=inst_id),
                            part="",
                            drive_pdf_url=drive_pdf_url,
                            drive_file_id=file_id,
                            drive_modified_time=drive_time,
                            drive_imported_at=now,
                        )
                elif chart_id:
                    chart = Chart.objects.get(id=chart_id)
                    chart.drive_pdf_url = drive_pdf_url
                    chart.drive_file_id = file_id
                    chart.drive_modified_time = drive_time
                    chart.drive_imported_at = now
                    chart.save()
                else:
                    # ponytail: if an existing chart has a non-conforming part string it won't match
                    # the tuple filter and will appear as "New" here — creating a duplicate. Run a
                    # data migration to normalize part strings before first sync if needed.
                    Chart.objects.create(
                        song=song,
                        instrument=Instrument.objects.get(id=instrument_id),
                        part=part,
                        drive_pdf_url=drive_pdf_url,
                        drive_file_id=file_id,
                        drive_modified_time=drive_time,
                        drive_imported_at=now,
                    )
            except Exception as e:
                logger.error("Failed to import %s: %s", filename, e)
                messages.error(request, f"Failed to import {filename}: {e}")

        messages.success(request, f"Import complete for {song.title}.")
        return redirect("chart_import_picker")

    # GET
    folder_id = request.GET.get("folder_id")
    folder_name = request.GET.get("folder_name", "")
    song_id = request.GET.get("song_id")
    try:
        song = Song.objects.get(id=song_id) if song_id else None
    except Song.DoesNotExist:
        song = None

    drive_files = list_pdfs_in_folder(folder_id) if folder_id else []
    existing_charts = (
        list(Chart.objects.filter(song=song).select_related("instrument", "pdf"))
        if song else []
    )

    rows = []
    for drive_file in drive_files:
        resolved = resolve_drive_file(drive_file, instruments)
        matched_inst = resolved.matched_inst
        inst_conf = resolved.inst_conf
        part = resolved.part
        parsed = resolved.parsed

        key_instrument_ids = set()
        key_instrument_names = []
        if parsed.is_key:
            default_names = _KEY_INSTRUMENT_MAP.get(parsed.instrument_hint.lower(), [])
            name_set = {n.lower() for n in default_names}
            for inst in instruments:
                if inst.name.lower() in name_set:
                    key_instrument_ids.add(inst.id)
                    key_instrument_names.append(inst.name)

        tuple_charts = [
            c for c in existing_charts
            if matched_inst and c.instrument_id == matched_inst.id and (c.part or "") == part
        ]
        result = reconcile_file(drive_file, parsed, tuple_charts)

        rows.append({
            "drive_file": drive_file,
            "parsed": parsed,
            "instrument": matched_inst,
            "inst_conf": inst_conf,
            "part": part,
            "reconcile": result,
            "existing_chart": result.existing_chart,
            "key_instrument_ids": key_instrument_ids,
            "key_instrument_names": key_instrument_names,
        })

    return render(request, "chart_import/review.html", {
        "song": song,
        "songs": list(Song.objects.order_by("title")),
        "folder_id": folder_id,
        "folder_name": folder_name,
        "rows": rows,
        "instruments": instruments,
        "instruments_json": json.dumps([{"id": i.id, "name": i.name} for i in instruments]),
    })
