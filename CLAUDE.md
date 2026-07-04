# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```bash
# Run dev server
python manage.py runserver

# Run all tests
python manage.py test

# Run a single test module
python manage.py test members.tests.test_member_auth_views

# Check / fix import sorting (runs automatically on commit via pre-commit hook)
isort --check-only blowcomotion/ --diff
isort blowcomotion/

# Create / apply migrations
python manage.py makemigrations
python manage.py migrate

# Collect static (required after any CSS/JS change; production uses ManifestStaticFilesStorage)
python manage.py collectstatic --noinput
```

## Static files — source vs. collected

**Always edit files under `blowcomotion/static/`**, never under `static/` (the collected root). Django's `collectstatic` copies from `blowcomotion/static/` → `static/`; changes to `static/` are invisible to git and get overwritten on next deploy.

## Settings split

`blowcomotion/settings/` has four files:
- `base.py` — shared settings
- `dev.py` — `DEBUG=True`, console email, reCAPTCHA keys commented out
- `production.py` — `DEBUG=False`, secure cookies
- `local.py` — secrets not in repo (API keys, reCAPTCHA keys, `SECRET_KEY`); imported by both dev and production

## Architecture overview

**Django + Wagtail CMS.** Wagtail handles all CMS pages via a single catch-all URL at the bottom of `urls.py`. Everything above it is a named Django view.

**Hybrid app layout:** domain apps (`gigs`, `attendance`, `charts`, `instruments`, `members`) hold views, forms, urls, templates, tests, and management commands for their domain. ALL models live in the `blowcomotion` app, in the `blowcomotion/models/` package — new models for any domain still go there, and new apps must not gain models or migrations of their own. `blowcomotion/` itself also keeps StreamField blocks (`blowcomotion/blocks/`), the Wagtail admin wiring (`snippet_viewsets.py`, `chooser_viewsets.py`, `wagtail_hooks.py`), and cross-domain/infra management commands.

**Public form pipeline:** All public-facing form submissions (contact, join band, booking, donate, feedback, member signup) POST to a single `/process-form/` endpoint handled by `process_form()` in `views.py`. The form type is identified by a hidden `form_type` field.

**Member portal** is a separate set of views in `members/views.py` with its own URLs in `members/urls.py`, mounted at `/member/`. It uses Django's built-in auth views as base classes.

**Attendance and birthdays** are protected by role-based access: `@login_required` plus `@permission_required('blowcomotion.add_attendancerecord', ...)` or `@permission_required('blowcomotion.view_attendancerecord', ...)` (granted via the Attendance Taker role). This replaced the old shared HTTP Basic Auth password scheme.

**StreamField blocks** are defined in the `blowcomotion/blocks/` package (`layout.py`, `content.py`, `forms.py`, `media.py`, re-exported from `blowcomotion/blocks/__init__.py`) and rendered by templates in `templates/blocks/`. New page content types are added as blocks on `BlankCanvasPage`.

**GigoGig integration:** `CachedGig` is a DB table that stores gig data synced from the API (persists until next sync). The `gigs_for_date` view adds a second layer via Django's `cache` (600s TTL) on top of DB queries. Configured via `GIGO_API_URL` / `GIGO_API_KEY` / `GIGO_BAND_ID` in `local.py`.

**Patreon validation:** After an instrument rental request is submitted, `instruments/patreon.py` paginates the Patreon API v2 campaign member list to check whether the submitter's email has an active Patreon pledge. The result is stored on `InstrumentRentalRequestSubmission.patreon_validated` (None = not checked, True = active, False = not found / inactive) and included in the manager notification email. Requires in `local.py`:
- `PATREON_ACCESS_TOKEN` — creator access token (must have `campaigns.members` and `campaigns.members[email]` scopes)
- `PATREON_CAMPAIGN_ID` — numeric campaign ID

If either setting is absent the check is skipped silently (field stays None).

## reCAPTCHA — required on every public form

**Every form that accepts public POST submissions must:**
1. Be validated server-side by `_validate_recaptcha(request)` (in `blowcomotion/views.py`) before processing
2. Show the disclosure notice "This site is protected by reCAPTCHA." below the submit button

The disclosure notice is injected automatically by `form.js` for any form matching:
- `form[hx-post*="process-form"]` or `form[action*="process-form"]` — public CMS forms
- `form#member-form` — member portal forms
- `form[data-recaptcha]` — any other form type; add this attribute to opt in

The reCAPTCHA script and `form.js` load when `include_form_js=True` is in the template context (set by the view). In dev with no keys configured, `_validate_recaptcha` skips validation; in production it rejects submissions without a valid token.

**When adding a new public form:**
- Pass `include_form_js=True` in the view context (GET and POST)
- Call `_validate_recaptcha(request)` at the top of the POST handler before any processing
- Use `id="member-form"` on member portal forms, or route through `/process-form/` for CMS block forms — the notice appears automatically
- For any other form type, add `data-recaptcha` to the `<form>` element — `form.js` picks it up automatically

**Do NOT add inline reCAPTCHA submit handlers to templates.** `form.js` already attaches a submit handler to every `form#member-form` and `form[action*="process-form"]`. Adding a second `addEventListener('submit', ...)` in a template's `{% block extra_js %}` causes two concurrent handlers to both call `grecaptcha.execute()` and `form.submit()`, resulting in the form being submitted twice — two server requests, two emails sent, two tokens created.

## Commits and PRs

- GPG-sign all commits (`git commit -S`)
- No emojis in commit messages or PR descriptions
- No `Co-Authored-By` lines
- Conventional commit prefixes: `feat:`, `fix:`, `refactor:`, `chore:`
- PR base branch: `development` (not `main`)
