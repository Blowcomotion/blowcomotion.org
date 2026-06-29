import io
import re
from dataclasses import dataclass

from django.conf import settings

EXCLUDE_FOLDERS = ["01 -Warmups and Exercises", "03 - Resources-Reference"]
ARCHIVE_FOLDERS = ["ZZArchive - INACTIVE"]

# Keys are lowercase normalized tokens (spaces or underscores replaced with space)
_ALIAS_MAP = {
    "horn in f": "French Horn",
    "f horn": "French Horn",
    "fhorn": "French Horn",
    "tuba": "Tuba",
    "cowbell": "Cow Bell",
    "tmpt": "Trumpet",
    "tpet": "Trumpet",
    "bari sax": "Baritone Saxophone",
    "bari": "Baritone Saxophone",
    "clrnt": "Clarinet",
    "tnr": "Tenor Saxophone",
    "drums": "Drum Set",
    "4 piece drum kit": "Drum Set",
}

_SCORE_KEYWORDS = {"score", "conductor", "full", "all parts"}

_ORDINAL_MAP = {
    "1": "1st", "1st": "1st",
    "2": "2nd", "2nd": "2nd",
    "3": "3rd", "3rd": "3rd",
    "4": "4th", "4th": "4th",
}


@dataclass
class ParsedFile:
    instrument_hint: str  # alias-normalized name for instrument matching
    part_ordinal: str     # "1st", "2nd", "" etc.
    is_score: bool


def parse_filename(name: str) -> ParsedFile:
    stem = re.sub(r"\.pdf$", "", name, flags=re.IGNORECASE)
    # Normalize separators to spaces for keyword matching
    normalized = re.sub(r"[-_]+", " ", stem).strip()
    lower = normalized.lower()

    if any(kw in lower for kw in _SCORE_KEYWORDS):
        return ParsedFile(instrument_hint="", part_ordinal="", is_score=True)

    tokens = re.split(r"[-_\s]+", stem)

    instrument_hint = ""
    part_ordinal = ""
    instrument_token_end = 0

    # Slide a window over tokens looking for alias matches (longest first)
    for start in range(len(tokens)):
        for length in (4, 3, 2, 1):
            end = start + length
            if end > len(tokens):
                continue
            candidate = " ".join(tokens[start:end]).lower()
            if candidate in _ALIAS_MAP:
                instrument_hint = _ALIAS_MAP[candidate]
                instrument_token_end = end
                break
        if instrument_hint:
            break

    if not instrument_hint:
        # Use the last non-ordinal token as a raw hint (catches plain instrument names)
        for tok in reversed(tokens):
            if tok.lower() not in _ORDINAL_MAP:
                instrument_hint = tok
                break

    # Extract ordinal from tokens after the matched instrument
    for tok in tokens[instrument_token_end:]:
        if tok.lower() in _ORDINAL_MAP:
            part_ordinal = _ORDINAL_MAP[tok.lower()]
            break

    return ParsedFile(instrument_hint=instrument_hint, part_ordinal=part_ordinal, is_score=False)


def _get_drive_service():
    from googleapiclient.discovery import build
    return build("drive", "v3", developerKey=settings.GDRIVE_API_KEY)


def list_song_folders(folder_id: str) -> list:
    service = _get_drive_service()
    results = service.files().list(
        q=f"'{folder_id}' in parents and mimeType='application/vnd.google-apps.folder' and trashed=false",
        fields="files(id, name)",
        pageSize=1000,
    ).execute()
    return results.get("files", [])


def list_pdfs_in_folder(folder_id: str, _prefix: str = "") -> list:
    service = _get_drive_service()
    results = service.files().list(
        q=f"'{folder_id}' in parents and trashed=false",
        fields="files(id, name, mimeType, modifiedTime)",
        pageSize=1000,
    ).execute()
    files = []
    for item in results.get("files", []):
        if item["mimeType"] == "application/vnd.google-apps.folder":
            files.extend(list_pdfs_in_folder(item["id"], _prefix + item["name"] + "/"))
        elif item["name"].lower().endswith(".pdf"):
            item["relative_path"] = _prefix + item["name"]
            files.append(item)
    return files


def _download_pdf(file_id: str) -> bytes:
    from googleapiclient.http import MediaIoBaseDownload
    service = _get_drive_service()
    request = service.files().get_media(fileId=file_id)
    buf = io.BytesIO()
    dl = MediaIoBaseDownload(buf, request)
    done = False
    while not done:
        _, done = dl.next_chunk()
    return buf.getvalue()


import difflib
from datetime import datetime, timezone

from wagtail.documents import get_document_model

AMBIGUOUS_HINTS = {"baritone"}  # always route to review; ambiguous across 3 DB instruments


def match_song(folder_name: str, songs: list) -> tuple:
    if not songs:
        return None, 0.0
    names = [s.title for s in songs]
    scores = [(difflib.SequenceMatcher(None, folder_name.lower(), n.lower()).ratio(), i)
               for i, n in enumerate(names)]
    best_score, best_idx = max(scores)
    return songs[best_idx], best_score


def match_instrument(hint: str, instruments: list) -> tuple:
    if hint.lower() in AMBIGUOUS_HINTS:
        return None, "ambiguous"
    names = [i.name for i in instruments]
    # Exact case-insensitive match first
    lower_names = [n.lower() for n in names]
    if hint.lower() in lower_names:
        return instruments[lower_names.index(hint.lower())], "high"
    # Fuzzy fallback
    matches = difflib.get_close_matches(hint, names, n=1, cutoff=0.6)
    if matches:
        return instruments[names.index(matches[0])], "high"
    return None, "low"


@dataclass
class ReconcileResult:
    drive_file: dict
    parsed: ParsedFile
    apply: str          # "auto", "review", "noop"
    reason: str         # "Exact", "High", "Needs review", "New", ""
    existing_chart: object  # Chart instance or None


def _parse_drive_time(s: str) -> datetime:
    return datetime.fromisoformat(s.replace("Z", "+00:00"))


def reconcile_file(drive_file: dict, parsed: ParsedFile, existing_charts: list) -> ReconcileResult:
    drive_time = _parse_drive_time(drive_file["modifiedTime"])
    file_id = drive_file["id"]

    for chart in existing_charts:
        if chart.drive_file_id == file_id:
            stored = chart.drive_modified_time
            if stored:
                stored_utc = stored if stored.tzinfo else stored.replace(tzinfo=timezone.utc)
                if stored_utc >= drive_time:
                    return ReconcileResult(drive_file, parsed, "noop", "", chart)
            return ReconcileResult(drive_file, parsed, "auto", "Exact", chart)

    if len(existing_charts) == 1:
        return ReconcileResult(drive_file, parsed, "auto", "High", existing_charts[0])

    if len(existing_charts) > 1:
        return ReconcileResult(drive_file, parsed, "review", "Needs review", None)

    return ReconcileResult(drive_file, parsed, "review", "New", None)


def _safe_delete_document(doc):
    from blowcomotion.models import Chart

    # ponytail: skip rich-text usage scan — Chart PDFs are never embedded in rich text
    if not Chart.objects.filter(pdf=doc).exists():
        doc.file.delete(save=False)
        doc.delete()
