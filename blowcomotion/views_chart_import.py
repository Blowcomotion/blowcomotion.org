import logging
from datetime import datetime

from wagtail.documents import get_document_model

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.files.base import ContentFile
from django.http import HttpResponseForbidden
from django.shortcuts import redirect, render

from blowcomotion.drive_sync import (
    ARCHIVE_FOLDERS,
    EXCLUDE_FOLDERS,
    _download_pdf,
    _safe_delete_document,
    list_pdfs_in_folder,
    list_song_folders,
    match_instrument,
    match_song,
    parse_filename,
    reconcile_file,
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
        raw = list_song_folders(folder_id)
        for f in raw:
            name = f["name"]
            if any(name.startswith(ex) for ex in EXCLUDE_FOLDERS):
                continue
            archived = any(name.startswith(ar) for ar in ARCHIVE_FOLDERS)
            matched_song, score = match_song(name, songs)
            folders.append({
                "id": f["id"],
                "name": name,
                "matched_song": matched_song,
                "match_score": round(score, 2),
                "archived": archived,
            })

    return render(request, "chart_import/picker.html", {
        "folders": folders,
        "songs": songs,
    })


@login_required
def review(request):
    if not _admin_required(request):
        return HttpResponseForbidden()

    Document = get_document_model()
    instruments = list(Instrument.objects.all())

    if request.method == "POST":
        song_id = request.POST.get("song_id")
        if not song_id:
            messages.error(request, "Please select a song.")
            return redirect(request.get_full_path())
        song = Song.objects.get(id=song_id)
        selected_rows = request.POST.getlist("rows")

        for idx in selected_rows:
            file_id = request.POST.get(f"row_{idx}_file_id")
            filename = request.POST.get(f"row_{idx}_filename")
            modified_str = request.POST.get(f"row_{idx}_modified")
            instrument_id = request.POST.get(f"row_{idx}_instrument_id")
            part = request.POST.get(f"row_{idx}_part", "")
            chart_id = request.POST.get(f"row_{idx}_chart_id")

            try:
                content = _download_pdf(file_id)
                doc = Document(title=filename)
                doc.file.save(filename, ContentFile(content), save=True)
                drive_time = datetime.fromisoformat(modified_str.replace("Z", "+00:00"))

                if chart_id:
                    chart = Chart.objects.get(id=chart_id)
                    old_doc = chart.pdf
                    chart.pdf = doc
                    chart.drive_file_id = file_id
                    chart.drive_modified_time = drive_time
                    chart.save()
                    if old_doc:
                        _safe_delete_document(old_doc)
                else:
                    Chart.objects.create(
                        song=song,
                        instrument=Instrument.objects.get(id=instrument_id),
                        part=part,
                        pdf=doc,
                        drive_file_id=file_id,
                        drive_modified_time=drive_time,
                    )
            except Exception as e:
                logger.error("Failed to import %s: %s", filename, e)
                messages.error(request, f"Failed to import {filename}: {e}")

        messages.success(request, "Import complete.")
        return redirect("chart_import_picker")

    # GET
    folder_id = request.GET.get("folder_id")
    folder_name = request.GET.get("folder_name", "")
    song_id = request.GET.get("song_id")
    song = Song.objects.get(id=song_id) if song_id else None

    drive_files = list_pdfs_in_folder(folder_id) if folder_id else []
    existing_charts = (
        list(Chart.objects.filter(song=song).select_related("instrument", "pdf"))
        if song else []
    )

    rows = []
    for drive_file in drive_files:
        parsed = parse_filename(drive_file["name"])
        hint = "" if parsed.is_score else parsed.instrument_hint
        if parsed.is_score:
            hint = "Conductor"

        matched_inst, inst_conf = (
            match_instrument(hint, instruments) if hint else (None, "low")
        )

        part = ""
        if matched_inst and parsed.part_ordinal:
            part = f"{parsed.part_ordinal} {matched_inst.name}"

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
        })

    return render(request, "chart_import/review.html", {
        "song": song,
        "songs": list(Song.objects.all()),
        "folder_id": folder_id,
        "folder_name": folder_name,
        "rows": rows,
        "instruments": instruments,
    })
