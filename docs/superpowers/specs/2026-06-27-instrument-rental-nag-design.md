# Instrument Rental Nag Email — Design Spec

**Issue:** #158
**Date:** 2026-06-27

## Overview

A daily Django management command (`nag_instrument_renters`) that emails renters directly when
they haven't been seen at rehearsal or their Patreon membership is inactive. Two CTA links in
each email trigger unauthenticated Django views that notify admins of the renter's intent.

## New DB Fields (migration required)

### `SiteSettings`

| Field | Type | Default | Notes |
|---|---|---|---|
| `nag_cooldown_days` | `IntegerField` | `7` | Days to wait before re-nagging the same renter |

Surfaced in the existing "Attendance Cleanup Notifications" panel in Wagtail admin.

### `LibraryInstrument`

| Field | Type | Default | Notes |
|---|---|---|---|
| `last_nag_sent` | `DateField` | `null, blank` | Date most recent nag was sent; cleared on instrument return or status change away from `rented` |

Cleared in `LibraryInstrument.save()` when status changes away from `STATUS_RENTED` (existing
status-change hook).

## Management Command: `nag_instrument_renters`

**Location:** `blowcomotion/management/commands/nag_instrument_renters.py`

### Arguments

- `--dry-run` — print actions without sending emails or writing to DB
- `--day-to-run N` — only run on weekday N (0=Mon, 6=Sun); consistent with existing commands

### Algorithm

1. Load `SiteSettings`; exit if unavailable
2. Load `instrument_rental_notification_recipients`; exit if empty (unless `--dry-run`)
3. Query `LibraryInstrument` where `status=rented`, `member__isnull=False`, `member__email__isnull=False`
4. For each instrument:
   a. **Cooldown check:** skip if `last_nag_sent` is set and `today - last_nag_sent < nag_cooldown_days`
   b. **Attendance check:** `member.last_seen` is older than `attendance_cleanup_days` ago, OR `member.is_active == False`
   c. **Patreon check (stub):** `patreon_active == False` — reads existing field; no API call (see stub note below)
   d. If either check (b or c) triggers: send renter nag email; set `last_nag_sent = today` unless `--dry-run`
5. After all instruments: send admin summary email listing every renter nagged and which condition(s) triggered
6. Send `FORM_TEST_EMAIL` copy of admin summary (consistent with other commands)
7. If no renters qualify: log "Nothing to nag today", no emails sent

### Patreon Stub

The Patreon check reads `LibraryInstrument.patreon_active` (a manually-set boolean field) without
making any API calls. A `# ponytail:` comment in the code marks this as a stub pending issue #246,
which will add real Patreon API validation and update this field automatically.

## CTA Views

Two new unauthenticated GET views, URLs mounted under `/instrument-rental/`.

### Token

`django.core.signing.dumps({'instrument_id': pk})` with `max_age=30*86400` (30 days).
Instrument ID is the only payload — views look up current renter from the instrument record.

### `GET /instrument-rental/staying/`

- Verifies token; shows "Thanks, see you soon!" confirmation page
- Emails `instrument_rental_notification_recipients`: "Renter [name] confirmed they're returning for rehearsal ([instrument])"
- On invalid/expired token: shows a polite error page (no stack trace)

### `GET /instrument-rental/return/`

- Verifies token; shows "We'll be in touch!" confirmation page
- Emails `instrument_rental_notification_recipients`: "Renter [name] would like to return [instrument] — please follow up"
- On invalid/expired token: shows a polite error page

Both views are idempotent (clicking twice sends a second admin email but causes no data corruption).

## Renter Email (plain text)

```
Subject: A note from Blowcomotion about your instrument rental

Hi [first_name],

We wanted to check in about the [instrument name] you're renting from Blowcomotion.

[if attendance trigger]
We haven't seen you at rehearsal in a while (last seen: [date]). We'd love to have you back!

[if patreon trigger]
Our records show your Patreon membership may not be current. Keeping it active helps us
maintain the instrument library.

Please let us know your plans:

I'll be back at rehearsal soon:
https://blowcomotion.org/instrument-rental/staying/?t=<signed-token>

I'd like to return the instrument:
https://blowcomotion.org/instrument-rental/return/?t=<signed-token>

Start Wearing Purple,
Blowcomotion
```

Site base URL is read from `wagtail.models.Site` (consistent with existing email commands).

## Admin Summary Email (plain text)

Sent to `instrument_rental_notification_recipients` after all renter emails are dispatched.

```
Subject: Instrument Rental Nag Summary — [date]

Nag emails sent to [N] renter(s):

• [Member name] — [Instrument] (Reason: attendance, last seen [date])
• [Member name] — [Instrument] (Reason: patreon inactive)
• [Member name] — [Instrument] (Reason: attendance + patreon inactive)

Nothing to nag: [N] renter(s) skipped (cooldown active).
```

## Issue #246 Update

Add a comment to issue #246 documenting what the stub does and what the real implementation
must replace: update `LibraryInstrument.patreon_active` via Patreon API v2 before
`nag_instrument_renters` runs each day (or as part of the same command).

## Files Changed

| File | Change |
|---|---|
| `blowcomotion/models.py` | Add `nag_cooldown_days` to `SiteSettings`; add `last_nag_sent` to `LibraryInstrument`; clear `last_nag_sent` on status change in `save()` |
| `blowcomotion/migrations/0113_*.py` | Migration for new fields |
| `blowcomotion/management/commands/nag_instrument_renters.py` | New command |
| `blowcomotion/views.py` | Add `instrument_rental_staying` and `instrument_rental_return` views |
| `blowcomotion/urls.py` | Wire up two new URLs |
| `blowcomotion/templates/instrument_rental_staying.html` | Confirmation page |
| `blowcomotion/templates/instrument_rental_return.html` | Confirmation page |
| `blowcomotion/templates/instrument_rental_token_error.html` | Shared error page for bad/expired tokens |

## Out of Scope

- HTML email formatting (plain text only)
- Patreon API calls (stub only, see #246)
- Member portal authentication on CTA views (unauthenticated by design — link is the credential)
- Logging nag events to a separate audit table (not requested)
