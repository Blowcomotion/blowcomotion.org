# Admin Role Permissions — Design Spec

**Issue:** #193
**Date:** 2026-07-02

## Overview

Introduce role-based access control for the Wagtail admin utility views and custom dashboards
that are currently gated only by `is_superuser` (data dump, CSV exports, sync gigs), by a shared
HTTP Basic Auth password (attendance, birthdays), or by nothing beyond Wagtail's blanket
admin-login check (rental requests, library dashboards, chart import).

Every role is a standard Django/Wagtail `Group`, managed at `/admin/groups/` like any other
Wagtail group. No new permission framework, no per-user role field — this rides entirely on
Django's existing `auth.Permission` system, which Wagtail's `SnippetViewSet`s already use.

**Explicitly out of scope for this spec** (tracked as follow-up work):
- Fixing duplicate admin/band-member users on prod (#279) — informed by this role list, done next.
- Deleting the now-unused `attendance_password`/`birthdays_password` `SiteSettings` fields — done
  once this is live and prod is confirmed working without them.

## Roles and Permissions

| Role (Group) | Permissions | Grants |
|---|---|---|
| **Admin** | `is_superuser` (existing flag — no new group) | Everything; superusers bypass all `has_perm` checks |
| **Dev** | new `blowcomotion.access_dev_tools`; existing `blowcomotion.change_cachedgig` | Scrubbed data dump only (`include_real_data` forced off); Sync Gigs |
| **Data Analyst** | new `blowcomotion.access_real_data_exports` | Real (unscrubbed) data dump; all 4 CSV exports (Members/Attendance/Charts/Library) |
| **Gig Booker** | existing `blowcomotion.change_cachedgig`; existing `Event` snippet perms | Sync Gigs; `Event` snippet CRUD |
| **Library Manager** | existing perms on `LibraryInstrument`, `InstrumentHistoryLog`, `InstrumentStorageLocation`, `Equipment` | Those snippets; Rental Requests dashboard/review/return; the 3 Library Dashboards (Rented/Available/Needs Repair) |
| **Arranger/Composer** | existing perms on `Chart`, `Song`, `SongConductor`, `SongSoloist`, `SongVideo` | Those snippets; "Import Charts from Drive" tool |
| **Attendance Taker** | existing `view_attendancerecord`/`add_attendancerecord`/`change_attendancerecord` | Attendance capture, attendance reports, gigs-for-date, inactive-member reactivation, birthdays, `AttendanceRecord` snippet |
| **Editor** | Wagtail's built-in "Editors"/"Moderators" groups, **patched** with perms on `blowcomotion.CustomImage` and `wagtailmedia.Media` | Page editing (already default) + images/audio/video, which are currently gapped because `CustomImage` replaced Wagtail's stock image model and `wagtailmedia` isn't covered by Wagtail's default group setup |
| **Band Member** | none — existing `login_required` on member-portal views | Their own profile |

`change_cachedgig` and the `Event`/`Chart`/`Song`/`LibraryInstrument`/`AttendanceRecord` perms
above are Django's auto-generated model permissions (`add/change/delete/view_<model>`), already in
the DB — no new permissions needed for those.

## New Permissions (migration required)

Added via `Meta.permissions` on `SiteSettings` (no natural single model owns "dump everything"):

```python
class SiteSettings(BaseSiteSetting):
    class Meta:
        permissions = [
            ("access_dev_tools", "Can access developer data dump tools"),
            ("access_real_data_exports", "Can access real member data dumps and CSV exports"),
        ]
```

Requires `python manage.py makemigrations`.

## Enforcement Changes

### `blowcomotion/views.py`

| View | Current gate | New gate |
|---|---|---|
| `dump_data` | `is_superuser` | Scrubbed dump: `is_superuser`, `access_dev_tools`, or `access_real_data_exports`. Real dump (`include_real_data=true`): `is_superuser` or `access_real_data_exports` only — 403 if requested without one of those. |
| `export_members_csv`, `export_attendance_csv`, `export_charts_csv`, `export_library_instruments_csv` | `is_superuser` | `is_superuser` or `access_real_data_exports` |
| `sync_gigs_admin` | `is_superuser` | `is_superuser` or `change_cachedgig` |
| `attendance_capture` | `@http_basic_auth()` | `@permission_required('blowcomotion.add_attendancerecord', login_url=...)` (member-portal login) |
| `inactive_members` | `@http_basic_auth()` | same as `attendance_capture` (reactivation lives on the same workflow) |
| `attendance_reports`, `attendance_section_report_new`, `gigs_for_date` | `@http_basic_auth()` | `@permission_required('blowcomotion.view_attendancerecord', ...)` |
| `birthdays` | `@http_basic_auth_birthdays()` | `@permission_required('blowcomotion.view_attendancerecord', ...)` — Attendance Taker, not every band member, since they already handle member PII |
| `rental_requests_dashboard`, `rental_request_review`, `rental_request_return`, `instrument_library_rented`, `instrument_library_available`, `instrument_library_needs_repair` | none beyond Wagtail admin login | `@permission_required('blowcomotion.change_libraryinstrument', ...)` |

`http_basic_auth`, `http_basic_auth_generic`, and `http_basic_auth_birthdays` stay in place
(unused after this change, removed along with the password fields in the later follow-up).

### `blowcomotion/views_chart_import.py`

`picker` and `review`: replace `@login_required` with
`@permission_required('blowcomotion.change_chart', ...)`.

### `blowcomotion/wagtail_hooks.py`

The custom admin menu items (Utilities submenu, Rental Requests, Import Charts) are currently
shown to any Wagtail admin user regardless of permission. Add a small `is_shown` check per item so
menu visibility matches the underlying view's permission — e.g. a thin `PermissionMenuItem`
wrapper (or `functools.partial`-style lambda passed to `is_shown`) checking
`request.user.has_perm(...)`.

## Rollout: `setup_roles` management command

New idempotent command, `blowcomotion/management/commands/setup_roles.py`, following the same
shape as `backup_db.py`:

- `Group.objects.get_or_create(name=...)` for Dev, Data Analyst, Gig Booker, Library Manager,
  Arranger/Composer, Attendance Taker.
- Assigns the permission sets from the table above (`group.permissions.set(...)`, safe to re-run).
- Patches the existing "Editors" and "Moderators" groups: adds `add/change/delete_customimage` and
  `add/change/delete_media` permissions if missing.

Run locally (`python manage.py setup_roles`) and in prod via `ssh pythonanywhere` once merged and
migrated.

## Testing

- `blowcomotion/tests/test_admin_roles.py`: for each gated view, assert 403 for a logged-in user
  without the permission, and 200/302 for a user with it (and for `is_superuser`).
- `dump_data`: assert `include_real_data=true` 403s for a Dev-only user, and succeeds for a Data
  Analyst.
- `setup_roles` command: assert it's safe to call twice (no duplicate groups, permissions still
  correct on second run).
