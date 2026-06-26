# Instrument Rental Modernization v2 — Design Spec

**Issue:** [#157](https://github.com/Blowcomotion/blowcomotion.org/issues/157)
**PR:** #249 (`feature/issue-157-instrument-rental`)
**Date:** 2026-06-25

## Problem

PR #249 delivered the base rental request form but several gaps remain before it can go live:

- Members with incomplete profiles can reach the form and submit useless requests
- The form only captures one instrument choice; admins have no alternatives if that type is unavailable
- Some instruments should not appear in the rental dropdown (or in member profile selectors)
- The approval workflow is entirely manual — there is no way for a library admin to approve or deny a request, assign a specific unit, and notify the member from within the system
- The existing "Library: Quick Rent" admin view is superseded by this feature and should be deprecated
- `LibraryInstrumentDocument` and `agreement_signed_date` on `LibraryInstrument` are no longer part of the rental workflow

## Scope

- Profile completeness guard before the rental form is accessible
- Two independent hide booleans on `Instrument` (rental portal / member forms)
- 2nd and 3rd optional instrument choices on the submission
- Wagtail admin rental dashboard: pending requests list + per-request approve/deny view
- Reworked email flow: pending acknowledgement on submit, approval/denial on admin action
- Remove Patreon prompt from the form success page (moves to approval email only)
- Deprecate "Library: Quick Rent" admin menu item and URL
- Remove `agreement_signed_date` field and `LibraryInstrumentDocument` model from `LibraryInstrument`

Out of scope: Patreon API validation (#246), member requests dashboard (#248).

## Branch

Continue on `feature/issue-157-instrument-rental` (PR #249). All v2 changes stack on top of the existing commits.

---

## Data Model

### `Instrument` — two new fields

| Field | Type | Default | Help text |
|---|---|---|---|
| `hide_from_rental` | BooleanField | False | "Hide from the instrument rental request form. Use for instruments too rare or unavailable to offer — e.g. a vintage sousaphone kept as a display piece." |
| `hide_from_member_forms` | BooleanField | False | "Hide from member profile and signup instrument selectors. Use for instruments that members don't play but exist in inventory — e.g. a prop instrument or one not assigned to any section." |

### `LibraryInstrument` — two removals

- Drop `agreement_signed_date` (`DateField`) — no longer part of the rental workflow
- Drop `LibraryInstrumentDocument` child model entirely (table dropped; existing records lost)
- Remove corresponding panels from `LibraryInstrumentViewSet` in `snippet_viewsets.py` (`agreement_signed_date` from panels list; `InlinePanel('rental_documents')` from panels)

### `InstrumentRentalRequestSubmission` — five new fields

| Field | Type | Notes |
|---|---|---|
| `second_choice` | FK → Instrument, null/blank, PROTECT | Optional 2nd instrument type preference |
| `third_choice` | FK → Instrument, null/blank, PROTECT | Optional 3rd instrument type preference |
| `status` | CharField, choices, default PENDING | PENDING / APPROVED / DENIED |
| `admin_message` | TextField, blank=True | Library manager's response, written at review time |
| `assigned_unit` | FK → LibraryInstrument, null/blank, SET_NULL | Specific physical unit assigned on approval |

Status choices constant on the model:
```python
STATUS_PENDING = "pending"
STATUS_APPROVED = "approved"
STATUS_DENIED = "denied"
STATUS_CHOICES = [
    (STATUS_PENDING, "Pending"),
    (STATUS_APPROVED, "Approved"),
    (STATUS_DENIED, "Denied"),
]
```

`__str__` updated to include status. `list_display` in the admin viewset updated to show `status` and `assigned_unit`.

### Migration

One migration covering all of the above:
- Add `hide_from_rental`, `hide_from_member_forms` to `Instrument`
- Add `second_choice`, `third_choice`, `status`, `admin_message`, `assigned_unit` to `InstrumentRentalRequestSubmission`
- Remove `agreement_signed_date` from `LibraryInstrument`
- Delete `LibraryInstrumentDocument` table — **note: this is destructive; any existing `LibraryInstrumentDocument` rows will be permanently deleted**

Route this migration through the `wagtail-migration-reviewer` agent before committing.

---

## Form

### `MemberProfileForm` (`member_forms.py`)

- `primary_instrument` queryset: add `.filter(hide_from_member_forms=False)` in `__init__`
- `additional_instruments` queryset: change to `Instrument.objects.filter(hide_from_member_forms=False).order_by("name")`

### `MemberSignupForm` (`forms.py`)

- `primary_instrument` queryset: change to `Instrument.objects.filter(hide_from_member_forms=False).order_by('name')`

### `InstrumentRentalRequestForm` (`member_forms.py`)

Add two optional fields after `instrument`:

```python
second_choice = forms.ModelChoiceField(
    queryset=Instrument.objects.none(),
    required=False,
    empty_label="No second choice",
    label="Second choice (optional)",
    widget=forms.Select(attrs={"class": "form-select"}),
)
third_choice = forms.ModelChoiceField(
    queryset=Instrument.objects.none(),
    required=False,
    empty_label="No third choice",
    label="Third choice (optional)",
    widget=forms.Select(attrs={"class": "form-select"}),
)
```

In `__init__`, build one queryset filtered by `hide_from_rental=False` and assign to all three fields with the same `label_from_instance` availability label. Second and third choice instruments are not required to have library records (a member might list a preference for a type we don't yet own); filter only on `hide_from_rental=False`.

---

## View: `instrument_rental_request`

### Rental policy gate (GET and POST)

If `site_settings.instrument_rental_policy` is falsy (empty or None), the view passes `rental_not_configured=True` to the template context and returns immediately (does not process POST). The template renders a "coming soon" alert identical to `member/requests.html` when this flag is set.

### Profile completeness guard (GET and POST)

At the top of the view, after the rental policy gate:

```python
required = [member.full_name, member.email, member.phone, member.address]
if not all(required):
    messages.warning(request, "Please complete your contact information before requesting an instrument rental.")
    return redirect("member-profile")
```

### POST changes

- Save `second_choice` and `third_choice` from `form.cleaned_data` onto the submission
- Set `submission.status = InstrumentRentalRequestSubmission.STATUS_PENDING`
- Member email: render `emails/instrument_rental_request_pending.txt` — acknowledgement only, no Patreon mention
- Manager email: include `second_choice`, `third_choice` in the body; append a direct link to the Wagtail admin review page using `request.build_absolute_uri(f"/admin/rental-requests/{submission.pk}/")`
- Success page: no `patreon_url` in context; template shows "Request submitted — we'll be in touch"

---

## Wagtail Admin: Rental Requests Dashboard

Registered in `wagtail_hooks.py` via:
- `@hooks.register("register_admin_urls")` — mounts views under `/admin/rental-requests/`
- `@hooks.register("register_admin_menu_item")` — replaces "Library: Quick Rent" entry (same `order=295`, icon `french-horn`) with "Rental Requests"

### Dashboard view (`/admin/rental-requests/`)

Lists all `InstrumentRentalRequestSubmission` objects ordered by `date_submitted` descending, grouped or filtered by status (default: PENDING shown first). Columns: member name, email, 1st/2nd/3rd choice, date submitted, status. Each pending row has a "Review" link.

Template extends `wagtailadmin/base.html`.

### Review view (`/admin/rental-requests/<int:pk>/`)

**GET:** Shows read-only submission detail (member info, all three choices with availability counts, notes, date, current status). If status is already APPROVED or DENIED, shows outcome read-only with no action form.

If PENDING: shows action form with:
- Unit selector: `ModelChoiceField` querying `LibraryInstrument` with `status=STATUS_AVAILABLE` and `instrument__in=[first, second, third choice instruments]`, labeled `"{instrument.name} — {serial_number}"`
- Message textarea (required for both approve and deny)
- Two submit buttons: `name="action" value="approve"` and `name="action" value="deny"`

**POST approve:**
1. Validate unit selected and message non-empty
2. `submission.status = APPROVED`, `submission.admin_message = message`, `submission.assigned_unit = unit`
3. Mirror the save path from `instrument_library_quick_rent` (views.py:160-179): `unit.member = submission.member`, `unit.status = STATUS_RENTED`, `unit.rental_date = date.today()`, then `unit.save()` and `member.renting = True; member.save()` — this fires the existing history-log and renting-status hooks.
4. `submission.save()`
5. Send approval email to member

**POST deny:**
1. Validate message non-empty
2. `submission.status = DENIED`, `submission.admin_message = message`
3. `submission.save()`
4. Send denial email to member

Both actions redirect back to the dashboard with a success message.

**Permission:** These views are mounted under Wagtail's admin URL namespace via `register_admin_urls`. Wagtail's middleware enforces admin login for all URLs under `/admin/` — no explicit decorator is needed, matching the pattern of `instrument_library_quick_rent` and other existing admin views in `views.py`.

---

## Email Templates

### `emails/instrument_rental_request_pending.txt` (replaces `_confirmation.txt`)

Subject: `"Your instrument rental request — {instrument}"`

Body: thank the member, confirm receipt of their request for [1st choice] (with 2nd/3rd if provided), state that the library team will review and follow up, no Patreon mention.

**Rename note:** The existing template is `emails/instrument_rental_request_confirmation.txt`. The view reference in `member_views.py` (line 354) and any test assertions in `test_instrument_rental.py` that reference this filename must also be updated to `_pending.txt`.

### `emails/instrument_rental_request_approved.txt` (new)

Subject: `"Your instrument rental request has been approved — {instrument}"`

Body: congratulate member, show assigned instrument name + serial number, include admin's custom message, include Patreon link with a note to complete membership before pickup.

### `emails/instrument_rental_request_denied.txt` (new)

Subject: `"Your instrument rental request — {instrument}"`

Body: inform member the request was not approved at this time, include admin's custom message, encourage them to reach out with questions.

---

## Deprecation: Library Quick Rent

In `wagtail_hooks.py`:
- Comment out `register_library_quick_rent_menu_item` hook with `# TODO(#250): delete — replaced by Rental Requests dashboard`

In `urls.py` (if the view has a URL entry there):
- Comment out the URL pattern with the same TODO note

The `instrument_library_quick_rent` view function in `views.py` is left in place but dead-linked. Issue #250 tracks final deletion after library admins confirm the new dashboard covers their workflow.

---

## Templates

| Template | Change |
|---|---|
| `member/instrument_rental_request.html` | Add rental policy gate (show "coming soon" alert when policy not set, matching `member/requests.html`); add 2nd/3rd choice dropdowns; update success state to remove Patreon, show "we'll be in touch" |
| `wagtailadmin/rental_requests_dashboard.html` | New — pending requests list |
| `wagtailadmin/rental_request_review.html` | New — review/approve/deny form |
| `emails/instrument_rental_request_pending.txt` | Replaces `emails/instrument_rental_request_confirmation.txt` — pending acknowledgement only |
| `emails/instrument_rental_request_approved.txt` | New — approval + Patreon link |
| `emails/instrument_rental_request_denied.txt` | New — denial with admin message |

---

## Files Changed

| File | Change |
|---|---|
| `blowcomotion/models.py` | Add fields to `Instrument` and `InstrumentRentalRequestSubmission`; remove `agreement_signed_date` and `LibraryInstrumentDocument` |
| `blowcomotion/forms.py` | Filter `MemberSignupForm.primary_instrument` queryset |
| `blowcomotion/member_forms.py` | Filter profile form querysets; add 2nd/3rd choice fields to rental form |
| `blowcomotion/member_views.py` | Add profile guard; update POST to save choices, send pending email, remove Patreon from success context |
| `blowcomotion/wagtail_hooks.py` | Register admin dashboard URLs and menu item; comment out Quick Rent hook |
| `blowcomotion/snippet_viewsets.py` | Remove `agreement_signed_date` and `rental_documents` panels from `LibraryInstrumentViewSet`; update `InstrumentRentalRequestSubmissionViewset` panels/list_display |
| `blowcomotion/migrations/XXXX_rental_v2.py` | New migration |
| `blowcomotion/templates/member/instrument_rental_request.html` | Add 2nd/3rd choice fields; update success state |
| `blowcomotion/templates/wagtailadmin/rental_requests_dashboard.html` | New |
| `blowcomotion/templates/wagtailadmin/rental_request_review.html` | New |
| `blowcomotion/templates/emails/instrument_rental_request_pending.txt` | Replaces `_confirmation.txt` |
| `blowcomotion/templates/emails/instrument_rental_request_approved.txt` | New |
| `blowcomotion/templates/emails/instrument_rental_request_denied.txt` | New |
| `blowcomotion/tests/test_instrument_rental.py` | Update existing tests for new fields/guard; add approval/denial view tests |
