import difflib
import io
import re
from dataclasses import dataclass
from datetime import datetime, timezone

from django.conf import settings

EXCLUDE_FOLDERS = ["01 -Warmups and Exercises", "03 - Resources-Reference"]
ARCHIVE_FOLDERS = ["ZZArchive - INACTIVE"]

# Keys are lowercase normalized tokens (dots/spaces/underscores replaced with space)
_ALIAS_MAP = {
    # French Horn / Mellophone
    "horn in f": "French Horn/Mellophone",
    "hornin f": "French Horn/Mellophone",
    "f horn": "French Horn/Mellophone",
    "fhorn": "French Horn/Mellophone",
    "fr horn": "French Horn/Mellophone",
    "frech horn": "French Horn/Mellophone",
    "fhn": "French Horn/Mellophone",
    "mellophone": "French Horn/Mellophone",
    # Tuba / Sousaphone
    "tuba": "Tuba/Sousaphone",
    "sousa": "Tuba/Sousaphone",
    "sousaphone": "Tuba/Sousaphone",
    # Baritone / Euphonium
    "baritone bc": "Baritone",
    "baritone tc": "Baritone/Euphonium",
    "baritone treble": "Baritone/Euphonium",
    "baritone bass": "Baritone/Euphonium",
    "euph": "Baritone/Euphonium",
    "euphonium": "Baritone/Euphonium",
    # Saxophones — full names prevent "Saxophone" fuzzy-matching "Bass Saxophone"
    "tenor saxophone": "Tenor Saxophone",
    "tenor sax": "Tenor Saxophone",
    "tenor": "Tenor Saxophone",
    "tnr": "Tenor Saxophone",
    "alto saxophone": "Alto Saxophone",
    "alto sax": "Alto Saxophone",
    "alto": "Alto Saxophone",
    "baritone saxophone": "Baritone Saxophone",
    "baritone sax": "Baritone Saxophone",
    "bari sax": "Baritone Saxophone",
    "bari": "Baritone Saxophone",
    "bass saxophone": "Bass Saxophone",
    "bass sax": "Bass Saxophone",
    "soprano saxophone": "Soprano Saxophone",
    "soprano sax": "Soprano Saxophone",
    # Brass
    "bass trombone": "Bass Trombone",
    "tbn": "Trombone",
    "tmpt": "Trumpet",
    "tpet": "Trumpet",
    "flugel": "Flugelhorn",
    "flugelhorn": "Flugelhorn",
    # Reed
    "bass clarinet": "Bass Clarinet",
    "clrnt": "Clarinet",
    # Bass
    "electric bass": "Electric Bass",
    "elec bass": "Electric Bass",
    # Percussion
    "concert bass drum": "Bass Drum",
    "tenor drums": "Quad Tenors",
    "tenor line": "Quad Tenors",
    "drum set": "Drum Set",
    "drumset": "Drum Set",
    "bells": "Bells, Marching",
    "aux perc": "Hand Percussion",
    "hand clap": "Hand Percussion",
    "bateria": "Drum Set",
    "4 piece drum kit": "Drum Set",
    # Miscellaneous
    "tenorhorn": "Horn Tenor",
    "cowbell": "Cow Bell",
}

_SCORE_TOKENS = {"score", "conductor"}

# Transposition key labels — filenames like "Song Name - Bb.pdf" share one PDF across instruments
_KEY_LABELS = {"bb", "eb", "ab", "db", "gb", "fb", "cb", "f", "g", "c", "d", "a", "e", "b", "bass", "concert"}

# Default instrument names per transposition key, derived from production chart data
_KEY_INSTRUMENT_MAP = {
    "bb": ["Trumpet", "Clarinet", "Tenor Saxophone"],
    "eb": ["Alto Saxophone", "Baritone Saxophone"],
    "c": ["Flute", "Trombone", "Tuba/Sousaphone", "Baritone/Euphonium", "Bells, Marching"],
    "bass": ["Tuba/Sousaphone"],
}

_ORDINAL_MAP = {
    "1": "1st", "1st": "1st",
    "2": "2nd", "2nd": "2nd",
    "3": "3rd", "3rd": "3rd",
    "4": "4th", "4th": "4th",
    # Roman numerals
    "i": "1st",
    "ii": "2nd",
    "iii": "3rd",
    "iv": "4th",
}


@dataclass
class ResolvedFile:
    drive_file: dict
    parsed: "ParsedFile"
    matched_inst: object   # Instrument or None
    inst_conf: str         # "high", "low", "ambiguous"
    part: str


@dataclass
class ParsedFile:
    instrument_hint: str  # alias-normalized name or transposition key (e.g. "Bb", "Eb")
    part_ordinal: str     # "1st", "2nd", "" etc.
    is_score: bool
    is_key: bool = False  # True when filename encodes a transposition key shared across instruments
    alt_hint: str = ""   # post-dash side for "Song - Instrument" format; resolved if primary is low-confidence


def _split_camel(text: str) -> str:
    """Split CamelCase and letter→digit boundaries: "CaravanAltoSax" → "Caravan Alto Sax"."""
    text = re.sub(r"([a-z])([A-Z])", r"\1 \2", text)
    text = re.sub(r"([a-zA-Z])(\d)", r"\1 \2", text)
    return text.strip()


def parse_filename(name: str) -> ParsedFile:
    stem = re.sub(r"\.pdf$", "", name, flags=re.IGNORECASE)
    # Normalize separators to spaces, then split CamelCase for score-phrase detection.
    # CamelCase splitting only affects normalized (for score detection) and the no-separator
    # else branch; the separator-based branches use stem directly for reliable split points.
    normalized = _split_camel(re.sub(r"[-_]+", " ", stem).strip())
    lower = normalized.lower()

    tokens_lower = re.split(r"[\s_-]+", lower)
    # "all parts" only triggers score mode when it ends the (normalized) filename — "Song all parts_Tuba"
    # has "all parts" mid-string and should NOT be treated as a score.
    if (
        re.search(r"\ball\s+parts\s*$", lower)
        or "full score" in lower
        or any(tok in tokens_lower for tok in _SCORE_TOKENS)
    ):
        return ParsedFile(instrument_hint="", part_ordinal="", is_score=True)

    # Detect filename format and isolate the instrument portion.
    # "Song Name - Key" (post-dash is a single key label like Bb/Eb/C): key-based chart.
    # "Instrument - Song Name" or "Song Name - Instrument" (space-dash-space): ambiguous;
    #   try pre-dash as primary, store post-dash as alt_hint for fallback in resolve_drive_file.
    # "Song Name-Instrument" (no spaces around dash, pre-dash has spaces): post-dash is the instrument.
    # No separator: apply CamelCase splitting so "CaravanAltoSax" → tokens ["Caravan","Alto","Sax"].
    _alt_hint = ""
    if " - " in stem:
        pre, post = stem.split(" - ", 1)
        post_stripped = post.strip()
        if " " not in post_stripped and post_stripped.lower() in _KEY_LABELS:
            return ParsedFile(instrument_hint=post_stripped, part_ordinal="", is_score=False, is_key=True)
        search_stem = pre
        instrument_portion_isolated = True
        _alt_hint = post_stripped  # may be the actual instrument (Song - Instrument format)
    elif "-" in stem and " " in stem.split("-", 1)[0]:
        search_stem = stem.split("-", 1)[1]
        instrument_portion_isolated = True
    else:
        search_stem = _split_camel(stem)
        instrument_portion_isolated = False

    tokens = re.split(r"[-_.~\s]+", search_stem)

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
        if instrument_portion_isolated:
            # Instrument portion is clean — collect ordinal, strip "in <Key>" suffixes.
            # "Clarinet_in_Bb1" → tokens ["Clarinet","in","Bb1"] → hint="Clarinet", ord="1st"
            # Key tokens are only stripped when directly preceded by the word "in"; bare words
            # like "bass" in "Bass Drum" are NOT treated as key labels.
            _sorted_keys = sorted(_KEY_LABELS, key=len, reverse=True)

            def _key_digit(t):
                """Return trailing digit string if t is <key><digit>, '' if bare key, else None."""
                for k in _sorted_keys:
                    if t == k:
                        return ""
                    if t.startswith(k) and t[len(k):].isdigit():
                        return t[len(k):]
                return None

            hint_tokens = []
            expect_key = False  # True immediately after seeing "in"
            for tok in tokens:
                tok_lower = tok.lower()
                if tok_lower == "in":
                    expect_key = True
                    continue
                if expect_key:
                    expect_key = False
                    kd = _key_digit(tok_lower)
                    if kd is not None:
                        if kd and not part_ordinal:
                            part_ordinal = _ORDINAL_MAP.get(kd, kd + "th")
                        continue
                    # "in" not followed by a key — restore "in" as part of the name
                    hint_tokens.append("in")
                if tok_lower in _ORDINAL_MAP:
                    if not part_ordinal:
                        part_ordinal = _ORDINAL_MAP[tok_lower]
                elif tok_lower.isdigit():
                    pass  # bare numeric (date prefix, page number) — skip
                else:
                    hint_tokens.append(tok)
            hint = " ".join(hint_tokens)
            # If the "instrument" portion has no letters it's a date/version, not an instrument
            if not any(c.isalpha() for c in hint):
                return ParsedFile(instrument_hint="", part_ordinal="", is_score=True, alt_hint=_alt_hint)
            return ParsedFile(instrument_hint=hint, part_ordinal=part_ordinal, is_score=False, alt_hint=_alt_hint)
        else:
            # No clear separator — use last non-ordinal token only
            for tok in reversed(tokens):
                if tok.lower() not in _ORDINAL_MAP:
                    instrument_hint = tok
                    break

    # Extract ordinal from tokens after the matched instrument
    for tok in tokens[instrument_token_end:]:
        if tok.lower() in _ORDINAL_MAP:
            part_ordinal = _ORDINAL_MAP[tok.lower()]
            break

    return ParsedFile(instrument_hint=instrument_hint, part_ordinal=part_ordinal, is_score=False, alt_hint=_alt_hint)


def _get_drive_service():
    from googleapiclient.discovery import build
    api_key = settings.GDRIVE_API_KEY
    if not api_key:
        from django.core.exceptions import ImproperlyConfigured
        raise ImproperlyConfigured("GDRIVE_API_KEY is not set in local.py")
    return build("drive", "v3", developerKey=api_key)


_SHARED_DRIVE_KWARGS = dict(supportsAllDrives=True, includeItemsFromAllDrives=True)


def list_song_folders(folder_id: str) -> list:
    service = _get_drive_service()
    results = service.files().list(
        q=f"'{folder_id}' in parents and mimeType='application/vnd.google-apps.folder' and trashed=false",
        fields="files(id, name)",
        pageSize=1000,
        **_SHARED_DRIVE_KWARGS,
    ).execute()
    return results.get("files", [])


def list_pdfs_in_folder(folder_id: str, _prefix: str = "") -> list:
    service = _get_drive_service()
    results = service.files().list(
        q=f"'{folder_id}' in parents and trashed=false",
        fields="files(id, name, mimeType, modifiedTime)",
        pageSize=1000,
        **_SHARED_DRIVE_KWARGS,
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


AMBIGUOUS_HINTS = {"baritone", "drums"}  # always route to review; ambiguous across multiple DB instruments


def match_song(folder_name: str, songs: list) -> tuple:
    if not songs:
        return None, 0.0
    names = [s.title for s in songs]
    scores = [(difflib.SequenceMatcher(None, folder_name.lower(), n.lower()).ratio(), i)
               for i, n in enumerate(names)]
    best_score, best_idx = max(scores)
    return songs[best_idx], best_score


def _resolve_alt_hint(text: str) -> tuple:
    """Resolve a raw post-dash string to (canonical_hint, ordinal, via_alias).

    via_alias is True when the alias map was used, making the match highly reliable.
    Song names never appear in the alias map, so via_alias=True means the post-dash
    side is almost certainly the instrument (not the song title).
    """
    # Strip ALL parentheticals: "(cropped)", "(updated solo)", "(8va)", "(1)" etc.
    text = re.sub(r"\([^)]*\)", "", text).strip()
    # Apply CamelCase and digit boundary splitting: "BariSax" → "Bari Sax"
    text = _split_camel(text)
    tokens = re.split(r"[-_.~\s]+", text.strip())
    ordinal = ""
    for start in range(len(tokens)):
        for length in (4, 3, 2, 1):
            end = start + length
            if end > len(tokens):
                continue
            candidate = " ".join(tokens[start:end]).lower()
            if candidate in _ALIAS_MAP:
                for tok in tokens[end:]:
                    if tok.lower() in _ORDINAL_MAP and not ordinal:
                        ordinal = _ORDINAL_MAP[tok.lower()]
                return _ALIAS_MAP[candidate], ordinal, True
    hint_tokens = []
    for tok in tokens:
        if tok.lower() in _ORDINAL_MAP:
            if not ordinal:
                ordinal = _ORDINAL_MAP[tok.lower()]
        else:
            hint_tokens.append(tok)
    return " ".join(hint_tokens), ordinal, False


def resolve_drive_file(drive_file: dict, instruments: list) -> "ResolvedFile":
    parsed = parse_filename(drive_file["name"])
    if parsed.is_key:
        return ResolvedFile(drive_file=drive_file, parsed=parsed, matched_inst=None, inst_conf="key", part="")
    hint = "Conductor" if parsed.is_score else parsed.instrument_hint
    matched_inst, inst_conf = match_instrument(hint, instruments) if hint else (None, "low")
    part = f"{parsed.part_ordinal} {matched_inst.name}".strip() if (matched_inst and parsed.part_ordinal) else ""

    # For "X - Y" filenames the format is ambiguous (Instrument - Song vs Song - Instrument).
    # Fall back to the post-dash alt_hint when:
    #   - primary gave low confidence (primary was not an instrument), OR
    #   - alt resolved via alias map (aliases contain only instrument names, never song titles), OR
    #   - primary matched only via fuzzy (e.g. "Carinito" → "Clarinet" at 0.75) and alt has any match
    #     (fuzzy false positives happen when a song name phonetically resembles an instrument)
    if parsed.alt_hint:
        alt_canonical, alt_ordinal, alt_via_alias = _resolve_alt_hint(parsed.alt_hint)
        alt_inst, alt_conf = match_instrument(alt_canonical, instruments) if alt_canonical else (None, "low")
        # Score-detected files always matched to "Conductor"; don't treat that as exact
        # so the alt_hint can still override when the filename carries a real instrument.
        primary_is_exact = (not parsed.is_score) and matched_inst is not None and hint.lower() == matched_inst.name.lower()
        prefer_alt = (
            (inst_conf == "low" and alt_conf != "low")
            or (alt_via_alias and alt_conf != "low")
            or (not primary_is_exact and alt_conf != "low")
        )
        if prefer_alt:
            matched_inst, inst_conf = alt_inst, alt_conf
            part = f"{alt_ordinal} {matched_inst.name}".strip() if (matched_inst and alt_ordinal) else ""

    return ResolvedFile(drive_file=drive_file, parsed=parsed, matched_inst=matched_inst, inst_conf=inst_conf, part=part)


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
