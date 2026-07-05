# Hybrid App Split Implementation Plan (Issue #312)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Split the `blowcomotion` monolith into five domain Django apps (`gigs`, `attendance`, `charts`, `instruments`, `members`) holding views/forms/urls/templates/tests/commands, while ALL models stay in the `blowcomotion` app (split into a `models/` package) so the database is never touched.

**Architecture:** Pure code moves — no behavior changes, no renames of functions/classes, no model app-label changes, therefore no schema migrations. New apps have NO `models.py` and NO `migrations/`. Wagtail admin wiring (`wagtail_hooks.py`, `snippet_viewsets.py`, `chooser_viewsets.py`) stays centralized in `blowcomotion` and imports view functions from the domain apps. Templates move into `<app>/templates/<same-subpath>/` so every template path string keeps resolving via `APP_DIRS`.

**Tech Stack:** Django 5 + Wagtail. Test runner: `python manage.py test`. Import sorting: isort (pre-commit hook).

## Global Constraints

- **Zero DB impact:** `python manage.py makemigrations --check --dry-run` must print "No changes detected" at the end of every task. Exception: Task 7 (blocks split) may generate ONE state-only migration — see that task for the exact acceptance check. If any other task generates migration changes, STOP and fix; do not commit a migration.
- **Models never move apps.** All model classes keep `app_label` `blowcomotion`. New apps must not contain a `models.py` or `migrations/` directory.
- **Pure moves:** moved functions/classes are copied byte-identical (imports at the top of the file are the only lines you adapt). No refactoring, no renaming, no "improvements".
- **URL names are frozen.** Every `name="..."` in URL patterns must survive exactly — templates and views call `reverse()`/`{% url %}` on them.
- **Template path strings are frozen.** A template rendered as `"attendance/reports.html"` must move to `attendance/templates/attendance/reports.html` (same trailing path, new app dir). `APP_DIRS=True` is already set.
- **Tests:** the full suite (`python manage.py test`) must pass at the end of every task with the SAME test count as the baseline recorded in Task 1. When moving a test file, update `mock.patch("...")` target strings — patch targets point at the module where the name is *used*, so a function moved to `gigs.views` must be patched as `gigs.views.<name>`.
- **Commits:** GPG-signed (`git commit -S`), conventional prefix (`refactor:`), no emojis, no Co-Authored-By. If the isort pre-commit hook modifies files, `git add -u` and re-run the commit.
- **Use `git mv`** for whole-file moves (preserves history). For partial extractions, edit files normally.
- **Do NOT run `collectstatic`** — not needed for local dev. Static files under `blowcomotion/static/` do not move.
- **New app skeleton = one file:** `<app>/__init__.py` (empty) plus the app name in `INSTALLED_APPS`. No `apps.py` needed (no models, default AppConfig is fine).
- Work on branch `refactor/312-hybrid-apps` off `development`.

## Target layout (end state)

```
blowcomotion/          # CMS core: models/ package, blocks/ package, form pipeline,
                       # wagtail_hooks, snippet/chooser viewsets, templatetags, static,
                       # settings, root urls, base templates, migrations (unchanged)
gigs/                  # GigoGig API: gigo.py helpers, sync admin view, gigs_for_date
attendance/            # capture, reports, inactive members, attendance forms/commands
charts/                # chart_api, drive_sync, chart import views, sync/export commands
instruments/           # rental dashboard + CTA views, library views, patreon client
members/               # member portal, auth, signup form, birthdays, middleware
```

Dissolved entirely: `blowcomotion/utils.py`, `blowcomotion/forms.py`, `blowcomotion/member_views.py`, `blowcomotion/member_auth.py`, `blowcomotion/member_forms.py`, `blowcomotion/member_urls.py`, `blowcomotion/middleware.py`, `blowcomotion/patreon_client.py`, `blowcomotion/chart_api.py`, `blowcomotion/drive_sync.py`, `blowcomotion/views_chart_import.py`.

Remaining in `blowcomotion/views.py` (~1,100 lines): the public form pipeline (`process_form`, `_process_form_submission`, `_process_member_signup`, `_validate_recaptcha`, `_get_form_recipients`, `_send_form_email`, `_create_email_message`, `_get_success_message`), `dump_data`, `fetch_embed_data`.

Line numbers below are as of commit `56f70e4` and drift as tasks complete — **symbol names are authoritative**, line numbers are hints.

---

### Task 1: Baseline + extract `gigs` app

**Files:**
- Create: `gigs/__init__.py`, `gigs/views.py`, `gigs/gigo.py`, `gigs/management/__init__.py`, `gigs/management/commands/__init__.py`, `gigs/tests/__init__.py`
- Move: `blowcomotion/management/commands/sync_gigs.py` → `gigs/management/commands/sync_gigs.py`
- Move: `blowcomotion/templates/admin/sync_gigs.html`, `blowcomotion/templates/admin/sync_gigs_result.html` → `gigs/templates/admin/`
- Move: `blowcomotion/tests/test_sync_gigs_command.py`, `blowcomotion/tests/test_sync_gigs_admin_view.py` → `gigs/tests/`
- Modify: `blowcomotion/settings/base.py` (INSTALLED_APPS), `blowcomotion/urls.py`, `blowcomotion/wagtail_hooks.py`, `blowcomotion/views.py`, `blowcomotion/utils.py`

**Interfaces:**
- Produces: `gigs.gigo.convert_utc_gig_to_central(gig)` and `gigs.gigo.make_gigo_api_request(endpoint, timeout=10, retries=0, method='GET', data=None)` — signatures unchanged from `blowcomotion/utils.py`. `gigs.views.gigs_for_date` (view, URL name `gigs-for-date`) and `gigs.views.sync_gigs_admin` — Task 2's `attendance/urls.py` and `wagtail_hooks.py` import these.

- [ ] **Step 1: Record baseline**

```bash
git checkout -b refactor/312-hybrid-apps development
python manage.py test 2>&1 | tail -3
python manage.py makemigrations --check --dry-run
```
Record the "Ran N tests" count — every later task must end at the same N, status OK. Expect "No changes detected".

- [ ] **Step 2: Create the app and register it**

```bash
mkdir -p gigs/management/commands gigs/tests gigs/templates/admin
touch gigs/__init__.py gigs/management/__init__.py gigs/management/commands/__init__.py gigs/tests/__init__.py
```

In `blowcomotion/settings/base.py`, add to the top of `INSTALLED_APPS`:

```python
INSTALLED_APPS = [
    "blowcomotion",
    "gigs",
    "search",
    ...
```

- [ ] **Step 3: Create `gigs/gigo.py`**

Move `convert_utc_gig_to_central` (utils.py:16-61) and `make_gigo_api_request` (utils.py:236-313) verbatim from `blowcomotion/utils.py` into `gigs/gigo.py`, carrying only the imports those two functions need. Delete them from `blowcomotion/utils.py`.

- [ ] **Step 4: Create `gigs/views.py`**

Move `sync_gigs_admin` (views.py:745-798) and `gigs_for_date` (views.py:2053-2103) verbatim from `blowcomotion/views.py` into `gigs/views.py`. Carry the imports they need; gigo helpers now come `from gigs.gigo import convert_utc_gig_to_central`. Models still come `from blowcomotion.models import CachedGig, ...`.

- [ ] **Step 5: Move the command and templates**

```bash
git mv blowcomotion/management/commands/sync_gigs.py gigs/management/commands/sync_gigs.py
git mv blowcomotion/templates/admin/sync_gigs.html gigs/templates/admin/sync_gigs.html
git mv blowcomotion/templates/admin/sync_gigs_result.html gigs/templates/admin/sync_gigs_result.html
rmdir blowcomotion/templates/admin
```

In `gigs/management/commands/sync_gigs.py` change `from blowcomotion.utils import convert_utc_gig_to_central, make_gigo_api_request` → `from gigs.gigo import ...`.

- [ ] **Step 6: Update every importer of the moved names**

```bash
grep -rn "gigs_for_date\|sync_gigs_admin\|convert_utc_gig_to_central\|make_gigo_api_request" blowcomotion/ --include="*.py" | grep -v migrations
```

Expected hits to fix:
- `blowcomotion/urls.py`: add `from gigs import views as gigs_views`; change the gigs-for-date line to `path("attendance/gigs-for-date/", gigs_views.gigs_for_date, name="gigs-for-date")`.
- `blowcomotion/wagtail_hooks.py`: remove `sync_gigs_admin` from the `blowcomotion.views` import; add `from gigs.views import sync_gigs_admin`.
- `blowcomotion/views.py`: drop the now-unused `from blowcomotion.utils import convert_utc_gig_to_central, make_gigo_api_request` names IF nothing left in views.py uses them (grep inside the file first — attendance views may use them; if so import from `gigs.gigo`).
- Any other hit (e.g. `chooser_viewsets.py`): repoint to `gigs.gigo`.

- [ ] **Step 7: Move tests and fix patch targets**

```bash
git mv blowcomotion/tests/test_sync_gigs_command.py gigs/tests/
git mv blowcomotion/tests/test_sync_gigs_admin_view.py gigs/tests/
grep -n "blowcomotion\." gigs/tests/*.py
```

Update imports and every `mock.patch("blowcomotion.utils....")` / `patch("blowcomotion.views.sync_gigs_admin...")` style string to the new module paths (`gigs.gigo`, `gigs.views`). Patch strings referring to modules that did NOT move (e.g. `blowcomotion.models`) stay.

- [ ] **Step 8: Verify**

```bash
python manage.py test 2>&1 | tail -3
python manage.py makemigrations --check --dry-run
```
Expected: same N tests, OK; "No changes detected".

- [ ] **Step 9: Commit**

```bash
git add -A && git commit -S -m "refactor: extract gigs app from blowcomotion monolith"
```

---

### Task 2: Extract `attendance` app

**Files:**
- Create: `attendance/__init__.py`, `attendance/views.py`, `attendance/forms.py`, `attendance/urls.py`, `attendance/management/__init__.py`, `attendance/management/commands/__init__.py`, `attendance/tests/__init__.py`
- Move: commands `cleanup_attendance_roster.py`, `send_attendance_report.py`, `export_attendance_to_csv.py` → `attendance/management/commands/`
- Move: `blowcomotion/templates/attendance/` (whole dir incl. `partials/`) → `attendance/templates/attendance/`
- Move: `blowcomotion/tests/test_attendance_views.py`, `test_attendance_commands.py` → `attendance/tests/` (note: `test_member_attendance.py` is member-portal — it moves in Task 5, not here)
- Modify: `blowcomotion/settings/base.py`, `blowcomotion/urls.py`, `blowcomotion/forms.py`, `blowcomotion/views.py`, `blowcomotion/wagtail_hooks.py`

**Interfaces:**
- Consumes: `gigs.views.gigs_for_date` (Task 1) for the URL include.
- Produces: `attendance.views.export_attendance_csv` — `wagtail_hooks.py` imports it. URL names `attendance-main`, `attendance-reports`, `attendance-section-report`, `gigs-for-date`, `inactive-members`, `attendance-capture` all preserved.

- [ ] **Step 1: Create app skeleton** (same pattern as Task 1 Step 2) and add `"attendance"` to `INSTALLED_APPS` after `"gigs"`.

- [ ] **Step 2: Create `attendance/forms.py`**

Move `AttendanceForm` (forms.py:21), `SectionAttendanceForm` (forms.py:60), `AttendanceReportFilterForm` (forms.py:175) verbatim from `blowcomotion/forms.py`, with the imports they need. Delete them from `blowcomotion/forms.py`.

- [ ] **Step 3: Create `attendance/views.py`**

Move verbatim from `blowcomotion/views.py`: `attendance_capture` (1242), `inactive_members` (1749), `attendance_reports` (1820), `attendance_section_report_new` (1886), `export_attendance_csv` (983). Also move any module-level constants in views.py used only by these (check the constants block near the top, views.py:70-77). Forms import becomes `from attendance.forms import ...`; models stay `from blowcomotion.models import ...`.

- [ ] **Step 4: Create `attendance/urls.py`**

```python
from django.urls import path

from attendance import views
from gigs import views as gigs_views

urlpatterns = [
    path("", views.attendance_capture, name="attendance-main"),
    path("reports/", views.attendance_reports, name="attendance-reports"),
    path("reports/<str:section_slug>/", views.attendance_section_report_new, name="attendance-section-report"),
    path("gigs-for-date/", gigs_views.gigs_for_date, name="gigs-for-date"),
    path("inactive-members/", views.inactive_members, name="inactive-members"),
    path("<str:section_slug>/", views.attendance_capture, name="attendance-capture"),
]
```

In `blowcomotion/urls.py` replace the six attendance/gigs-for-date/inactive-members path lines with:

```python
path("attendance/", include("attendance.urls")),
```

Remove the now-unused `gigs_views` import from root urls if nothing else uses it.

- [ ] **Step 5: Move commands, templates, tests**

```bash
git mv blowcomotion/management/commands/cleanup_attendance_roster.py attendance/management/commands/
git mv blowcomotion/management/commands/send_attendance_report.py attendance/management/commands/
git mv blowcomotion/management/commands/export_attendance_to_csv.py attendance/management/commands/
git mv blowcomotion/templates/attendance attendance/templates/attendance
git mv blowcomotion/tests/test_attendance_views.py attendance/tests/
git mv blowcomotion/tests/test_attendance_commands.py attendance/tests/
```

Update imports/patch targets in the moved commands and tests (`blowcomotion.views.attendance_*` → `attendance.views.*`, `blowcomotion.forms.AttendanceForm` → `attendance.forms.AttendanceForm`).

- [ ] **Step 6: Update wagtail_hooks and stragglers**

```bash
grep -rn "attendance_capture\|attendance_reports\|attendance_section_report_new\|inactive_members\|export_attendance_csv\|AttendanceForm\|SectionAttendanceForm\|AttendanceReportFilterForm" blowcomotion/ --include="*.py" | grep -v migrations
```
Fix each: `wagtail_hooks.py` imports `export_attendance_csv` from `attendance.views`; `blowcomotion/views.py` drops the attendance form imports; `blowcomotion/tests/test_export_views_permissions.py` (stays central) repoints any patched/imported attendance names.

- [ ] **Step 7: Verify** — same commands/expectations as Task 1 Step 8 (same N, OK, no migration changes).

- [ ] **Step 8: Commit**

```bash
git add -A && git commit -S -m "refactor: extract attendance app from blowcomotion monolith"
```

---

### Task 3: Extract `charts` app

**Files:**
- Create: `charts/__init__.py`, `charts/urls.py`, `charts/views.py`, `charts/management/...`, `charts/tests/__init__.py`
- Move (whole files): `blowcomotion/chart_api.py` → `charts/api.py`; `blowcomotion/drive_sync.py` → `charts/drive_sync.py`; `blowcomotion/views_chart_import.py` → `charts/import_views.py`
- Move: commands `sync_charts.py`, `export_charts_to_csv.py`, `populate_audio_durations.py` → `charts/management/commands/`
- Move: `blowcomotion/templates/chart_import/` → `charts/templates/chart_import/`
- Move: tests `test_chart_api.py`, `test_chart_import_views.py`, `test_drive_sync.py`, `test_export_charts_command.py`, `test_chart_model.py` → `charts/tests/`
- Modify: `blowcomotion/settings/base.py`, `blowcomotion/urls.py`, `blowcomotion/wagtail_hooks.py`, `blowcomotion/views.py`

**Interfaces:**
- Produces: `charts.views.export_charts_csv` and `charts.import_views.picker`/`review` — imported by `wagtail_hooks.py`. URL names `chart-instruments-list`, `chart-songs-for-instrument`, `chart-songs`, `chart-instruments`, `chart-parts` preserved.

- [ ] **Step 1: Skeleton + INSTALLED_APPS** (`"charts"`).

- [ ] **Step 2: Move the three modules**

```bash
git mv blowcomotion/chart_api.py charts/api.py
git mv blowcomotion/drive_sync.py charts/drive_sync.py
git mv blowcomotion/views_chart_import.py charts/import_views.py
```
In `charts/import_views.py`: `from blowcomotion.drive_sync import ...` → `from charts.drive_sync import ...`.

- [ ] **Step 3: Create `charts/views.py`** — move `export_charts_csv` (views.py:1032) verbatim from `blowcomotion/views.py`.

- [ ] **Step 4: Create `charts/urls.py`**

```python
from django.urls import path

from charts import api

urlpatterns = [
    path("instruments/", api.instruments_with_charts, name="chart-instruments-list"),
    path("songs/<int:instrument_id>/", api.songs_for_instrument, name="chart-songs-for-instrument"),
    # Legacy endpoints (kept for backwards compatibility)
    path("songs/", api.songs_with_charts, name="chart-songs"),
    path("instruments/<int:song_id>/", api.instruments_for_song, name="chart-instruments"),
    path("parts/<int:song_id>/<int:instrument_id>/", api.charts_for_song_instrument, name="chart-parts"),
]
```

Root `blowcomotion/urls.py`: replace the five `charts/...` lines with `path("charts/", include("charts.urls"))`; drop the `chart_api` import.

- [ ] **Step 5: Move commands, templates, tests; fix imports**

```bash
git mv blowcomotion/management/commands/sync_charts.py charts/management/commands/
git mv blowcomotion/management/commands/export_charts_to_csv.py charts/management/commands/
git mv blowcomotion/management/commands/populate_audio_durations.py charts/management/commands/
git mv blowcomotion/templates/chart_import charts/templates/chart_import
git mv blowcomotion/tests/test_chart_api.py blowcomotion/tests/test_chart_import_views.py blowcomotion/tests/test_drive_sync.py blowcomotion/tests/test_export_charts_command.py blowcomotion/tests/test_chart_model.py charts/tests/
```
`sync_charts.py` imports `blowcomotion.drive_sync` → `charts.drive_sync`. In moved tests, update imports and patch strings (`blowcomotion.drive_sync.` → `charts.drive_sync.`, `blowcomotion.chart_api.` → `charts.api.`, `blowcomotion.views_chart_import.` → `charts.import_views.`).

- [ ] **Step 6: Update wagtail_hooks**

In `blowcomotion/wagtail_hooks.py`: `register_chart_import_urls` (line 116) does `from blowcomotion import views_chart_import` → `from charts import import_views as views_chart_import` (keep the local alias so the body is untouched); the `export_charts_csv` import moves to `from charts.views import export_charts_csv`. Then sweep:

```bash
grep -rn "chart_api\|drive_sync\|views_chart_import\|export_charts_csv" blowcomotion/ --include="*.py" | grep -v migrations
```
Expected: zero hits (fix any).

- [ ] **Step 7: Verify** (same N, OK, no migration changes). **Step 8: Commit**

```bash
git add -A && git commit -S -m "refactor: extract charts app from blowcomotion monolith"
```

---

### Task 4: Extract `instruments` app

**Files:**
- Create: `instruments/__init__.py`, `instruments/views.py`, `instruments/forms.py`, `instruments/urls.py`, `instruments/management/...`, `instruments/tests/__init__.py`
- Move: `blowcomotion/patreon_client.py` → `instruments/patreon.py`
- Move: commands `check_instrument_rentals.py`, `nag_instrument_renters.py`, `validate_patreon_rentals.py`, `export_library_instruments_to_csv.py`, `migrate_primary_instruments.py` → `instruments/management/commands/`
- Move: templates `blowcomotion/templates/instrument_library/` → `instruments/templates/instrument_library/`; the four root-level `instrument_rental_*.html` → `instruments/templates/`; `blowcomotion/templates/emails/instrument_rental_request_*.txt` (4 files) → `instruments/templates/emails/`
- Move: tests `test_instrument_rental.py`, `test_instrument_rental_cta_views.py`, `test_library_rental_dashboard_permissions.py`, `test_nag_instrument_renters_command.py`, `test_export_library_instruments_command.py` → `instruments/tests/`
- Modify: `blowcomotion/settings/base.py`, `blowcomotion/urls.py`, `blowcomotion/forms.py`, `blowcomotion/views.py`, `blowcomotion/wagtail_hooks.py`, `blowcomotion/member_views.py`

**Interfaces:**
- Produces: `instruments.patreon` — same public names as `blowcomotion.patreon_client` (`check_patreon_membership`, `fetch_all_members`, `MIN_RENTAL_PLEDGE_CENTS`); `blowcomotion/views.py` (form pipeline) and `blowcomotion/member_views.py` now import from it. `instruments.views` exports for `wagtail_hooks.py`: `instrument_library_rented`, `instrument_library_available`, `instrument_library_needs_repair`, `rental_requests_dashboard`, `rental_request_review`, `rental_request_return`, `export_library_instruments_csv`. URL names `instrument-rental-staying`, `instrument-rental-patreon-updated`, `instrument-rental-return` preserved.

- [ ] **Step 1: Skeleton + INSTALLED_APPS** (`"instruments"`).

- [ ] **Step 2: Move the patreon client**

```bash
git mv blowcomotion/patreon_client.py instruments/patreon.py
grep -rln "patreon_client" blowcomotion/ --include="*.py" | grep -v migrations
```
Repoint every hit (`blowcomotion/views.py`, `blowcomotion/member_views.py`, `instruments/management/commands/validate_patreon_rentals.py` after its move) to `from instruments.patreon import ...`.

- [ ] **Step 3: Create `instruments/forms.py`** — move `LibraryInstrumentRentForm` (forms.py:474) and `LibraryInstrumentReturnForm` (forms.py:551) verbatim from `blowcomotion/forms.py`.

- [ ] **Step 4: Create `instruments/views.py`**

Move verbatim from `blowcomotion/views.py`: `instrument_library_rented` (77), `instrument_library_available` (94), `instrument_library_needs_repair` (111), `instrument_library_quick_rent` (133), `export_library_instruments_csv` (1069), `RentalRequestReviewForm` (2169), `_send_rental_approved_email` (2200), `_send_rental_denied_email` (2223), `_send_rental_returned_email` (2244), `rental_requests_dashboard` (2281), `rental_request_review` (2565), `rental_request_return` (2613), `_get_site_settings_for_view` (2673), `_get_nag_all_candidates` (2681), `_nag_cta_for_reasons` (2713), `_build_nag_email` (2723), `instrument_rental_staying` (2767), `instrument_rental_patreon_updated` (2797), `instrument_rental_return` (2827). Forms from `instruments.forms`, patreon from `instruments.patreon`, models from `blowcomotion.models`.

- [ ] **Step 5: Create `instruments/urls.py`**

```python
from django.urls import path

from instruments import views

urlpatterns = [
    path("staying/", views.instrument_rental_staying, name="instrument-rental-staying"),
    path("patreon-updated/", views.instrument_rental_patreon_updated, name="instrument-rental-patreon-updated"),
    path("return/", views.instrument_rental_return, name="instrument-rental-return"),
]
```

Root urls: replace the three `instrument-rental/...` lines with `path("instrument-rental/", include("instruments.urls"))`.

- [ ] **Step 6: Move commands, templates, tests**

```bash
git mv blowcomotion/management/commands/check_instrument_rentals.py instruments/management/commands/
git mv blowcomotion/management/commands/nag_instrument_renters.py instruments/management/commands/
git mv blowcomotion/management/commands/validate_patreon_rentals.py instruments/management/commands/
git mv blowcomotion/management/commands/export_library_instruments_to_csv.py instruments/management/commands/
git mv blowcomotion/management/commands/migrate_primary_instruments.py instruments/management/commands/
git mv blowcomotion/templates/instrument_library instruments/templates/instrument_library
mkdir -p instruments/templates/emails
git mv blowcomotion/templates/instrument_rental_staying.html blowcomotion/templates/instrument_rental_patreon_updated.html blowcomotion/templates/instrument_rental_return.html blowcomotion/templates/instrument_rental_token_error.html instruments/templates/
git mv blowcomotion/templates/emails/instrument_rental_request_approved.txt blowcomotion/templates/emails/instrument_rental_request_denied.txt blowcomotion/templates/emails/instrument_rental_request_pending.txt blowcomotion/templates/emails/instrument_rental_request_returned.txt instruments/templates/emails/
git mv blowcomotion/tests/test_instrument_rental.py blowcomotion/tests/test_instrument_rental_cta_views.py blowcomotion/tests/test_library_rental_dashboard_permissions.py blowcomotion/tests/test_nag_instrument_renters_command.py blowcomotion/tests/test_export_library_instruments_command.py instruments/tests/
```

`nag_instrument_renters.py` imports `_build_nag_email` from `blowcomotion.views` → `instruments.views`. Update all moved tests' imports and patch strings (`blowcomotion.views.` → `instruments.views.` for moved names, `blowcomotion.patreon_client.` → `instruments.patreon.`).

- [ ] **Step 7: Sweep remaining importers**

```bash
grep -rn "instrument_library_\|rental_request\|patreon_client\|LibraryInstrumentRentForm\|LibraryInstrumentReturnForm\|_build_nag_email\|instrument_rental_staying\|instrument_rental_patreon_updated\|instrument_rental_return" blowcomotion/ --include="*.py" | grep -v migrations
```
Fix `wagtail_hooks.py` (imports move to `instruments.views`), `blowcomotion/views.py` leftover imports, `member_views.py` patreon import. Note: the form pipeline's `InstrumentRentalRequestSubmission` handling stays in `blowcomotion/views.py` — only repoint its patreon import.

- [ ] **Step 8: Verify** (same N, OK, no migration changes). **Step 9: Commit**

```bash
git add -A && git commit -S -m "refactor: extract instruments app from blowcomotion monolith"
```

---

### Task 5: Extract `members` app (largest)

**Files:**
- Create: `members/__init__.py`, `members/tests/__init__.py`, `members/management/...`, `members/utils.py`, `members/birthdays.py`
- Move (whole files): `blowcomotion/member_views.py` → `members/views.py`; `blowcomotion/member_auth.py` → `members/auth.py`; `blowcomotion/member_forms.py` → `members/forms.py`; `blowcomotion/member_urls.py` → `members/urls.py`; `blowcomotion/middleware.py` → `members/middleware.py`
- Move: `MemberSignupForm` from `blowcomotion/forms.py` into `members/forms.py`; then DELETE `blowcomotion/forms.py` (must be empty of classes)
- Move: `validate_birthday` + `send_member_to_go3_band_invite` from `blowcomotion/utils.py` into `members/utils.py`; then DELETE `blowcomotion/utils.py`
- Move: from `blowcomotion/views.py`: `get_birthday` (281), `get_next_year_birthday_info` (303), `birthdays` (1960) → `members/birthdays.py`; `export_members_csv` (940) → `members/views.py`
- Move: commands `invite_members.py`, `send_monthly_birthday_summary.py`, `load_members_from_csv.py` → `members/management/commands/`
- Move: templates `blowcomotion/templates/member/` → `members/templates/member/`; `birthdays.html`, `member_signup_success.html` → `members/templates/`; emails `set_password.txt`, `email_change_confirm.txt`, `member_signup_invite.txt`, `member_signup_welcome.txt`, `monthly_birthday_summary.html`, `weekly_birthday_summary.html` → `members/templates/emails/`
- Move: tests `test_member_auth_helpers.py`, `test_member_auth_views.py`, `test_member_middleware.py`, `test_member_model.py`, `test_member_portal.py`, `test_member_attendance.py`, `test_member_signup_go3.py`, `test_birthday_command.py`, `test_birthday_views.py`, `test_export_members_command.py`, `test_invite_members_command.py` → `members/tests/`
- Modify: `blowcomotion/settings/base.py` (INSTALLED_APPS + MIDDLEWARE), `blowcomotion/urls.py`, `blowcomotion/views.py`, `blowcomotion/blocks.py`, `blowcomotion/wagtail_hooks.py`

**Interfaces:**
- Consumes: `instruments.patreon` (Task 4) — already correct inside `member_views.py` after Task 4.
- Produces: `members.forms.MemberSignupForm`, `members.forms._yesno_to_bool`, `members.auth` (all names from old `member_auth`), `members.utils.send_member_to_go3_band_invite`, `members.utils.validate_birthday` — the form pipeline in `blowcomotion/views.py` and `blocks.py` import these. `members.views.export_members_csv` for `wagtail_hooks.py`.
- Note: `members/views.py` keeps `from blowcomotion.views import _validate_recaptcha` — that helper stays in the core pipeline. This is one-directional per module (`blowcomotion.views` imports `members.auth`/`members.forms`/`members.utils`, never `members.views`), so no circular import.

- [ ] **Step 1: Skeleton + settings**

Create dirs/`__init__.py` files; add `"members"` to `INSTALLED_APPS`. In `blowcomotion/settings/base.py:68` change `"blowcomotion.middleware.MemberIdleLogoutMiddleware"` → `"members.middleware.MemberIdleLogoutMiddleware"`.

- [ ] **Step 2: Move the five member modules**

```bash
git mv blowcomotion/member_views.py members/views.py
git mv blowcomotion/member_auth.py members/auth.py
git mv blowcomotion/member_forms.py members/forms.py
git mv blowcomotion/member_urls.py members/urls.py
git mv blowcomotion/middleware.py members/middleware.py
```
Fix internal imports: `members/views.py` (`from members.auth import ...`, `from members.forms import ...`); `members/urls.py` (`from members import views as member_views` — keep the alias so pattern lines are untouched).

- [ ] **Step 3: Fold `MemberSignupForm` into `members/forms.py`**

Move `MemberSignupForm` (forms.py:205-473) verbatim into `members/forms.py`; replace its old import there (`from blowcomotion.forms import MemberSignupForm` → delete, it's now local). It keeps importing chooser widgets `from blowcomotion.chooser_viewsets import ...` and `from members.utils import validate_birthday` (after Step 4). `blowcomotion/forms.py` should now define nothing — delete it.

- [ ] **Step 4: Create `members/utils.py` and `members/birthdays.py`**

`members/utils.py`: move `validate_birthday` (utils.py:62) and `send_member_to_go3_band_invite` (utils.py:104) verbatim; delete `blowcomotion/utils.py` (must be empty).
`members/birthdays.py`: move `get_birthday`, `get_next_year_birthday_info`, `birthdays` verbatim from `blowcomotion/views.py`. Also move `export_members_csv` into `members/views.py`.

- [ ] **Step 5: Rewire root urls**

In `blowcomotion/urls.py`:

```python
from members import birthdays as member_birthday_views
...
    path("birthdays/", member_birthday_views.birthdays, name="birthdays"),
    path("member/", include("members.urls")),
```
Drop the `member_urls` import.

- [ ] **Step 6: Move commands, templates, tests**

```bash
git mv blowcomotion/management/commands/invite_members.py members/management/commands/
git mv blowcomotion/management/commands/send_monthly_birthday_summary.py members/management/commands/
git mv blowcomotion/management/commands/load_members_from_csv.py members/management/commands/
git mv blowcomotion/templates/member members/templates/member
git mv blowcomotion/templates/birthdays.html blowcomotion/templates/member_signup_success.html members/templates/
mkdir -p members/templates/emails
git mv blowcomotion/templates/emails/set_password.txt blowcomotion/templates/emails/email_change_confirm.txt blowcomotion/templates/emails/member_signup_invite.txt blowcomotion/templates/emails/member_signup_welcome.txt blowcomotion/templates/emails/monthly_birthday_summary.html blowcomotion/templates/emails/weekly_birthday_summary.html members/templates/emails/
git mv blowcomotion/tests/test_member_auth_helpers.py blowcomotion/tests/test_member_auth_views.py blowcomotion/tests/test_member_middleware.py blowcomotion/tests/test_member_model.py blowcomotion/tests/test_member_portal.py blowcomotion/tests/test_member_attendance.py blowcomotion/tests/test_member_signup_go3.py blowcomotion/tests/test_birthday_command.py blowcomotion/tests/test_birthday_views.py blowcomotion/tests/test_export_members_command.py blowcomotion/tests/test_invite_members_command.py members/tests/
```
Command import fixes: `invite_members.py` → `from members.auth import ...`; `send_monthly_birthday_summary.py` → `from members.birthdays import get_birthday, get_next_year_birthday_info`.

- [ ] **Step 7: Sweep every stale import**

```bash
grep -rn "member_views\|member_auth\|member_forms\|member_urls\|blowcomotion.middleware\|blowcomotion.utils\|blowcomotion.forms\|MemberSignupForm\|_yesno_to_bool\|send_member_to_go3_band_invite\|validate_birthday\|get_birthday\|export_members_csv" blowcomotion/ --include="*.py" | grep -v migrations
```
Expected fixes: `blowcomotion/views.py` (pipeline imports → `members.auth`, `members.forms`, `members.utils`), `blowcomotion/blocks.py:343` lazy import → `from members.forms import MemberSignupForm`, `blowcomotion/wagtail_hooks.py` (`export_members_csv` → `members.views`). Then fix imports and patch strings in all moved tests (`blowcomotion.member_auth.` → `members.auth.`, `blowcomotion.views.get_birthday` → `members.birthdays.get_birthday`, `blowcomotion.utils.send_member_to_go3_band_invite` → `members.utils....`, middleware setting override strings in `test_member_middleware.py`, etc.).

- [ ] **Step 8: Verify** (same N, OK, no migration changes). **Step 9: Commit**

```bash
git add -A && git commit -S -m "refactor: extract members app from blowcomotion monolith"
```

---

### Task 6: Split `blowcomotion/models.py` into a `models/` package

Models keep app_label `blowcomotion` — a models package inside the same app changes nothing Django cares about, as long as every class is importable from `blowcomotion.models`.

**Files:**
- Create: `blowcomotion/models/__init__.py`, `core.py`, `band.py`, `members.py`, `music.py`, `attendance.py`, `gigs.py`, `pages.py`, `instruments.py`, `submissions.py`
- Delete: `blowcomotion/models.py` (contents fully distributed)

**Interfaces:**
- Produces: `from blowcomotion.models import <AnyModel>` continues to work for all 40 classes — nothing outside this package may need changing.

Module assignment (line hints from original models.py):

| Module | Classes |
|---|---|
| `core.py` | NotificationBanner (36), SiteSettings (47), CustomImage (215), CustomRendition (233) |
| `music.py` | Chart (242), SongConductor (277), SongSoloist (282), SongVideo (287), Song (343), EventSetlistSong (399), Event (404) |
| `band.py` | Section (456), SectionInstructor (480), Instrument (489) |
| `members.py` | MemberInstrument (536), Member (545), PasswordSetToken (1091), EmailChangeToken (1104) |
| `gigs.py` | CachedGig (1117) |
| `attendance.py` | AttendanceRecord (1200) |
| `pages.py` | BasePage (1255), BlankCanvasPage (1260), WikiIndexPage (1346), WikiAuthor (1367), WikiPage (1387) |
| `instruments.py` | InstrumentStorageLocation (1413), LibraryInstrument (1429), LibraryInstrumentPhoto (1698), InstrumentRentalNagLog (1720), InstrumentHistoryLog (1741), Equipment (1813), EquipmentPhoto (1879) |
| `submissions.py` | BaseFormSubmission (1901), ContactFormSubmission, FeedbackFormSubmission, JoinBandFormSubmission, BookingFormSubmission, DonateFormSubmission, InstrumentRentalRequestSubmission |

- [ ] **Step 0: Record model-registry baseline (before touching anything)**

```bash
python -c "import django, os; os.environ.setdefault('DJANGO_SETTINGS_MODULE','blowcomotion.settings.dev'); django.setup(); from django.apps import apps; print(sorted(m.__name__ for m in apps.get_app_config('blowcomotion').get_models()))" > /tmp/models_before.txt
cat /tmp/models_before.txt
```

- [ ] **Step 1: Inventory module-level names**

```bash
grep -n "^[A-Z_]* =\|^def \|^[a-z_]* =" blowcomotion/models.py
```
Every module-level constant/helper/choices list goes into the module of its primary user; if shared across modules, put it in the module where it's defined first and import it in the others.

- [ ] **Step 2: Create the package**

Cut each class verbatim into its module per the table, each module carrying only the imports its classes need. Cross-module FKs/references import directly (e.g. `members.py` does `from blowcomotion.models.band import Instrument, Section` — or use string references `"blowcomotion.Instrument"` where the original already did; do NOT change existing string-vs-class FK style).

`blowcomotion/models/__init__.py` — explicit re-exports (this exact list):

```python
from blowcomotion.models.attendance import AttendanceRecord
from blowcomotion.models.band import Instrument, Section, SectionInstructor
from blowcomotion.models.core import (
    CustomImage,
    CustomRendition,
    NotificationBanner,
    SiteSettings,
)
from blowcomotion.models.gigs import CachedGig
from blowcomotion.models.instruments import (
    Equipment,
    EquipmentPhoto,
    InstrumentHistoryLog,
    InstrumentRentalNagLog,
    InstrumentStorageLocation,
    LibraryInstrument,
    LibraryInstrumentPhoto,
)
from blowcomotion.models.members import (
    EmailChangeToken,
    Member,
    MemberInstrument,
    PasswordSetToken,
)
from blowcomotion.models.music import (
    Chart,
    Event,
    EventSetlistSong,
    Song,
    SongConductor,
    SongSoloist,
    SongVideo,
)
from blowcomotion.models.pages import (
    BasePage,
    BlankCanvasPage,
    WikiAuthor,
    WikiIndexPage,
    WikiPage,
)
from blowcomotion.models.submissions import (
    BaseFormSubmission,
    BookingFormSubmission,
    ContactFormSubmission,
    DonateFormSubmission,
    FeedbackFormSubmission,
    InstrumentRentalRequestSubmission,
    JoinBandFormSubmission,
)
```

Then delete `blowcomotion/models.py`. If Step 1 found module-level helpers that other code imports from `blowcomotion.models`, add them to the re-export list (check with `grep -rn "from blowcomotion.models import" --include="*.py" . | grep -v migrations` and make every imported name resolvable).

- [ ] **Step 3: Verify — this is the critical gate**

```bash
python manage.py makemigrations --check --dry-run
python manage.py test 2>&1 | tail -3
python -c "import django, os; os.environ.setdefault('DJANGO_SETTINGS_MODULE','blowcomotion.settings.dev'); django.setup(); from django.apps import apps; print(sorted(m.__name__ for m in apps.get_app_config('blowcomotion').get_models()))" > /tmp/models_after.txt
diff /tmp/models_before.txt /tmp/models_after.txt && echo "registry identical"
```
Expected: "No changes detected" (if ANY migration is proposed, a class body changed — diff and fix; do not commit a migration); same N tests OK; `diff` output empty → "registry identical".

- [ ] **Step 4: Commit**

```bash
git add -A && git commit -S -m "refactor: split models.py into domain modules within blowcomotion app"
```

---

### Task 7: Split `blocks.py`, update CLAUDE.md, final sweep

**Files:**
- Create: `blowcomotion/blocks/__init__.py`, `layout.py`, `content.py`, `forms.py`, `media.py`
- Delete: `blowcomotion/blocks.py`
- Modify: `CLAUDE.md`
- Possibly create: one state-only migration (see Step 3)

Module assignment:

| Module | Blocks |
|---|---|
| `layout.py` | HorizontalRuleBlock, SpacerBlock, AdjustableSpacerBlock, AccordionListBlock, ColumnContentBlock, ThreeColumnBlock, TwoColumnBlock, FourColumnBlock, ColumnLayoutBlock |
| `content.py` | HeroBlock, EventsBlock, AlignableRichtextBlock, QuoteBlock, ButtonBlock, ImageBlock, CarouselImageBlock, ImageCarouselBlock, QuotedImageBlock, MultiImageBannerBlock, FullWidthImageBlock, CountdownBlock, TimelineItemBlock, TimelineBlock, MenuItemBlock, MenuItem, UpcomingPublicGigs |
| `forms.py` | ContactFormBlock, JoinBandFormBlock, BookingFormBlock, DonateFormBlock, MemberSignupFormBlock, PayPalDonateButton, VenmoDonateButton, PatreonButton, SquareDonateButton |
| `media.py` | JukeBoxBlock, ChartLibraryBlock, VideoItemOverridesBlock, VideoItemBlock, VideoFeedBlock |

- [ ] **Step 1: Create the package**

Cut each block class verbatim into its module. `ColumnContentBlock` (a StreamBlock listing many blocks) will need imports from sibling modules — import directly (`from blowcomotion.blocks.content import HeroBlock`, etc.). `blowcomotion/blocks/__init__.py` re-exports every class explicitly (same style as models `__init__`, all 40 block classes), so `from blowcomotion.blocks import HeroBlock` and old migration references keep working. Delete `blocks.py`. Update nothing else — `models/pages.py` imports via `blowcomotion.blocks` which still resolves.

- [ ] **Step 2: Check block-path serialization**

```bash
python manage.py makemigrations --dry-run
```
Two acceptable outcomes: (a) "No changes detected" — done, skip Step 3. (b) A migration altering only StreamField definitions on page models (block classes' `__module__` changed, which Wagtail serializes in `block_lookup`). Then Step 3 applies.

- [ ] **Step 3 (only if Step 2 proposed changes): Generate and verify the state-only migration**

```bash
python manage.py makemigrations blowcomotion -n streamfield_block_module_paths
python manage.py sqlmigrate blowcomotion <new_migration_number>
```
The sqlmigrate output must contain NO SQL statements (only transaction wrapper / "no SQL to execute"). If any `ALTER`/`CREATE`/`UPDATE` appears, STOP, delete the migration, revert the blocks split, and report. Otherwise keep the migration — it is a serialization-path update with zero DB effect.

- [ ] **Step 4: Full stale-reference sweep**

```bash
grep -rn "blowcomotion.utils\|blowcomotion.forms\b\|blowcomotion.member_\|blowcomotion.middleware\|blowcomotion.patreon_client\|blowcomotion.chart_api\|blowcomotion.drive_sync\|blowcomotion.views_chart_import" --include="*.py" . | grep -v migrations | grep -v docs/
```
Expected: zero hits. Fix any.

- [ ] **Step 5: Update CLAUDE.md**

Rewrite the stale parts to match reality:
- "Run a single test module" example → `python manage.py test members.tests.test_member_auth_views`
- "Single main app" paragraph → describe the hybrid layout: domain apps (`gigs`, `attendance`, `charts`, `instruments`, `members`) hold views/forms/urls/templates/tests/commands; ALL models remain in `blowcomotion` (in `blowcomotion/models/` package) — new models for any domain still go there; new apps must not gain models/migrations.
- "Member portal" paragraph → `members/views.py`, `members/urls.py`
- reCAPTCHA section → `_validate_recaptcha` is in `blowcomotion/views.py` (fix the `:525` line reference to the new location)
- Patreon section → `instruments/patreon.py`

- [ ] **Step 6: Final verification**

```bash
python manage.py test 2>&1 | tail -3
python manage.py makemigrations --check --dry-run
isort --check-only blowcomotion/ gigs/ attendance/ charts/ instruments/ members/ --diff
```
Expected: baseline N tests OK; no changes (or only the already-committed state-only migration); isort clean.

- [ ] **Step 7: Commit**

```bash
git add -A && git commit -S -m "refactor: split blocks.py into modules and update project docs"
```

---

## Out of scope (deliberately)

- `snippet_viewsets.py` (809 lines), `chooser_viewsets.py`, `wagtail_hooks.py` stay whole in `blowcomotion` — they are central Wagtail-admin wiring; splitting them across apps would fragment one admin menu into five files for no token win. Revisit only if they grow past ~1,200 lines.
- No model moves to new apps — see issue discussion; DB risk with zero extra benefit.
- `setup_roles.py`, `backup_db.py`, `optimize_jukebox_blocks.py` commands stay in `blowcomotion` (cross-domain / infra).
- `search/` app, templatetags, static files: untouched.
