# Instrument Rental Modernization Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a member-portal instrument rental request form at `/member/instrument-rental/` that pre-fills contact info, shows instrument availability inline, flags waitlist submissions, acknowledges a CMS-editable lending policy, emails library managers and the member, and surfaces all submissions in the Wagtail admin.

**Architecture:** Member portal view (`member_views.py`) protected by `@login_required`. Submission stored in a new `InstrumentRentalRequestSubmission` model (extends existing `BaseFormSubmission`). Two emails sent on submit via the existing `_MemberEmail` helper from `member_auth.py`: one to library managers (from `SiteSettings.instrument_rental_notification_recipients`), one confirmation to the member. Availability is computed from `LibraryInstrument.status` at request time.

**Tech Stack:** Django, Wagtail, Bootstrap 5, existing member portal patterns in `member_views.py` / `member_forms.py` / `snippet_viewsets.py`.

## Global Constraints

- GPG-sign all commits: `git commit -S`
- No emojis in commit messages or PR descriptions
- No `Co-Authored-By` lines in commits
- Conventional commit prefixes: `feat:`, `fix:`, `refactor:`, `chore:`
- PR base branch: `development`
- Work on branch: `feature/issue-157-instrument-rental`
- Run `python manage.py test blowcomotion` after each task; all must pass before committing
- Edit files under `blowcomotion/static/` only (never `static/`)
- After any model or SiteSettings change: run `python manage.py makemigrations` and include the generated migration in the commit

## Parallelism Notes

- **Task 1** must complete before all others (model must exist).
- **Tasks 2 and 3** are independent — run in parallel after Task 1.
- **Task 4** requires Task 2 (needs the form class).
- **Task 5** requires Task 4 (needs the URL name and view context variables).

## File Map

| File | Action | Responsibility |
|---|---|---|
| `blowcomotion/models.py` | Modify | Add `InstrumentRentalRequestSubmission`; add `instrument_rental_policy` to `SiteSettings` |
| `blowcomotion/member_forms.py` | Modify | Add `InstrumentRentalRequestForm` |
| `blowcomotion/member_views.py` | Modify | Add `instrument_rental_request` view |
| `blowcomotion/member_urls.py` | Modify | Add URL pattern |
| `blowcomotion/snippet_viewsets.py` | Modify | Add `InstrumentRentalRequestSubmissionViewset`; register in `FormsViewSetGroup` |
| `blowcomotion/templates/member/instrument_rental_request.html` | Create | Form + success state template |
| `blowcomotion/templates/member/portal_base.html` | Modify | Add nav link |
| `blowcomotion/templates/emails/instrument_rental_request_confirmation.txt` | Create | Member confirmation email |
| `blowcomotion/migrations/0107_instrument_rental_request.py` | Create (generated) | Schema migration |
| `blowcomotion/tests/test_instrument_rental.py` | Create | All tests for this feature |

---

### Task 1: Model and Migration

**Files:**
- Modify: `blowcomotion/models.py`
- Create (generated): `blowcomotion/migrations/0107_instrument_rental_request.py`
- Create: `blowcomotion/tests/test_instrument_rental.py`

**Interfaces:**
- Produces: `InstrumentRentalRequestSubmission` — fields: `member` (FK→Member, SET_NULL), `instrument` (FK→Instrument, PROTECT), `is_waitlist` (BooleanField), `phone` (CharField), `address` (CharField), `policy_acknowledged` (BooleanField). Inherits `name`, `email`, `message`, `date_submitted` from `BaseFormSubmission`. The `message` field stores optional notes — no extra `notes` field needed.
- Produces: `SiteSettings.instrument_rental_policy` — `RichTextField(blank=True)`

- [ ] **Step 1: Write the failing tests**

Create `blowcomotion/tests/test_instrument_rental.py`:

```python
from django.test import TestCase

from blowcomotion.models import (
    Instrument,
    InstrumentRentalRequestSubmission,
    LibraryInstrument,
    Member,
)


def make_instrument(name="Trumpet"):
    return Instrument.objects.create(name=name)


def make_library_instrument(instrument, status=LibraryInstrument.STATUS_AVAILABLE, serial="SN001"):
    return LibraryInstrument.objects.create(
        instrument=instrument, serial_number=serial, status=status
    )


def make_member(**kwargs):
    defaults = dict(first_name="Sam", last_name="Player", email="sam@example.com",
                    phone="512-555-0100", address="123 Main St")
    defaults.update(kwargs)
    return Member.objects.create(**defaults)


class InstrumentRentalRequestSubmissionModelTest(TestCase):
    def setUp(self):
        self.instrument = make_instrument()
        self.member = make_member()

    def test_str_active_request(self):
        sub = InstrumentRentalRequestSubmission.objects.create(
            name="Sam Player",
            email="sam@example.com",
            instrument=self.instrument,
            member=self.member,
            is_waitlist=False,
            policy_acknowledged=True,
        )
        self.assertIn("request", str(sub))
        self.assertIn("Trumpet", str(sub))

    def test_str_waitlist(self):
        sub = InstrumentRentalRequestSubmission.objects.create(
            name="Sam Player",
            email="sam@example.com",
            instrument=self.instrument,
            member=self.member,
            is_waitlist=True,
            policy_acknowledged=True,
        )
        self.assertIn("waitlist", str(sub))

    def test_member_deletion_nulls_fk(self):
        sub = InstrumentRentalRequestSubmission.objects.create(
            name="Sam Player",
            email="sam@example.com",
            instrument=self.instrument,
            member=self.member,
            is_waitlist=False,
            policy_acknowledged=True,
        )
        self.member.delete()
        sub.refresh_from_db()
        self.assertIsNone(sub.member)
```

- [ ] **Step 2: Run to verify tests fail**

```bash
python manage.py test blowcomotion.tests.test_instrument_rental -v 2
```

Expected: `ImportError` or `AttributeError` — `InstrumentRentalRequestSubmission` does not exist yet.

- [ ] **Step 3: Add `InstrumentRentalRequestSubmission` to `models.py`**

Find the `DonateFormSubmission` class (around line 1985). Add after its closing line:

```python
class InstrumentRentalRequestSubmission(BaseFormSubmission):
    """Member portal instrument rental requests. `message` field stores optional notes."""

    member = models.ForeignKey(
        "blowcomotion.Member",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="rental_requests",
    )
    instrument = models.ForeignKey(
        "blowcomotion.Instrument",
        on_delete=models.PROTECT,
        related_name="rental_requests",
    )
    is_waitlist = models.BooleanField(default=False)
    phone = models.CharField(max_length=255, blank=True, null=True)
    address = models.CharField(max_length=255, blank=True, null=True)
    policy_acknowledged = models.BooleanField(default=False)

    def __str__(self):
        status = "waitlist" if self.is_waitlist else "request"
        return f"{self.name} — {self.instrument} ({status}) on {self.date_submitted:%Y-%m-%d}"

    class Meta:
        ordering = ["-date_submitted"]
        verbose_name = "Instrument Rental Request"
        verbose_name_plural = "Instrument Rental Requests"
```

- [ ] **Step 4: Add `instrument_rental_policy` to `SiteSettings`**

In `SiteSettings` (around line 47), find the `instrument_rental_notification_recipients` field (line ~115). Add this field directly after it:

```python
    instrument_rental_policy = RichTextField(
        blank=True,
        help_text="Lending policy text displayed on the instrument rental request form.",
    )
```

Then in `SiteSettings.panels` (around line 167), find the `"Form Email Recipients"` `MultiFieldPanel`. Add a new panel **after** it:

```python
        MultiFieldPanel([
            FieldPanel('instrument_rental_policy'),
        ], heading="Instrument Rental Policy"),
```

- [ ] **Step 5: Generate and inspect the migration**

```bash
python manage.py makemigrations
```

Expected: creates `blowcomotion/migrations/0107_instrument_rental_request.py`. Confirm it adds `InstrumentRentalRequestSubmission` table and `instrument_rental_policy` field on `SiteSettings`.

- [ ] **Step 6: Apply migration**

```bash
python manage.py migrate
```

Expected: `OK` with no errors.

- [ ] **Step 7: Run tests**

```bash
python manage.py test blowcomotion.tests.test_instrument_rental -v 2
```

Expected: all 3 model tests pass.

- [ ] **Step 8: Commit**

```bash
git add blowcomotion/models.py blowcomotion/migrations/0107_instrument_rental_request.py blowcomotion/tests/test_instrument_rental.py
git commit -S -m "feat: add InstrumentRentalRequestSubmission model and instrument_rental_policy setting"
```

---

### Task 2: Form

**Depends on:** Task 1 (model must exist for queryset)

**Files:**
- Modify: `blowcomotion/member_forms.py`
- Modify: `blowcomotion/tests/test_instrument_rental.py`

**Interfaces:**
- Consumes: `Instrument`, `LibraryInstrument` from `blowcomotion.models`
- Produces: `InstrumentRentalRequestForm` — fields: `instrument` (ModelChoiceField with annotated queryset), `notes` (optional CharField/Textarea), `policy_acknowledged` (required BooleanField). `cleaned_data["instrument"]` is an `Instrument` instance with an `available_count` annotation.

- [ ] **Step 1: Write the failing form tests**

Append to `blowcomotion/tests/test_instrument_rental.py`:

```python
from django.db.models import Count, Q

from blowcomotion.member_forms import InstrumentRentalRequestForm


class InstrumentRentalRequestFormTest(TestCase):
    def setUp(self):
        self.instrument = make_instrument("Trombone")
        self.li = make_library_instrument(self.instrument, status=LibraryInstrument.STATUS_AVAILABLE)

    def test_valid_form(self):
        form = InstrumentRentalRequestForm(data={
            "instrument": self.instrument.pk,
            "notes": "Prefer medium bore",
            "policy_acknowledged": True,
        })
        self.assertTrue(form.is_valid(), form.errors)

    def test_instrument_required(self):
        form = InstrumentRentalRequestForm(data={"policy_acknowledged": True})
        self.assertFalse(form.is_valid())
        self.assertIn("instrument", form.errors)

    def test_policy_required(self):
        form = InstrumentRentalRequestForm(data={
            "instrument": self.instrument.pk,
            "policy_acknowledged": False,
        })
        self.assertFalse(form.is_valid())
        self.assertIn("policy_acknowledged", form.errors)

    def test_notes_optional(self):
        form = InstrumentRentalRequestForm(data={
            "instrument": self.instrument.pk,
            "policy_acknowledged": True,
        })
        self.assertTrue(form.is_valid(), form.errors)

    def test_label_shows_available_count(self):
        form = InstrumentRentalRequestForm()
        obj = Instrument.objects.annotate(
            available_count=Count(
                "library_inventory",
                filter=Q(library_inventory__status=LibraryInstrument.STATUS_AVAILABLE),
            )
        ).get(pk=self.instrument.pk)
        label = form.fields["instrument"].label_from_instance(obj)
        self.assertIn("1 available", label)

    def test_label_shows_waitlist_when_zero(self):
        self.li.status = LibraryInstrument.STATUS_RENTED
        self.li.save()
        form = InstrumentRentalRequestForm()
        obj = Instrument.objects.annotate(
            available_count=Count(
                "library_inventory",
                filter=Q(library_inventory__status=LibraryInstrument.STATUS_AVAILABLE),
            )
        ).get(pk=self.instrument.pk)
        label = form.fields["instrument"].label_from_instance(obj)
        self.assertIn("waitlist", label)

    def test_instrument_without_library_record_excluded(self):
        other = Instrument.objects.create(name="Tuba")
        # No LibraryInstrument for "other"
        form = InstrumentRentalRequestForm()
        pks = list(form.fields["instrument"].queryset.values_list("pk", flat=True))
        self.assertNotIn(other.pk, pks)
```

- [ ] **Step 2: Run to verify tests fail**

```bash
python manage.py test blowcomotion.tests.test_instrument_rental.InstrumentRentalRequestFormTest -v 2
```

Expected: `ImportError` — `InstrumentRentalRequestForm` does not exist yet.

- [ ] **Step 3: Add imports to `member_forms.py`**

The current top of `member_forms.py` has:
```python
from blowcomotion.models import Instrument, Member
```

Add `LibraryInstrument` and the db model helpers:
```python
from django.db.models import Count, Q

from blowcomotion.models import Instrument, LibraryInstrument, Member
```

- [ ] **Step 4: Add `InstrumentRentalRequestForm` to `member_forms.py`**

Append at the end of the file:

```python
class InstrumentRentalRequestForm(forms.Form):
    instrument = forms.ModelChoiceField(
        queryset=Instrument.objects.none(),
        empty_label="Select an instrument",
        label="Instrument",
        widget=forms.Select(attrs={"class": "form-select"}),
    )
    notes = forms.CharField(
        required=False,
        label="Notes",
        widget=forms.Textarea(attrs={"class": "form-control", "rows": 3}),
    )
    policy_acknowledged = forms.BooleanField(
        required=True,
        label="I have read and agree to the Instrument Lending Policy",
        error_messages={"required": "You must acknowledge the policy to submit this request."},
        widget=forms.CheckboxInput(attrs={"class": "form-check-input"}),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        qs = (
            Instrument.objects.annotate(
                available_count=Count(
                    "library_inventory",
                    filter=Q(library_inventory__status=LibraryInstrument.STATUS_AVAILABLE),
                )
            )
            .filter(library_inventory__isnull=False)
            .distinct()
            .order_by("name")
        )
        self.fields["instrument"].queryset = qs
        self.fields["instrument"].label_from_instance = lambda obj: (
            f"{obj.name} ({obj.available_count} available)"
            if obj.available_count > 0
            else f"{obj.name} (waitlist — 0 available)"
        )
```

- [ ] **Step 5: Run tests**

```bash
python manage.py test blowcomotion.tests.test_instrument_rental.InstrumentRentalRequestFormTest -v 2
```

Expected: all 7 form tests pass.

- [ ] **Step 6: Run full test suite to check for regressions**

```bash
python manage.py test blowcomotion -v 1
```

Expected: all pass.

- [ ] **Step 7: Commit**

```bash
git add blowcomotion/member_forms.py blowcomotion/tests/test_instrument_rental.py
git commit -S -m "feat: add InstrumentRentalRequestForm"
```

---

### Task 3: Admin Viewset

**Depends on:** Task 1 (model must exist)  
**Parallel with:** Task 2

**Files:**
- Modify: `blowcomotion/snippet_viewsets.py`

**Interfaces:**
- Consumes: `InstrumentRentalRequestSubmission` from `blowcomotion.models`
- Produces: `InstrumentRentalRequestSubmissionViewset` registered in `FormsViewSetGroup`

- [ ] **Step 1: Add the viewset to `snippet_viewsets.py`**

Find `DonateFormSubmissionViewset` (around line 695). After its closing line, add:

```python
class InstrumentRentalRequestSubmissionViewset(SnippetViewSet):
    model = None
    menu_label = "Instrument Rental Requests"
    menu_name = "instrument_rental_requests"
    menu_icon = "bi-music-note-beamed"
    list_display = ["name", "email", "instrument", "is_waitlist", "date_submitted"]
    search_fields = ("name", "email")
    panels = [
        "member",
        "name",
        "email",
        "phone",
        "address",
        "instrument",
        "is_waitlist",
        "message",
        "policy_acknowledged",
        "date_submitted",
    ]

    def __init__(self, *args, **kwargs):
        from .models import InstrumentRentalRequestSubmission
        self.model = InstrumentRentalRequestSubmission
        super().__init__(*args, **kwargs)
```

- [ ] **Step 2: Register in `FormsViewSetGroup`**

Find `FormsViewSetGroup` (around line 715). Update `items` to include the new viewset:

```python
class FormsViewSetGroup(SnippetViewSetGroup):
    items = (
        ContactFormSubmissionViewset,
        FeedbackFormSubmissionViewset,
        JoinBandFormSubmissionViewset,
        BookingFormSubmissionViewset,
        DonateFormSubmissionViewset,
        InstrumentRentalRequestSubmissionViewset,
    )
```

- [ ] **Step 3: Run full test suite**

```bash
python manage.py test blowcomotion -v 1
```

Expected: all pass.

- [ ] **Step 4: Commit**

```bash
git add blowcomotion/snippet_viewsets.py
git commit -S -m "feat: register InstrumentRentalRequestSubmission in Wagtail admin"
```

---

### Task 4: View and URL

**Depends on:** Tasks 1 and 2

**Files:**
- Modify: `blowcomotion/member_views.py`
- Modify: `blowcomotion/member_urls.py`
- Modify: `blowcomotion/tests/test_instrument_rental.py`

**Interfaces:**
- Consumes: `InstrumentRentalRequestForm` (Task 2), `InstrumentRentalRequestSubmission` (Task 1), `_MemberEmail` from `member_auth`, `SiteSettings` from `models`
- Produces: `instrument_rental_request` view at URL name `member-instrument-rental`. GET context keys: `member`, `form`, `policy_text`. POST success context keys: `member`, `submitted` (True), `is_waitlist`, `instrument`, `patreon_url`.

- [ ] **Step 1: Write the failing view tests**

Append to `blowcomotion/tests/test_instrument_rental.py`:

```python
from unittest.mock import patch

from django.urls import reverse

from blowcomotion.member_auth import create_member_user


class InstrumentRentalRequestViewTest(TestCase):
    def setUp(self):
        self.instrument = make_instrument("Trumpet")
        self.li = make_library_instrument(self.instrument, status=LibraryInstrument.STATUS_AVAILABLE)
        self.member = make_member()
        self.user = create_member_user(self.member)
        self.user.set_password("Pass123!")
        self.user.save()
        self.client.login(username="sam@example.com", password="Pass123!")

    def test_get_redirects_anonymous(self):
        self.client.logout()
        response = self.client.get(reverse("member-instrument-rental"))
        self.assertRedirects(
            response,
            "/member/login/?next=/member/instrument-rental/",
            fetch_redirect_response=False,
        )

    def test_get_returns_200(self):
        response = self.client.get(reverse("member-instrument-rental"))
        self.assertEqual(response.status_code, 200)

    def test_get_context_has_member_and_form(self):
        response = self.client.get(reverse("member-instrument-rental"))
        self.assertEqual(response.context["member"], self.member)
        self.assertIn("form", response.context)

    def _post(self, extra=None):
        data = {"instrument": self.instrument.pk, "policy_acknowledged": True}
        if extra:
            data.update(extra)
        return self.client.post(reverse("member-instrument-rental"), data)

    def test_post_creates_submission(self):
        self._post()
        self.assertEqual(InstrumentRentalRequestSubmission.objects.count(), 1)

    def test_post_active_request_not_waitlisted(self):
        self._post()
        sub = InstrumentRentalRequestSubmission.objects.first()
        self.assertFalse(sub.is_waitlist)

    def test_post_sets_waitlist_when_none_available(self):
        self.li.status = LibraryInstrument.STATUS_RENTED
        self.li.save()
        self._post()
        sub = InstrumentRentalRequestSubmission.objects.first()
        self.assertTrue(sub.is_waitlist)

    def test_post_snapshots_member_contact_info(self):
        self._post({"notes": "any note"})
        sub = InstrumentRentalRequestSubmission.objects.first()
        self.assertEqual(sub.name, self.member.full_name)
        self.assertEqual(sub.email, self.member.email)
        self.assertEqual(sub.phone, self.member.phone)
        self.assertEqual(sub.address, self.member.address)

    def test_post_stores_notes_in_message(self):
        self._post({"notes": "prefer small bore"})
        sub = InstrumentRentalRequestSubmission.objects.first()
        self.assertEqual(sub.message, "prefer small bore")

    @patch("blowcomotion.member_views._MemberEmail")
    def test_post_sends_two_emails(self, mock_email_cls):
        mock_email_cls.return_value.send.return_value = None
        self._post()
        self.assertEqual(mock_email_cls.call_count, 2)

    def test_post_renders_success_state(self):
        response = self._post()
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context["submitted"])
        self.assertEqual(response.context["instrument"], self.instrument)

    def test_invalid_post_rerenders_form_with_errors(self):
        response = self.client.post(reverse("member-instrument-rental"), {"policy_acknowledged": True})
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.context.get("submitted", False))
        self.assertIn("instrument", response.context["form"].errors)

    def test_user_without_member_profile_redirects(self):
        from django.contrib.auth import get_user_model
        User = get_user_model()
        staff = User.objects.create_user(username="staff@example.com", password="StaffP@ss!")
        self.client.login(username="staff@example.com", password="StaffP@ss!")
        response = self.client.get(reverse("member-instrument-rental"))
        self.assertEqual(response.status_code, 302)
```

- [ ] **Step 2: Run to verify tests fail**

```bash
python manage.py test blowcomotion.tests.test_instrument_rental.InstrumentRentalRequestViewTest -v 2
```

Expected: `NoReverseMatch` — URL `member-instrument-rental` does not exist yet.

- [ ] **Step 3: Add imports to `member_views.py`**

The current imports in `member_views.py` include several `from blowcomotion.models import ...` and `from blowcomotion.member_auth import ...` lines. Add the missing items:

In the `from blowcomotion.member_auth import (...)` block, add `_MemberEmail`:
```python
from blowcomotion.member_auth import (
    _MemberEmail,
    create_member_user,
    ensure_set_password_flow,
    # ... existing entries ...
)
```

In the `from blowcomotion.member_forms import (...)` block, add `InstrumentRentalRequestForm`:
```python
from blowcomotion.member_forms import (
    # ... existing entries ...
    InstrumentRentalRequestForm,
)
```

Add a models import for the new symbols. Find the line that imports from `blowcomotion.models` (if none exists, add one):
```python
from blowcomotion.models import (
    InstrumentRentalRequestSubmission,
    LibraryInstrument,
    SiteSettings,
)
```

Also ensure `from django.template.loader import render_to_string` is present (add it near the top django imports if missing).

- [ ] **Step 4: Add the view to `member_views.py`**

Append after `requests_view`:

```python
@login_required
def instrument_rental_request(request):
    if not hasattr(request.user, "member"):
        return redirect("/")
    member = request.user.member
    site_settings = SiteSettings.for_request(request)

    if request.method == "POST":
        form = InstrumentRentalRequestForm(request.POST)
        if form.is_valid():
            instrument = form.cleaned_data["instrument"]
            available = instrument.library_inventory.filter(
                status=LibraryInstrument.STATUS_AVAILABLE
            ).count()
            is_waitlist = available == 0

            submission = InstrumentRentalRequestSubmission.objects.create(
                member=member,
                name=member.full_name,
                email=member.email,
                phone=member.phone or "",
                address=member.address or "",
                instrument=instrument,
                is_waitlist=is_waitlist,
                message=form.cleaned_data.get("notes") or "",
                policy_acknowledged=True,
            )

            recipients = [
                r.strip()
                for r in (site_settings.instrument_rental_notification_recipients or "").split(",")
                if r.strip()
            ]
            if recipients:
                status_label = "WAITLIST" if is_waitlist else "ACTIVE REQUEST"
                manager_body = (
                    f"Instrument Rental Request [{status_label}]\n\n"
                    f"Member: {member.full_name}\n"
                    f"Email: {member.email}\n"
                    f"Phone: {member.phone or 'not provided'}\n"
                    f"Address: {member.address or 'not provided'}\n"
                    f"Instrument requested: {instrument.name}\n"
                    f"Waitlist: {'Yes' if is_waitlist else 'No'}\n"
                    f"Notes: {submission.message or '—'}\n"
                )
                _MemberEmail(
                    subject=f"Instrument Rental Request — {member.full_name} ({instrument.name})",
                    body=manager_body,
                    from_email=settings.FROM_EMAIL,
                    to=recipients,
                ).send(fail_silently=True)

            if member.email:
                confirmation_body = render_to_string(
                    "emails/instrument_rental_request_confirmation.txt",
                    {
                        "member": member,
                        "instrument": instrument,
                        "is_waitlist": is_waitlist,
                        "notes": submission.message,
                        "patreon_url": site_settings.patreon_url,
                    },
                )
                _MemberEmail(
                    subject=f"Your instrument rental request — {instrument.name}",
                    body=confirmation_body,
                    from_email=settings.FROM_EMAIL,
                    to=[member.email],
                ).send(fail_silently=True)

            return render(request, "member/instrument_rental_request.html", {
                "member": member,
                "submitted": True,
                "is_waitlist": is_waitlist,
                "instrument": instrument,
                "patreon_url": site_settings.patreon_url,
            })

        return render(request, "member/instrument_rental_request.html", {
            "member": member,
            "form": form,
            "policy_text": site_settings.instrument_rental_policy,
        })

    form = InstrumentRentalRequestForm()
    return render(request, "member/instrument_rental_request.html", {
        "member": member,
        "form": form,
        "policy_text": site_settings.instrument_rental_policy,
    })
```

- [ ] **Step 5: Add the URL to `member_urls.py`**

Find the line:
```python
path("", member_views.member_home, name="member-home"),
```

Add immediately before it:
```python
path("instrument-rental/", member_views.instrument_rental_request, name="member-instrument-rental"),
```

- [ ] **Step 6: Run tests**

```bash
python manage.py test blowcomotion.tests.test_instrument_rental.InstrumentRentalRequestViewTest -v 2
```

Expected: 12 tests — most will fail with `TemplateDoesNotExist` for `member/instrument_rental_request.html`. That's expected — the template is Task 5. Only the redirect and 302 tests should pass. Note which tests are failing with template errors vs logic errors before proceeding.

Actually: all tests that call the view will fail with `TemplateDoesNotExist`. Create a minimal stub template first to unblock test runs:

```bash
touch blowcomotion/templates/member/instrument_rental_request.html
```

Then re-run:
```bash
python manage.py test blowcomotion.tests.test_instrument_rental.InstrumentRentalRequestViewTest -v 2
```

Expected: all 12 tests pass. (The stub template is empty but the view renders it without error.)

- [ ] **Step 7: Run full test suite**

```bash
python manage.py test blowcomotion -v 1
```

Expected: all pass.

- [ ] **Step 8: Commit**

```bash
git add blowcomotion/member_views.py blowcomotion/member_urls.py blowcomotion/tests/test_instrument_rental.py blowcomotion/templates/member/instrument_rental_request.html
git commit -S -m "feat: add instrument rental request view and URL"
```

---

### Task 5: Templates

**Depends on:** Task 4

**Files:**
- Modify: `blowcomotion/templates/member/instrument_rental_request.html` (replace stub)
- Modify: `blowcomotion/templates/member/portal_base.html`
- Create: `blowcomotion/templates/emails/instrument_rental_request_confirmation.txt`

**Interfaces:**
- Consumes GET context: `member`, `form`, `policy_text`
- Consumes POST success context: `member`, `submitted` (True), `is_waitlist`, `instrument`, `patreon_url`

- [ ] **Step 1: Write the form template**

Replace the stub `blowcomotion/templates/member/instrument_rental_request.html` with:

```html
{% extends "member/portal_base.html" %}
{% load wagtailcore_tags %}
{% block title %}Request an Instrument — Blowcomotion{% endblock %}
{% block portal_content %}
<h2 class="mb-4">Request an Instrument</h2>

{% if submitted %}
  <div class="alert alert-success">
    {% if is_waitlist %}
      You've been added to the waitlist for <strong>{{ instrument.name }}</strong>. A library manager will reach out when one becomes available.
    {% else %}
      Your request for <strong>{{ instrument.name }}</strong> has been received. A library manager will be in touch soon.
    {% endif %}
  </div>
  {% if patreon_url %}
  <p class="mt-3">To support the instrument library, please ensure your Patreon membership is active:</p>
  <a href="{{ patreon_url }}" class="site-btn" target="_blank" rel="noopener">Become a Patron</a>
  {% endif %}
{% else %}
  <p>Your contact information on file will be included with this request.
    <a href="{% url 'member-profile' %}">Need to update it?</a>
  </p>

  <div class="card mb-4">
    <div class="card-body">
      <dl class="row mb-0">
        <dt class="col-sm-3">Name</dt><dd class="col-sm-9">{{ member.full_name }}</dd>
        <dt class="col-sm-3">Email</dt><dd class="col-sm-9">{{ member.email }}</dd>
        <dt class="col-sm-3">Phone</dt><dd class="col-sm-9">{{ member.phone|default:"not provided" }}</dd>
        <dt class="col-sm-3">Address</dt><dd class="col-sm-9">{{ member.address|default:"not provided" }}</dd>
      </dl>
    </div>
  </div>

  <form method="post">
    {% csrf_token %}

    <div class="mb-3">
      <label class="form-label fw-semibold" for="{{ form.instrument.id_for_label }}">Instrument *</label>
      {{ form.instrument }}
      {% if form.instrument.errors %}
        <div class="text-danger small mt-1">{{ form.instrument.errors }}</div>
      {% endif %}
    </div>

    <div class="mb-3">
      <label class="form-label" for="{{ form.notes.id_for_label }}">Notes</label>
      {{ form.notes }}
    </div>

    {% if policy_text %}
    <div class="mb-3">
      <label class="form-label fw-semibold">Instrument Lending Policy</label>
      <div class="border rounded p-3" style="max-height:300px;overflow-y:auto;background:#f8f9fa;">
        {{ policy_text|richtext }}
      </div>
    </div>
    {% endif %}

    <div class="mb-4 form-check">
      {{ form.policy_acknowledged }}
      <label class="form-check-label" for="{{ form.policy_acknowledged.id_for_label }}">
        {{ form.policy_acknowledged.label }}
      </label>
      {% if form.policy_acknowledged.errors %}
        <div class="text-danger small mt-1">{{ form.policy_acknowledged.errors }}</div>
      {% endif %}
    </div>

    <button type="submit" class="site-btn">Submit Request</button>
  </form>
{% endif %}
{% endblock %}
```

- [ ] **Step 2: Add the nav link to `portal_base.html`**

Find this line in `blowcomotion/templates/member/portal_base.html`:
```html
<a href="{% url 'member-requests' %}" class="list-group-item list-group-item-action{% if request.resolver_match.url_name == 'member-requests' %} active{% endif %}">My Requests</a>
```

Add directly after it:
```html
<a href="{% url 'member-instrument-rental' %}" class="list-group-item list-group-item-action{% if request.resolver_match.url_name == 'member-instrument-rental' %} active{% endif %}">Request an Instrument</a>
```

- [ ] **Step 3: Create the member confirmation email template**

Create `blowcomotion/templates/emails/instrument_rental_request_confirmation.txt`:

```
Hi {{ member.preferred_name|default:member.first_name }},

Your instrument rental request has been received.

Request details:
  Instrument: {{ instrument.name }}
  Status: {% if is_waitlist %}Waitlist (no units currently available){% else %}Active request{% endif %}
{% if notes %}  Notes: {{ notes }}
{% endif %}
{% if is_waitlist %}You are on the waitlist for {{ instrument.name }}. A library manager will reach out when a unit becomes available.
{% else %}A library manager will be in touch soon to complete your rental.
{% endif %}
{% if patreon_url %}To support the instrument library, please ensure your Patreon membership is active:
{{ patreon_url }}
{% endif %}
Start Wearing Purple,
Blowcomotion
```

- [ ] **Step 4: Run full test suite**

```bash
python manage.py test blowcomotion -v 1
```

Expected: all pass.

- [ ] **Step 5: Collect static and smoke-test in the browser**

```bash
python manage.py collectstatic --noinput
python manage.py runserver
```

Visit `http://localhost:8000/member/instrument-rental/` while logged in. Verify:
- Contact info displays correctly
- Instrument dropdown shows availability labels
- Policy text renders (if set in admin)
- Submitting creates a submission and shows the success state with Patreon link
- "Request an Instrument" appears in the portal nav and highlights when active
- Submitting with no instrument selected shows an inline error

- [ ] **Step 6: Commit**

```bash
git add blowcomotion/templates/member/instrument_rental_request.html blowcomotion/templates/member/portal_base.html blowcomotion/templates/emails/instrument_rental_request_confirmation.txt
git commit -S -m "feat: add instrument rental request templates and portal nav link"
```

---

## Post-Implementation Checklist

- [ ] Set `instrument_rental_notification_recipients` in Wagtail admin (Site Settings) to `instruments@blowcomotion.org`
- [ ] Paste the lending policy text into `instrument_rental_policy` in Site Settings
- [ ] Open a PR against `development` referencing issue #157
