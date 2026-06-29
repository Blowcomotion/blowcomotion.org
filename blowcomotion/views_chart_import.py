import logging

from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.http import HttpResponseForbidden
from django.shortcuts import render

from blowcomotion.drive_sync import (
    ARCHIVE_FOLDERS,
    EXCLUDE_FOLDERS,
    list_song_folders,
    match_song,
)
from blowcomotion.models import Song

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
