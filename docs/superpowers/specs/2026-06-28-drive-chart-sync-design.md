# Google Drive Chart Sync — Design

**Issue:** https://github.com/Blowcomotion/blowcomotion.org/issues/221
**Date:** 2026-06-28
**Status:** Approved design, pending spec review

## Problem

Charts in the database go stale. The band's composers/arrangers maintain music
notation in a **public Google Drive folder**
(`https://drive.google.com/drive/u/0/folders/1i4K4ifpAtCPmjIa-uK74Q3RG-v5D4Jqr`),
re-exporting parts whenever a chart changes. Creating and updating `Chart`
objects by hand in the Wagtail CMS is tedious, and the arrangers will not log
into the CMS. As a result the `ChartLibraryBlock` UI (which members like) shows
out-of-date charts.

We need to (1) pull chart PDFs from the Drive folder via the Drive API, (2)
auto-assign each PDF to a `Song`, `Instrument`, and `part` as automatically as
possible, and (3) keep charts fresh as the Drive contents change — across
arrangers with inconsistent update habits.

## Goals

- Pick a song from the Drive folder in a Wagtail admin UI and import its charts.
- Auto-match each PDF to `(song, instrument, part)`; confirm/correct the
  uncertain ones in a review screen before anything is written.
- Keep already-mapped charts fresh automatically (scheduled), without guessing.
- Never spawn duplicate Songs/Instruments from fuzzy filename variants.

## Non-goals

- No OAuth / service-account / per-user Drive auth. Public folder + API key only.
- No in-CMS version history of charts. Drive is the source of version truth.
- The planned "conductor chart" boolean refactor on `Chart` is **out of scope**.
  Conductor/full-score PDFs map to the existing `Conductor` instrument, matching
  how the current production data is organized.

## Decisions (from brainstorming)

| Topic | Decision |
|---|---|
| Sync timing | Combination: scheduled auto-refresh **and** manual "sync now". |
| Auth | Public folder + restricted **API key** (any GCP project, not the folder owner). |
| Matching | Manual sync uses a **review-and-confirm** screen; auto-refresh never guesses. |
| Missing Song | Fuzzy-match folder to existing `Song` first; auto-create only when no match. |
| Missing/ambiguous Instrument | Dropdown of existing instruments + explicit "create new 'X'". |
| Folder scope | Recurse + flatten; skip `01 -Warmups`/`03 - Resources`; `ZZArchive` shown but de-emphasized. |
| Full scores / conductor sheets | Map to existing `Conductor` instrument, blank part. Multiple allowed per song. |
| PDF update | New Wagtail Document per change, repoint Chart, **delete old Document + file**. |
| Refresh identity | Combination of `file_id`/`md5` (exact) + `(song, instrument, part)` tuple (fallback), with confidence. |
| Drive client | `google-api-python-client` (new dependency), API-key mode (no OAuth). |

## Architecture (Approach 1: shared module + admin view + command)

```
blowcomotion/
  services/drive_sync.py            # core: Drive client, parser, matcher, reconciler
  views_chart_import.py             # admin views: picker -> review -> import
  wagtail_hooks.py                  # register admin URLs + menu item (existing file)
  templates/chart_import/
    picker.html                     # list Drive song folders -> matched Song
    review.html                     # per-file review table w/ confidence
  management/commands/sync_charts.py  # cron entry point (auto-refresh)
```

One core module; two thin callers (admin view, management command) share the
same parser/matcher/reconciler so interactive and automatic paths never diverge.
Mirrors existing repo patterns: `wagtail_hooks.py`, management commands, and the
`CachedGig` external-sync precedent.

## Configuration

In `local.py` (secrets, not committed), mirroring the existing `GIGO_*` pattern:

```python
GDRIVE_API_KEY = "AIza..."                                # restricted to Drive API
GDRIVE_CHARTS_FOLDER_ID = "1i4K4ifpAtCPmjIa-uK74Q3RG-v5D4Jqr"
GDRIVE_EXCLUDE_FOLDERS = ["01 -Warmups and Exercises", "03 - Resources-Reference"]
GDRIVE_ARCHIVE_FOLDERS = ["ZZArchive - INACTIVE"]         # shown but de-emphasized
```

Drive client is created with `build('drive', 'v3', developerKey=GDRIVE_API_KEY)`
— **no OAuth flow**. (The official Drive quickstart shows OAuth; we use only the
API-key path for the public folder.)

## Model changes (`Chart`)

Add three nullable fields to anchor refresh; one migration:

- `drive_file_id` — `CharField(max_length=255, null=True, blank=True, db_index=True)`
  The Drive file last imported for this chart. Exact fast-path anchor.
- `drive_md5` — `CharField(max_length=64, null=True, blank=True)`
  Last-synced `md5Checksum`; a change means the file content changed in place.
- `drive_modified_time` — `DateTimeField(null=True, blank=True)`
  Drive `modifiedTime` of the imported file; the newest-wins tiebreaker when
  several files map to one `(song, instrument, part)` tuple.

No `is_conductor_chart` field (out of scope). The `(song, instrument, part)`
fallback identity uses the existing FK + CharField fields.

## Filename parsing & matching (`drive_sync.py`)

Parsing is heuristic; **every result is overridable in the review screen**, so a
wrong guess costs one dropdown, never a bad write.

- **Instrument alias map** — explicit dict built from analyzing the real Drive
  filenames against the production instrument list. Known mappings include:
  `Horn_in_F`/`F Horn`/`FHorn` -> French Horn/Mellophone; `Tuba` -> Tuba/Sousaphone;
  `Cowbell` -> Cow Bell; `Tmpt`/`Tpet` -> Trumpet; `Bari`/`Bari Sax` -> Baritone Saxophone;
  `Clrnt` -> Clarinet; `Tnr` -> Tenor Saxophone; `Drums`/`4-Piece_Drum_Kit` -> Drum Set.
  (`Baritone` alone is genuinely ambiguous across 3 DB instruments -> always
  routed to the review dropdown, never auto-resolved.)
- **Part extraction** — trailing `_1`/`1`/`_2`/`2nd` etc. produces the DB's
  convention: `"1st <Instrument>"`, `"2nd <Instrument>"`. No number -> blank part
  (matching how single-part charts are stored today).
- **Score / conductor detection** — keywords `score`, `conductor`, `full`,
  `all parts` -> `Conductor` instrument, blank part. Multiple allowed per song.
- **Song matching** — fuzzy-match the Drive folder name to existing `Song.title`
  using `difflib` (stdlib). High-similarity -> pre-selected existing song;
  low -> "create new song '<folder name>'" offered in the picker. Prevents
  duplicates like Drive `Soulfinger` vs DB `Soul Finger`.
- **Fuzzy fallback** — `difflib.SequenceMatcher` similarity against instrument
  names for anything the alias map misses; drives the confidence flag.

No new dependency for matching — `difflib` is stdlib.

## Reconciliation engine (the core of refresh)

Arrangers behave inconsistently: some overwrite files in place, some drop a new
dated set alongside the old (e.g. `Brick House 1-15-...` and `Brick House
2-26-25-...` coexisting in one folder), some rename, some drop individual files.
The reconciler keys on **both** anchors and emits a proposed action + confidence
per Drive file:

| Situation | Action | Confidence |
|---|---|---|
| Stored `file_id` exists, **md5 changed** | refresh PDF (in-place edit) | **Exact** |
| Stored `file_id` gone, **one** new file parses to same `(song, instrument, part)` | refresh PDF (rename/re-export) | **High** |
| **Multiple** files map to one tuple | newest `modifiedTime` wins; others flagged | **Needs review** |
| New file, no matching tuple | create new chart | **Manual only** |
| Stored `file_id` exists, md5 unchanged | no-op | — |

Confidence is the gate between automatic and review (below).

## Data flow — manual sync (admin)

1. **Pick a song.** Admin opens "Import Charts from Drive". List top-level
   folders via `files.list?q='<FOLDER_ID>' in parents`. Each folder is
   fuzzy-matched to a `Song`; picker shows `Drive folder -> matched Song (or NEW)`.
   Excluded folders hidden; archive folders shown de-emphasized.
2. **Scan.** On selecting a song, recurse all PDFs under that folder (flattened,
   relative path retained). Parse each filename; match instrument; run the
   reconciler against existing charts for that song.
3. **Review screen** — one row per PDF:
   - confidence badge (Exact / High / Needs review / New) + relative path
   - instrument: pre-filled when confident; dropdown (existing + "create new 'X'")
     when ambiguous
   - part: editable text, pre-filled per convention
   - score/conductor rows pre-set to `Conductor`, blank part
   - action shown: "new" vs "update existing" vs "skip"
   - per-row **skip** checkbox; newest-wins pre-selected among duplicate tuples
   - song match confirmed/overridden at top (existing `Song` dropdown or "create new")
4. **Import.** For each non-skipped row: download the PDF, create a Wagtail
   Document, create/update the `Chart`, store `drive_file_id`/`drive_md5`/
   `drive_modified_time`. On update: repoint the Chart to the new Document, then
   delete the old Document **and its file** — **only after** the new Document is
   confirmed saved, and **only if** the old Document is not referenced elsewhere
   (Wagtail rich text / StreamField usage check). Charts use `related_name="+"`
   so PDFs are normally exclusive, but the hard delete is the one irreversible
   step and gets this guard.

## Data flow — auto-refresh (cron)

`python manage.py sync_charts` — runs the reconciler across every `Chart` with a
`drive_file_id` (optionally scoped to one song):

- **Auto-applies** only **Exact** and unambiguous **High** confidence actions
  (refresh PDF: new Document, repoint, delete old per the same guard above).
- **Never** creates new charts, creates instruments, or applies "Needs review" /
  "Manual only" actions. These are **logged** as "N charts need review" for the
  next manual sync.
- Flags: `--song "Title"` to scope; `--dry-run` to print proposed actions
  without writing.
- Failure handling: Drive unreachable / quota error -> log + non-zero exit, no
  partial writes. Runs as a PythonAnywhere scheduled task.

## Error handling

- Drive API unreachable / quota exceeded: manual path surfaces the error in the
  UI; cron path logs and exits non-zero. No partial chart writes either way.
- Download failure mid-import: that row fails loudly; other rows proceed. The old
  Document is deleted only after the replacement is confirmed saved.
- Unknown instrument with no confident match: routed to the review dropdown
  (manual) or skipped+logged (auto). Never auto-created.

## Testing

- **Filename-parser unit tests** — table of real Drive filenames -> expected
  `(instrument, part, is_score)`.
- **Matcher tests** — against a fixture instrument list mirroring production
  (includes the ambiguous `Baritone*` trio and alias cases).
- **Reconciler tests** — each row of the confidence table above, including the
  Brick House multi-dated-set case.
- **Import test** — mocked Drive `files.list`/`files.get`/download responses;
  asserts Document creation, Chart create/update, old-Document deletion + guard.
- **Parser validation against production data** — a `--validate` mode (or a
  one-off script) that dry-runs the parser over the local Drive copy and reports
  what fraction of parsed `(instrument, part)` reproduces the 915 existing
  production charts. This measures whether the heuristic actually works far
  better than a hand-picked unit table; run it before trusting auto-refresh.
- Run via `python manage.py test`. Migration reviewed per repo conventions
  (wagtail-migration-reviewer) before commit.

## Open verification (pre-implementation)

- Confirm API-key `files.list` works for **listing children** of the public
  folder (Google is occasionally finicky about listing vs. fetching-by-id for
  public folders). Tested early with the real key; fallback is fetching the file
  tree by known IDs with the same key — still no owner involvement.

## Dependencies

- `google-api-python-client` (new) — official Drive client, API-key mode.
- `difflib` (stdlib) — fuzzy matching.
- No other new dependencies; `requests` already present if a REST fallback is
  ever needed.
