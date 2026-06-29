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
