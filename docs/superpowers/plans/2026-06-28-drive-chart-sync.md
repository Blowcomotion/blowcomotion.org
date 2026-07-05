# Google Drive Chart Sync Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Pull PDF charts from a public Google Drive folder into Wagtail, auto-match each PDF to `(Song, Instrument, part)`, let admins review and confirm before importing, and keep charts fresh via a scheduled management command.

**Architecture:** Single core module `blowcomotion/drive_sync.py` handles Drive API calls, filename parsing, instrument/song matching, and reconciliation. Two thin callers share this: `blowcomotion/views_chart_import.py` (manual picker→review→import flow) and `blowcomotion/management/commands/sync_charts.py` (automated cron refresh). `Chart` gains two nullable fields to anchor refresh identity. Admin views registered via the existing `wagtail_hooks.py`.

**Tech Stack:** Django/Wagtail, `google-api-python-client` (new), `difflib` (stdlib).

## Global Constraints

- GPG-sign all commits: `git commit -S`
- No `Co-Authored-By` lines, no emojis in commits or PRs
- Conventional commit prefixes: `feat:`, `fix:`, `refactor:`, `chore:`
- PR base branch: `development`
- Tests run via `python manage.py test blowcomotion.tests.test_drive_sync`
- Edit files under `blowcomotion/static/`, never `static/`
- `local.py` holds secrets; `base.py` holds safe defaults with `None`
- Migrations reviewed by `wagtail-migration-reviewer` agent before commit
- Use `get_document_model()` for Wagtail documents, never import `Document` directly
- `Chart.pdf` has `related_name="+"` — no reverse manager; use `Chart.objects.filter(pdf=doc)`
- `Chart.song` is a `ParentalKey` with `related_name="charts"` — `song.charts.all()` works

---

### Task 1: Model fields + settings defaults + migration

**Files:**
- Modify: `blowcomotion/models.py` (Chart class, after `instrument` field)
- Modify: `blowcomotion/settings/base.py` (after GIGO settings block)
- Create: auto-generated migration

**Interfaces:**
- Produces: `Chart.drive_file_id` (CharField, db_index) and `Chart.drive_modified_time` (DateTimeField) accessible to all later tasks

- [ ] **Step 1: Add fields to Chart in models.py**

Find the `Chart` class (around line 246). After the `instrument = models.ForeignKey(...)` line, add:

```python
drive_file_id = models.CharField(max_length=255, null=True, blank=True, db_index=True)
drive_modified_time = models.DateTimeField(null=True, blank=True)
```

- [ ] **Step 2: Add settings defaults to base.py**

After the `GIGO_BAND_ID_LOCAL` line in `blowcomotion/settings/base.py`, add:

```python
GDRIVE_API_KEY = None
GDRIVE_CHARTS_FOLDER_ID = None
```

- [ ] **Step 3: Create and apply migration**

```bash
python manage.py makemigrations
```

Expected: creates `blowcomotion/migrations/XXXX_chart_drive_fields.py`

Use the `wagtail-migration-reviewer` agent to review the generated file, then apply:

```bash
python manage.py migrate
```

Expected: applies cleanly, no errors.

- [ ] **Step 4: Verify**

```bash
python manage.py shell -c "from blowcomotion.models import Chart; print(Chart._meta.get_field('drive_file_id'))"
```

Expected: `<django.db.models.fields.CharField: drive_file_id>`

- [ ] **Step 5: Commit**

```bash
git add blowcomotion/models.py blowcomotion/settings/base.py blowcomotion/migrations/
git commit -S -m "feat: add drive_file_id and drive_modified_time to Chart"
```

---

### Task 2: Install dependency + Drive client + filename parser

**Files:**
- Modify: `requirements.txt`
- Create: `blowcomotion/drive_sync.py`
- Create: `blowcomotion/tests/test_drive_sync.py`

**Interfaces:**
- Produces:
  - `EXCLUDE_FOLDERS: list[str]`, `ARCHIVE_FOLDERS: list[str]` — module constants
  - `_get_drive_service()` → Drive service object (lazy import of googleapiclient)
  - `list_song_folders(folder_id: str)` → `list[dict]` each with `id`, `name`
  - `list_pdfs_in_folder(folder_id: str)` → `list[dict]` each with `id`, `name`, `modifiedTime`, `relative_path`
  - `ParsedFile` dataclass: fields `instrument_hint: str`, `part_ordinal: str`, `is_score: bool`
  - `parse_filename(name: str) -> ParsedFile`
  - `_download_pdf(file_id: str) -> bytes`

- [ ] **Step 1: Install dependency**

Add `google-api-python-client` to `requirements.txt`, then:

```bash
pip install google-api-python-client
```

- [ ] **Step 2: Write parser tests first**

Create `blowcomotion/tests/test_drive_sync.py`:

```python
from django.test import TestCase
from blowcomotion.drive_sync import parse_filename, ParsedFile


class TestParseFilename(TestCase):
    def _p(self, name):
        return parse_filename(name)

    def test_score_keyword(self):
        r = self._p("MySong_Score.pdf")
        self.assertTrue(r.is_score)
        self.assertEqual(r.instrument_hint, "")
        self.assertEqual(r.part_ordinal, "")

    def test_conductor_keyword(self):
        r = self._p("MySong_Conductor.pdf")
        self.assertTrue(r.is_score)

    def test_full_score(self):
        r = self._p("MySong_Full_Score.pdf")
        self.assertTrue(r.is_score)

    def test_all_parts(self):
        r = self._p("MySong_All_Parts.pdf")
        self.assertTrue(r.is_score)

    def test_trumpet_tmpt_part_1(self):
        r = self._p("MySong_Tmpt_1.pdf")
        self.assertFalse(r.is_score)
        self.assertEqual(r.instrument_hint, "Trumpet")
        self.assertEqual(r.part_ordinal, "1st")

    def test_trumpet_tpet_part_2(self):
        r = self._p("Song_Tpet_2.pdf")
        self.assertEqual(r.instrument_hint, "Trumpet")
        self.assertEqual(r.part_ordinal, "2nd")

    def test_horn_in_f(self):
        r = self._p("Song_Horn_in_F.pdf")
        self.assertEqual(r.instrument_hint, "French Horn")

    def test_fhorn_part_1(self):
        r = self._p("Song_FHorn_1.pdf")
        self.assertEqual(r.instrument_hint, "French Horn")
        self.assertEqual(r.part_ordinal, "1st")

    def test_tuba_no_part(self):
        r = self._p("Song_Tuba.pdf")
        self.assertEqual(r.instrument_hint, "Tuba")
        self.assertEqual(r.part_ordinal, "")

    def test_cowbell(self):
        r = self._p("Song_Cowbell.pdf")
        self.assertEqual(r.instrument_hint, "Cow Bell")

    def test_bari_sax(self):
        r = self._p("Song_Bari_Sax.pdf")
        self.assertEqual(r.instrument_hint, "Baritone Saxophone")

    def test_bari(self):
        r = self._p("Song_Bari.pdf")
        self.assertEqual(r.instrument_hint, "Baritone Saxophone")

    def test_clrnt(self):
        r = self._p("Song_Clrnt.pdf")
        self.assertEqual(r.instrument_hint, "Clarinet")

    def test_tnr(self):
        r = self._p("Song_Tnr.pdf")
        self.assertEqual(r.instrument_hint, "Tenor Saxophone")

    def test_drums(self):
        r = self._p("Song_Drums.pdf")
        self.assertEqual(r.instrument_hint, "Drum Set")

    def test_drum_kit(self):
        r = self._p("Song_4-Piece_Drum_Kit.pdf")
        self.assertEqual(r.instrument_hint, "Drum Set")

    def test_baritone_stays_ambiguous(self):
        # "Baritone" alone is ambiguous across 3 DB instruments — never auto-resolved
        r = self._p("Song_Baritone.pdf")
        self.assertEqual(r.instrument_hint, "Baritone")
        self.assertFalse(r.is_score)

    def test_part_1st_word(self):
        r = self._p("Song_Trombone_1st.pdf")
        self.assertEqual(r.part_ordinal, "1st")

    def test_part_2nd_number(self):
        r = self._p("Song_Trombone_2.pdf")
        self.assertEqual(r.part_ordinal, "2nd")

    def test_part_2nd_word(self):
        r = self._p("Song_Trombone_2nd.pdf")
        self.assertEqual(r.part_ordinal, "2nd")

    def test_part_3rd(self):
        r = self._p("Song_Trombone_3.pdf")
        self.assertEqual(r.part_ordinal, "3rd")

    def test_no_part(self):
        r = self._p("Song_Trombone.pdf")
        self.assertEqual(r.part_ordinal, "")

    def test_pdf_extension_stripped(self):
        r = self._p("Song_Trombone.pdf")
        self.assertNotIn(".pdf", r.instrument_hint)
```

- [ ] **Step 3: Run tests to verify they fail**

```bash
python manage.py test blowcomotion.tests.test_drive_sync.TestParseFilename
```

Expected: `ImportError` (module not created yet)

- [ ] **Step 4: Create drive_sync.py**

Create `blowcomotion/drive_sync.py`:

```python
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
        for length in (3, 2, 1):
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
```

- [ ] **Step 5: Run parser tests**

```bash
python manage.py test blowcomotion.tests.test_drive_sync.TestParseFilename
```

Expected: all pass. Fix any failures before proceeding.

- [ ] **Step 6: Commit**

```bash
git add requirements.txt blowcomotion/drive_sync.py blowcomotion/tests/test_drive_sync.py
git commit -S -m "feat: add Drive client and filename parser"
```

---

### Task 3: Song/instrument matchers + reconciler

**Files:**
- Modify: `blowcomotion/drive_sync.py` (append)
- Modify: `blowcomotion/tests/test_drive_sync.py` (append)

**Interfaces:**
- Consumes: `ParsedFile` from Task 2
- Produces:
  - `match_song(folder_name: str, songs: list) -> tuple[Song | None, float]`
  - `AMBIGUOUS_HINTS: set[str]` — hints that always route to review
  - `match_instrument(hint: str, instruments: list) -> tuple[Instrument | None, str]` where str is `"high"`, `"low"`, or `"ambiguous"`
  - `ReconcileResult` dataclass: `drive_file: dict`, `parsed: ParsedFile`, `apply: str` ("auto"/"review"/"noop"), `reason: str` ("Exact"/"High"/"Needs review"/"New"/""), `existing_chart`
  - `reconcile_file(drive_file: dict, parsed: ParsedFile, existing_charts: list) -> ReconcileResult`
  - `_safe_delete_document(doc)` — deletes Wagtail Document + file if no other Chart references it

- [ ] **Step 1: Write matcher and reconciler tests**

Append to `blowcomotion/tests/test_drive_sync.py`:

```python
import datetime
from unittest.mock import MagicMock

from blowcomotion.drive_sync import (
    match_song, match_instrument, reconcile_file, ReconcileResult,
)


class TestMatchSong(TestCase):
    def _song(self, title):
        s = MagicMock()
        s.title = title
        return s

    def test_exact_match(self):
        songs = [self._song("Soul Finger"), self._song("Brick House")]
        song, score = match_song("Soul Finger", songs)
        self.assertEqual(song.title, "Soul Finger")
        self.assertGreater(score, 0.9)

    def test_fuzzy_match(self):
        songs = [self._song("Soul Finger"), self._song("Brick House")]
        song, score = match_song("Soulfinger", songs)
        self.assertEqual(song.title, "Soul Finger")
        self.assertGreater(score, 0.5)

    def test_poor_match_returns_low_score(self):
        songs = [self._song("Soul Finger")]
        _, score = match_song("Completely Different Title", songs)
        self.assertLess(score, 0.5)

    def test_empty_list(self):
        song, score = match_song("Soul Finger", [])
        self.assertIsNone(song)
        self.assertEqual(score, 0.0)


class TestMatchInstrument(TestCase):
    def _inst(self, name):
        i = MagicMock()
        i.name = name
        return i

    def _instruments(self):
        return [
            self._inst("Trumpet"),
            self._inst("French Horn"),
            self._inst("Mellophone"),
            self._inst("Tuba"),
            self._inst("Sousaphone"),
            self._inst("Baritone Horn"),
            self._inst("Baritone Saxophone"),
            self._inst("Euphonium (Baritone)"),
            self._inst("Trombone"),
            self._inst("Clarinet"),
            self._inst("Tenor Saxophone"),
            self._inst("Drum Set"),
            self._inst("Cow Bell"),
            self._inst("Conductor"),
        ]

    def test_exact_name_match(self):
        inst, conf = match_instrument("Trumpet", self._instruments())
        self.assertEqual(inst.name, "Trumpet")
        self.assertEqual(conf, "high")

    def test_fuzzy_trombone(self):
        inst, conf = match_instrument("Trombone", self._instruments())
        self.assertEqual(inst.name, "Trombone")
        self.assertEqual(conf, "high")

    def test_cow_bell(self):
        inst, conf = match_instrument("Cow Bell", self._instruments())
        self.assertEqual(inst.name, "Cow Bell")
        self.assertEqual(conf, "high")

    def test_ambiguous_baritone(self):
        _, conf = match_instrument("Baritone", self._instruments())
        self.assertEqual(conf, "ambiguous")

    def test_no_match(self):
        _, conf = match_instrument("Zylophone", self._instruments())
        self.assertEqual(conf, "low")

    def test_conductor(self):
        inst, conf = match_instrument("Conductor", self._instruments())
        self.assertEqual(inst.name, "Conductor")
        self.assertEqual(conf, "high")


class TestReconcileFile(TestCase):
    def _drive_file(self, file_id, modified="2025-06-01T12:00:00.000Z"):
        return {
            "id": file_id,
            "name": "Song_Tmpt_1.pdf",
            "modifiedTime": modified,
            "relative_path": "Song_Tmpt_1.pdf",
        }

    def _chart(self, file_id=None, modified=None):
        c = MagicMock()
        c.drive_file_id = file_id
        c.drive_modified_time = modified
        return c

    def _parsed(self):
        from blowcomotion.drive_sync import ParsedFile
        return ParsedFile(instrument_hint="Trumpet", part_ordinal="1st", is_score=False)

    def test_exact_newer_modified_is_auto(self):
        old_time = datetime.datetime(2025, 1, 1, tzinfo=datetime.timezone.utc)
        chart = self._chart(file_id="abc", modified=old_time)
        result = reconcile_file(self._drive_file("abc"), self._parsed(), [chart])
        self.assertEqual(result.apply, "auto")
        self.assertEqual(result.reason, "Exact")

    def test_exact_same_modified_is_noop(self):
        t = datetime.datetime(2025, 6, 1, 12, 0, 0, tzinfo=datetime.timezone.utc)
        chart = self._chart(file_id="abc", modified=t)
        result = reconcile_file(self._drive_file("abc"), self._parsed(), [chart])
        self.assertEqual(result.apply, "noop")

    def test_old_file_id_gone_one_chart_is_high(self):
        chart = self._chart(file_id="old_id", modified=datetime.datetime(2025, 1, 1, tzinfo=datetime.timezone.utc))
        result = reconcile_file(self._drive_file("new_id"), self._parsed(), [chart])
        self.assertEqual(result.apply, "auto")
        self.assertEqual(result.reason, "High")

    def test_multiple_charts_needs_review(self):
        chart = self._chart(file_id=None)
        result = reconcile_file(self._drive_file("new_id"), self._parsed(), [chart, chart])
        self.assertEqual(result.apply, "review")
        self.assertEqual(result.reason, "Needs review")

    def test_no_existing_chart_is_new(self):
        result = reconcile_file(self._drive_file("brand_new"), self._parsed(), [])
        self.assertEqual(result.apply, "review")
        self.assertEqual(result.reason, "New")
```

- [ ] **Step 2: Run to verify they fail**

```bash
python manage.py test blowcomotion.tests.test_drive_sync.TestMatchSong blowcomotion.tests.test_drive_sync.TestMatchInstrument blowcomotion.tests.test_drive_sync.TestReconcileFile
```

Expected: `ImportError` (functions not yet defined)

- [ ] **Step 3: Append matchers and reconciler to drive_sync.py**

```python
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
```

- [ ] **Step 4: Run matcher + reconciler tests**

```bash
python manage.py test blowcomotion.tests.test_drive_sync.TestMatchSong blowcomotion.tests.test_drive_sync.TestMatchInstrument blowcomotion.tests.test_drive_sync.TestReconcileFile
```

Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add blowcomotion/drive_sync.py blowcomotion/tests/test_drive_sync.py
git commit -S -m "feat: add song/instrument matchers and reconciler"
```

---

### Task 4: Picker admin view + template

**Files:**
- Create: `blowcomotion/views_chart_import.py`
- Create: `blowcomotion/templates/chart_import/picker.html`
- Modify: `blowcomotion/tests/test_drive_sync.py` (append)

**Interfaces:**
- Consumes: `list_song_folders`, `match_song`, `EXCLUDE_FOLDERS`, `ARCHIVE_FOLDERS` from `drive_sync`; `Song` model
- Produces: `picker(request)` view function; URL name `chart_import_picker` (wired in Task 6)

- [ ] **Step 1: Write picker view test**

Append to `blowcomotion/tests/test_drive_sync.py`:

```python
from unittest.mock import patch
from django.contrib.auth import get_user_model
from django.test import Client


class TestPickerView(TestCase):
    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_superuser("admin", "admin@test.com", "password")
        self.client = Client()
        self.client.login(username="admin", password="password")

    @patch("blowcomotion.views_chart_import.list_song_folders")
    @override_settings(GDRIVE_CHARTS_FOLDER_ID="root_folder_id")
    def test_picker_lists_folders(self, mock_list):
        mock_list.return_value = [{"id": "f1", "name": "Soul Finger"}]
        response = self.client.get("/cms/chart-import/")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Soul Finger")

    def test_picker_requires_login(self):
        response = Client().get("/cms/chart-import/")
        self.assertNotEqual(response.status_code, 200)
```

Add `from django.test import override_settings` at the top of the test file imports.

- [ ] **Step 2: Run to verify fail**

```bash
python manage.py test blowcomotion.tests.test_drive_sync.TestPickerView
```

Expected: 404 (view not wired yet — will pass after Task 6)

- [ ] **Step 3: Create views_chart_import.py**

Create `blowcomotion/views_chart_import.py`:

```python
import logging
import io
from datetime import datetime, timezone

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.files.base import ContentFile
from django.http import HttpResponseForbidden
from django.shortcuts import redirect, render
from django.conf import settings
from wagtail.documents import get_document_model

from blowcomotion.drive_sync import (
    ARCHIVE_FOLDERS,
    EXCLUDE_FOLDERS,
    AMBIGUOUS_HINTS,
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
```

- [ ] **Step 4: Create picker template**

Create `blowcomotion/templates/chart_import/picker.html`:

```html
{% extends "wagtailadmin/base.html" %}
{% load i18n %}

{% block titletag %}Import Charts from Drive{% endblock %}

{% block content %}
<div class="nice-padding">
    <h1>Import Charts from Google Drive</h1>
    <p>Select a Drive song folder to scan and review its PDF charts before importing.</p>
    <table class="listing">
        <thead>
            <tr>
                <th>Drive folder</th>
                <th>Matched song</th>
                <th>Score</th>
                <th></th>
            </tr>
        </thead>
        <tbody>
        {% for folder in folders %}
            <tr{% if folder.archived %} style="opacity:0.55" title="Archive"{% endif %}>
                <td>{{ folder.name }}{% if folder.archived %} <em>(archive)</em>{% endif %}</td>
                <td>{{ folder.matched_song.title|default:"— new song —" }}</td>
                <td>{{ folder.match_score }}</td>
                <td>
                    <a href="{% url 'chart_import_review' %}?folder_id={{ folder.id }}&folder_name={{ folder.name|urlencode }}&song_id={{ folder.matched_song.id|default:'' }}"
                       class="button button-small">Review</a>
                </td>
            </tr>
        {% empty %}
            <tr>
                <td colspan="4">No folders found. Ensure <code>GDRIVE_CHARTS_FOLDER_ID</code> is set in <code>local.py</code>.</td>
            </tr>
        {% endfor %}
        </tbody>
    </table>
</div>
{% endblock %}
```

- [ ] **Step 5: Commit**

```bash
git add blowcomotion/views_chart_import.py blowcomotion/templates/chart_import/picker.html blowcomotion/tests/test_drive_sync.py
git commit -S -m "feat: add chart import picker view and template"
```

---

### Task 5: Review + import view + template

**Files:**
- Modify: `blowcomotion/views_chart_import.py` (append `review` view)
- Create: `blowcomotion/templates/chart_import/review.html`
- Modify: `blowcomotion/tests/test_drive_sync.py` (append)

**Interfaces:**
- Consumes: `list_pdfs_in_folder`, `parse_filename`, `match_instrument`, `reconcile_file`, `_download_pdf`, `_safe_delete_document` from `drive_sync`; `Song`, `Instrument`, `Chart` models; `get_document_model()`
- Produces: `review(request)` view; URL name `chart_import_review` (wired in Task 6)

- [ ] **Step 1: Write review + import tests**

Append to `blowcomotion/tests/test_drive_sync.py`:

```python
from blowcomotion.models import Song, Instrument, Chart


class TestImportView(TestCase):
    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_superuser("admin2", "admin2@test.com", "pw")
        self.client = Client()
        self.client.login(username="admin2", password="pw")
        self.song = Song.objects.create(title="Soul Finger")
        self.instrument = Instrument.objects.create(name="Trumpet")

    @patch("blowcomotion.views_chart_import.list_pdfs_in_folder")
    def test_review_get_renders(self, mock_list):
        mock_list.return_value = [{
            "id": "f1", "name": "Soul_Finger_Tmpt_1.pdf",
            "modifiedTime": "2025-01-15T12:00:00.000Z",
            "relative_path": "Soul_Finger_Tmpt_1.pdf",
        }]
        response = self.client.get(
            f"/cms/chart-import/review/?folder_id=abc&song_id={self.song.id}"
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Soul_Finger_Tmpt_1.pdf")

    @patch("blowcomotion.views_chart_import._download_pdf")
    @patch("blowcomotion.views_chart_import.list_pdfs_in_folder")
    def test_import_post_creates_chart(self, mock_list, mock_dl):
        mock_list.return_value = [{
            "id": "f1", "name": "Soul_Finger_Tmpt_1.pdf",
            "modifiedTime": "2025-01-15T12:00:00.000Z",
            "relative_path": "Soul_Finger_Tmpt_1.pdf",
        }]
        mock_dl.return_value = b"%PDF-1.4 test content"

        response = self.client.post("/cms/chart-import/review/", {
            "song_id": self.song.id,
            "folder_id": "abc",
            "rows": ["0"],
            "row_0_file_id": "f1",
            "row_0_filename": "Soul_Finger_Tmpt_1.pdf",
            "row_0_modified": "2025-01-15T12:00:00.000Z",
            "row_0_instrument_id": self.instrument.id,
            "row_0_part": "1st Trumpet",
            "row_0_chart_id": "",
        })
        self.assertEqual(Chart.objects.filter(song=self.song, instrument=self.instrument).count(), 1)
```

- [ ] **Step 2: Run to verify fail**

```bash
python manage.py test blowcomotion.tests.test_drive_sync.TestImportView
```

Expected: 404 (URL not wired yet)

- [ ] **Step 3: Append review view to views_chart_import.py**

```python
@login_required
def review(request):
    if not _admin_required(request):
        return HttpResponseForbidden()

    Document = get_document_model()
    instruments = list(Instrument.objects.all())

    if request.method == "POST":
        song_id = request.POST.get("song_id")
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

        tuple_charts = [
            c for c in existing_charts
            if matched_inst and c.instrument_id == matched_inst.id
        ]
        result = reconcile_file(drive_file, parsed, tuple_charts)

        part = ""
        if matched_inst and parsed.part_ordinal:
            part = f"{parsed.part_ordinal} {matched_inst.name}"

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
```

- [ ] **Step 4: Create review template**

Create `blowcomotion/templates/chart_import/review.html`:

```html
{% extends "wagtailadmin/base.html" %}
{% load i18n %}

{% block titletag %}Review Charts — {{ folder_name }}{% endblock %}

{% block content %}
<div class="nice-padding">
    <h1>Review Charts: {{ folder_name }}</h1>
    <form method="post">
        {% csrf_token %}
        <input type="hidden" name="folder_id" value="{{ folder_id }}">

        <div style="margin-bottom:1rem">
            <label><strong>Song:</strong>
                <select name="song_id">
                    <option value="">— create new song "{{ folder_name }}" —</option>
                    {% for s in songs %}
                    <option value="{{ s.id }}" {% if song and song.id == s.id %}selected{% endif %}>{{ s.title }}</option>
                    {% endfor %}
                </select>
            </label>
        </div>

        <table class="listing">
            <thead>
                <tr>
                    <th>Import?</th>
                    <th>File</th>
                    <th>Status</th>
                    <th>Instrument</th>
                    <th>Part</th>
                    <th>Action</th>
                </tr>
            </thead>
            <tbody>
            {% for row in rows %}
            {% with i=forloop.counter0 %}
            {% if row.reconcile.apply != "noop" %}
            <tr>
                <td><input type="checkbox" name="rows" value="{{ i }}"
                    {% if row.reconcile.apply == "auto" %}checked{% endif %}></td>
                <td title="{{ row.drive_file.relative_path }}">{{ row.drive_file.name }}</td>
                <td>
                    <span class="tag
                        {% if row.reconcile.reason == 'Exact' %}tag--teal
                        {% elif row.reconcile.reason == 'High' %}tag--primary
                        {% elif row.reconcile.reason == 'Needs review' %}tag--warning
                        {% else %}tag--salmon{% endif %}">
                        {{ row.reconcile.reason }}
                    </span>
                </td>
                <td>
                    {% if row.inst_conf == "high" and row.instrument %}
                        <input type="hidden" name="row_{{ i }}_instrument_id" value="{{ row.instrument.id }}">
                        {{ row.instrument.name }}
                    {% else %}
                        <select name="row_{{ i }}_instrument_id">
                            {% for inst in instruments %}
                            <option value="{{ inst.id }}"
                                {% if row.instrument and row.instrument.id == inst.id %}selected{% endif %}>
                                {{ inst.name }}
                            </option>
                            {% endfor %}
                        </select>
                    {% endif %}
                </td>
                <td><input type="text" name="row_{{ i }}_part" value="{{ row.part }}"></td>
                <td>{% if row.existing_chart %}update{% else %}new{% endif %}</td>
                <input type="hidden" name="row_{{ i }}_file_id" value="{{ row.drive_file.id }}">
                <input type="hidden" name="row_{{ i }}_filename" value="{{ row.drive_file.name }}">
                <input type="hidden" name="row_{{ i }}_modified" value="{{ row.drive_file.modifiedTime }}">
                <input type="hidden" name="row_{{ i }}_chart_id" value="{{ row.existing_chart.id|default:'' }}">
            </tr>
            {% endif %}
            {% endwith %}
            {% endfor %}
            </tbody>
        </table>

        <div style="margin-top:1rem">
            <button type="submit" class="button">Import selected</button>
            <a href="{% url 'chart_import_picker' %}" class="button button-secondary">Cancel</a>
        </div>
    </form>
</div>
{% endblock %}
```

- [ ] **Step 5: Commit**

```bash
git add blowcomotion/views_chart_import.py blowcomotion/templates/chart_import/ blowcomotion/tests/test_drive_sync.py
git commit -S -m "feat: add chart import review and import views"
```

---

### Task 6: Wagtail hooks — register URLs + menu item

**Files:**
- Modify: `blowcomotion/wagtail_hooks.py`

**Interfaces:**
- Consumes: `picker`, `review` from `views_chart_import.py`
- Produces: `/cms/chart-import/` and `/cms/chart-import/review/` live in the Wagtail admin; "Import Charts from Drive" in the sidebar

- [ ] **Step 1: Add URL registration to wagtail_hooks.py**

Open `blowcomotion/wagtail_hooks.py`. Find the existing `@hooks.register("register_admin_urls")` decorators and add alongside them:

```python
@hooks.register("register_admin_urls")
def register_chart_import_urls():
    from django.urls import path
    from blowcomotion import views_chart_import
    return [
        path("chart-import/", views_chart_import.picker, name="chart_import_picker"),
        path("chart-import/review/", views_chart_import.review, name="chart_import_review"),
    ]
```

- [ ] **Step 2: Add menu item**

In the same file, alongside the existing `@hooks.register("register_admin_menu_item")` calls (or the submenu section for Library/Exports), add:

```python
@hooks.register("register_admin_menu_item")
def register_chart_import_menu_item():
    from wagtail.admin.menu import MenuItem
    return MenuItem(
        "Import Charts from Drive",
        "/cms/chart-import/",
        icon_name="doc-full",
        order=901,
    )
```

- [ ] **Step 3: Start dev server and smoke-test**

```bash
python manage.py runserver
```

Open `http://localhost:8000/cms/`. Verify:
1. "Import Charts from Drive" appears in the sidebar.
2. Clicking it loads the picker page without a 500 error.
3. Without `GDRIVE_CHARTS_FOLDER_ID` configured, it shows "No folders found" message.

- [ ] **Step 4: Run all view tests now that URLs are registered**

```bash
python manage.py test blowcomotion.tests.test_drive_sync.TestPickerView blowcomotion.tests.test_drive_sync.TestImportView
```

Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add blowcomotion/wagtail_hooks.py
git commit -S -m "feat: register chart import admin URLs and menu item"
```

---

### Task 7: `sync_charts` management command

**Files:**
- Create: `blowcomotion/management/commands/sync_charts.py`
- Modify: `blowcomotion/tests/test_drive_sync.py` (append)

**Interfaces:**
- Consumes: `list_pdfs_in_folder`, `parse_filename`, `match_instrument`, `reconcile_file`, `_download_pdf`, `_safe_delete_document`, `_get_drive_service` from `drive_sync`; `Chart`, `Instrument`, `Song` from models
- Produces: `python manage.py sync_charts [--dry-run] [--song-id=N]`

- [ ] **Step 1: Write command tests**

Append to `blowcomotion/tests/test_drive_sync.py`:

```python
from django.core.management import call_command
from io import StringIO


class TestSyncChartsCommand(TestCase):
    def setUp(self):
        self.song = Song.objects.create(title="Soul Finger")
        self.instrument = Instrument.objects.create(name="Trumpet")

    @patch("blowcomotion.management.commands.sync_charts.list_pdfs_in_folder")
    @patch("blowcomotion.management.commands.sync_charts._download_pdf")
    @patch("blowcomotion.management.commands.sync_charts._get_drive_service")
    @override_settings(GDRIVE_CHARTS_FOLDER_ID="root_id")
    def test_dry_run_makes_no_writes(self, mock_service, mock_dl, mock_list):
        mock_list.return_value = []
        mock_service.return_value = MagicMock()
        initial = Chart.objects.count()
        call_command("sync_charts", "--dry-run", stdout=StringIO())
        mock_dl.assert_not_called()
        self.assertEqual(Chart.objects.count(), initial)

    @patch("blowcomotion.management.commands.sync_charts.list_pdfs_in_folder")
    @patch("blowcomotion.management.commands.sync_charts._download_pdf")
    @patch("blowcomotion.management.commands.sync_charts._get_drive_service")
    @override_settings(GDRIVE_CHARTS_FOLDER_ID="root_id")
    def test_exact_match_updates_chart(self, mock_service, mock_dl, mock_list):
        import datetime
        from wagtail.documents.models import Document as WagtailDocument

        mock_dl.return_value = b"%PDF-1.4 updated"

        old_doc = WagtailDocument(title="old.pdf")
        old_doc.file.save("old.pdf", ContentFile(b"%PDF-1.4 old"), save=True)
        old_time = datetime.datetime(2025, 1, 1, tzinfo=datetime.timezone.utc)
        chart = Chart.objects.create(
            song=self.song,
            instrument=self.instrument,
            part="1st Trumpet",
            pdf=old_doc,
            drive_file_id="file123",
            drive_modified_time=old_time,
        )

        parent_mock = MagicMock()
        parent_mock.files.return_value.get.return_value.execute.return_value = {
            "parents": ["song_folder_id"]
        }
        mock_service.return_value = parent_mock
        mock_list.return_value = [{
            "id": "file123",
            "name": "Soul_Finger_Tmpt_1.pdf",
            "modifiedTime": "2025-06-01T12:00:00.000Z",
            "relative_path": "Soul_Finger_Tmpt_1.pdf",
        }]

        call_command("sync_charts", stdout=StringIO())
        chart.refresh_from_db()
        self.assertNotEqual(chart.pdf_id, old_doc.id)
```

- [ ] **Step 2: Run to verify fail**

```bash
python manage.py test blowcomotion.tests.test_drive_sync.TestSyncChartsCommand
```

Expected: `ImportError` (command not created yet)

- [ ] **Step 3: Create the command**

Create `blowcomotion/management/commands/sync_charts.py`:

```python
import logging
from datetime import datetime

from django.conf import settings
from django.core.files.base import ContentFile
from django.core.management.base import BaseCommand
from wagtail.documents import get_document_model

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
```

- [ ] **Step 4: Run command tests**

```bash
python manage.py test blowcomotion.tests.test_drive_sync.TestSyncChartsCommand
```

Expected: all pass.

- [ ] **Step 5: Smoke test**

```bash
python manage.py sync_charts --dry-run
```

Expected: exits cleanly with "GDRIVE_CHARTS_FOLDER_ID not configured" (since local.py likely doesn't have it yet) OR "[dry-run] would update..." if configured.

- [ ] **Step 6: Run full test suite**

```bash
python manage.py test blowcomotion.tests.test_drive_sync
```

Expected: all tests pass.

- [ ] **Step 7: Commit**

```bash
git add blowcomotion/management/commands/sync_charts.py blowcomotion/tests/test_drive_sync.py
git commit -S -m "feat: add sync_charts management command"
```

---

## Post-implementation: Local.py config

Add to `local.py` (not committed):

```python
GDRIVE_API_KEY = "AIza..."                   # restricted to Drive API only
GDRIVE_CHARTS_FOLDER_ID = "1i4K4ifpAtCPmjIa-uK74Q3RG-v5D4Jqr"
```

Then verify the picker loads real Drive folders:

```bash
python manage.py runserver
# Open http://localhost:8000/cms/chart-import/
```

## PythonAnywhere scheduled task

After deploying to production, add a scheduled task in the PythonAnywhere dashboard:

```
/path/to/virtualenv/bin/python /path/to/manage.py sync_charts
```

Recommended cadence: daily. The `--dry-run` flag is safe to test on production first.
