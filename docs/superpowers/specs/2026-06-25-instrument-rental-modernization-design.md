# Instrument Rental Modernization — Design Spec

**Issue:** [#157](https://github.com/Blowcomotion/blowcomotion.org/issues/157)
**Date:** 2026-06-25

## Problem

The instrument rental process relies on a paper/PDF form. There is no digital record of requests, no way for members to self-serve, and instruments have historically been lent to people before their contact info was collected — making it impossible to follow up when they disappear. This feature digitizes the request process and gates it behind member onboarding.

## Scope

- Member-portal instrument rental request form (login required)
- Availability display inline in the instrument dropdown
- Waitlist behavior when no units are available
- Policy acknowledgement (editable in Wagtail admin)
- Email notification to library managers on submission
- Post-submission Patreon prompt
- Admin visibility of all submissions

Out of scope: Patreon API validation, ranked instrument preferences, instrument availability as a standalone public page.

## Architecture

This is a member portal feature. The form lives at `/member/instrument-rental/` in `member_views.py`, protected by `@login_required`. It does not use the public `/process-form/` pipeline or the CMS block system.

## Data Model

### `InstrumentRentalRequestSubmission` (new, extends `BaseFormSubmission`)

Extends the existing `BaseFormSubmission` pattern (same as `ContactFormSubmission`, etc.).

| Field | Type | Notes |
|---|---|---|
| `member` | FK → Member, SET_NULL, null/blank | Links to the requesting member |
| `instrument` | FK → Instrument, PROTECT | The instrument *type* requested (not a specific unit) |
| `is_waitlist` | BooleanField, default False | Set server-side at submission time |
| `notes` | TextField, blank/null | Optional notes from the member |
| `policy_acknowledged` | BooleanField | Required True to submit |
| `phone` | CharField, blank/null | Snapshot of member phone at submission time |
| `address` | CharField, blank/null | Snapshot of member address at submission time |

Inherited from `BaseFormSubmission`: `name`, `email`, `date_submitted`.

Contact fields (phone, address) are snapshotted from the member record at submission time so the admin sees what was accurate when the request was made, even if the member later updates their profile.

### `SiteSettings` addition

One new field: `instrument_rental_policy` (`RichTextField`, blank=True) — the full lending policy text, editable in Wagtail admin without a deploy.

The existing `instrument_rental_notification_recipients` field on `SiteSettings` is reused as-is for email routing.

## Form

`InstrumentRentalRequestForm` in `member_forms.py`.

**Fields:**
- `instrument`: `ModelChoiceField` — queryset is `Instrument` objects that have at least one `LibraryInstrument` record, annotated with `available_count`. Labels display availability inline: `"Trumpet (3 available)"` or `"Sousaphone (waitlist — 0 available)"`. Instruments with zero units in the library entirely (never entered) are excluded.
- `notes`: optional `CharField` with `Textarea` widget
- `policy_acknowledged`: `BooleanField(required=True)` — checkbox, must be checked to submit

## View

**`instrument_rental_request`** in `member_views.py`, decorated `@login_required`.

**GET:**
- Annotates `Instrument` queryset with `available_count` (count of related `LibraryInstrument` with `status='available'`), filtered to instruments with at least one library record.
- Renders the form.
- Passes member contact info (name, email, phone, address) to the template as read-only display values — not form fields.
- Passes `instrument_rental_policy` from `SiteSettings` for display above the policy checkbox.

**POST:**
- Validates the form.
- Re-queries `available_count` for the chosen instrument server-side to set `is_waitlist` (not trusted from client).
- Saves `InstrumentRentalRequestSubmission` with member FK, snapshotted contact fields, and `is_waitlist`.
- Sends email to `SiteSettings.instrument_rental_notification_recipients` via existing `_send_form_email`. Email includes: member name, email, phone, address, instrument requested, waitlist status, notes, and a link to the member's admin record.
- Redirects to a success page (or renders success state on same URL).

**URL:** `/member/instrument-rental/` added to `member_urls.py`.

## Template

`templates/member/instrument_rental_request.html`

- Member portal chrome (consistent with other portal pages from issue #212).
- Read-only contact info block (name, email, phone, address) with a "Need to update your info? Edit your profile →" link.
- Instrument dropdown with inline availability counts.
- Optional notes textarea.
- Policy text rendered from `SiteSettings.instrument_rental_policy` (RichText).
- Policy acknowledgement checkbox below the policy text.
- Submit button.

Success state (same template or redirect to `instrument_rental_request_success.html`):
- Confirms submission received.
- Distinguishes waitlist vs. active request: "You've been added to the waitlist for [instrument]" vs. "Your request for [instrument] has been received."
- Patreon prompt with button linking to `SiteSettings.patreon_url`.

## Admin

Register `InstrumentRentalRequestSubmission` in `wagtail_hooks.py` as a `ModelAdmin` (same pattern as other submission models). List view columns: `member`, `instrument`, `is_waitlist`, `date_submitted`, `name`.

## Migration

One migration covering:
- New `InstrumentRentalRequestSubmission` model
- New `instrument_rental_policy` field on `SiteSettings`

## Files Changed

| File | Change |
|---|---|
| `blowcomotion/models.py` | Add `InstrumentRentalRequestSubmission`; add `instrument_rental_policy` to `SiteSettings` |
| `blowcomotion/member_forms.py` | Add `InstrumentRentalRequestForm` |
| `blowcomotion/member_views.py` | Add `instrument_rental_request` view |
| `blowcomotion/member_urls.py` | Add URL pattern |
| `blowcomotion/wagtail_hooks.py` | Register submission model in admin |
| `blowcomotion/templates/member/instrument_rental_request.html` | New template |
| `blowcomotion/migrations/XXXX_instrument_rental_request.py` | New migration |
