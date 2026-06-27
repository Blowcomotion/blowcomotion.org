# Instrument Rental Modernization v2 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Extend the instrument rental feature with profile guards, 2nd/3rd instrument choices, hide flags on Instrument, a full approval workflow, and a Wagtail admin dashboard for reviewing and actioning requests.

**Architecture:** Model changes land first. The Wagtail admin dashboard uses `register_admin_urls` / `register_admin_menu_item` hooks (same pattern as existing custom admin views in `views.py`). All admin approval/denial email sending uses `_MemberEmail`, already imported in `views.py`. The member portal view adds a rental policy gate and profile completeness guard before rendering the form.

**Tech Stack:** Django 4.x, Wagtail CMS, Django Test Client, Bootstrap 5

## Global Constraints

- GPG-sign all commits: `git commit -S`
- No emojis in commit messages or PR descriptions
- No `Co-Authored-By` lines
- Conventional commit prefixes: `feat:`, `fix:`, `refactor:`, `chore:`
- Branch: `feature/issue-157-instrument-rental` (already checked out)
- Spec: `docs/superpowers/specs/2026-06-25-instrument-rental-v2-design.md`
- After generating any migration: dispatch the `wagtail-migration-reviewer` agent on the migration file before committing it
- Test command: `python manage.py test blowcomotion.tests.test_instrument_rental`
- Full suite: `python manage.py test`
- Edit source files under `blowcomotion/static/`, never under `static/`

---

### Task 1: Model changes, migration, and viewset panel cleanup

**Files:**
- Modify: `blowcomotion/models.py`
- Modify: `blowcomotion/snippet_viewsets.py`
- Modify: `blowcomotion/views.py` (remove dead `LibraryInstrumentDocument` references)
- Create: migration `blowcomotion/migrations/0108_rental_v2.py` (generated)
- Test: `blowcomotion/tests/test_instrument_rental.py`

**Interfaces:**
- Produces: `Instrument.hide_from_rental`, `Instrument.hide_from_member_forms` (BooleanField, default=False)
- Produces: `InstrumentRentalRequestSubmission.STATUS_PENDING = "pending"`, `STATUS_APPROVED = "approved"`, `STATUS_DENIED = "denied"`, `STATUS_CHOICES`
- Produces: `InstrumentRentalRequestSubmission.second_choice` (FK→Instrument, null/blank, on_delete=PROTECT, related_name="rental_requests_second_choice")
- Produces: `InstrumentRentalRequestSubmission.third_choice` (FK→Instrument, null/blank, on_delete=PROTECT, related_name="rental_requests_third_choice")
- Produces: `InstrumentRentalRequestSubmission.status` (CharField, max_length=20, choices=STATUS_CHOICES, default=STATUS_PENDING)
- Produces: `InstrumentRentalRequestSubmission.admin_message` (TextField, blank=True)
- Produces: `InstrumentRentalRequestSubmission.assigned_unit` (FK→LibraryInstrument, null/blank, on_delete=SET_NULL, related_name="rental_assignments")
- Removes: `LibraryInstrument.agreement_signed_date`
- Removes: `LibraryInstrumentDocument` model and table

- [ ] **Step 1: Write failing model tests**

Add to `blowcomotion/tests/test_instrument_rental.py`:

```python
class InstrumentHideFieldsTest(TestCase):
    def test_hide_from_rental_default_false(self):
        instr = Instrument.objects.create(name="Piccolo")
        self.assertFalse(instr.hide_from_rental)

    def test_hide_from_member_forms_default_false(self):
        instr = Instrument.objects.create(name="Piccolo")
        self.assertFalse(instr.hide_from_member_forms)


class RentalSubmissionStatusTest(TestCase):
    def setUp(self):
        self.instrument = make_instrument()
        self.member = make_member()

    def test_default_status_is_pending(self):
        sub = InstrumentRentalRequestSubmission.objects.create(
            name="Sam Player", email="sam@example.com",
            instrument=self.instrument, member=self.member, policy_acknowledged=True,
        )
        self.assertEqual(sub.status, InstrumentRentalRequestSubmission.STATUS_PENDING)

    def test_str_includes_status(self):
        sub = InstrumentRentalRequestSubmission.objects.create(
            name="Sam Player", email="sam@example.com",
            instrument=self.instrument, member=self.member, policy_acknowledged=True,
        )
        self.assertIn("pending", str(sub))
        self.assertIn("Trumpet", str(sub))

    def test_second_and_third_choice_nullable(self):
        sub = InstrumentRentalRequestSubmission.objects.create(
            name="Sam Player", email="sam@example.com",
            instrument=self.instrument, member=self.member, policy_acknowledged=True,
        )
        self.assertIsNone(sub.second_choice)
        self.assertIsNone(sub.third_choice)

    def test_second_choice_can_be_set(self):
        other = Instrument.objects.create(name="Tuba")
        sub = InstrumentRentalRequestSubmission.objects.create(
            name="Sam Player", email="sam@example.com",
            instrument=self.instrument, member=self.member,
            second_choice=other, policy_acknowledged=True,
        )
        sub.refresh_from_db()
        self.assertEqual(sub.second_choice, other)
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
python manage.py test blowcomotion.tests.test_instrument_rental.InstrumentHideFieldsTest blowcomotion.tests.test_instrument_rental.RentalSubmissionStatusTest
```
Expected: `FieldError` or `AttributeError` — new fields don't exist yet.

- [ ] **Step 3: Add hide booleans to `Instrument` in `models.py`**

After the `section` ForeignKey block (around line 493), before the `image` ForeignKey, insert:

```python
    hide_from_rental = models.BooleanField(
        default=False,
        help_text=(
            "Hide from the instrument rental request form. Use for instruments too rare "
            "or unavailable to offer — e.g. a vintage sousaphone kept as a display piece."
        ),
    )
    hide_from_member_forms = models.BooleanField(
        default=False,
        help_text=(
            "Hide from member profile and signup instrument selectors. Use for instruments "
            "that members don't play but exist in inventory — e.g. a prop instrument or "
            "one not assigned to any section."
        ),
    )
```

- [ ] **Step 4: Replace `InstrumentRentalRequestSubmission` in `models.py`**

Replace the entire class (currently lines 2006–2033) with:

```python
class InstrumentRentalRequestSubmission(BaseFormSubmission):
    """Member portal instrument rental requests. `message` field stores optional notes."""

    STATUS_PENDING = "pending"
    STATUS_APPROVED = "approved"
    STATUS_DENIED = "denied"
    STATUS_CHOICES = [
        (STATUS_PENDING, "Pending"),
        (STATUS_APPROVED, "Approved"),
        (STATUS_DENIED, "Denied"),
    ]

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
    second_choice = models.ForeignKey(
        "blowcomotion.Instrument",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="rental_requests_second_choice",
    )
    third_choice = models.ForeignKey(
        "blowcomotion.Instrument",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="rental_requests_third_choice",
    )
    is_waitlist = models.BooleanField(default=False)
    phone = models.CharField(max_length=255, blank=True, null=True)
    address = models.CharField(max_length=255, blank=True, null=True)
    policy_acknowledged = models.BooleanField(default=False)
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default=STATUS_PENDING,
    )
    admin_message = models.TextField(blank=True)
    assigned_unit = models.ForeignKey(
        "blowcomotion.LibraryInstrument",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="rental_assignments",
    )

    def __str__(self):
        return f"{self.name} — {self.instrument} ({self.status}) on {self.date_submitted:%Y-%m-%d}"

    class Meta:
        ordering = ["-date_submitted"]
        verbose_name = "Instrument Rental Request"
        verbose_name_plural = "Instrument Rental Requests"
```

- [ ] **Step 5: Remove `agreement_signed_date` from `LibraryInstrument`**

In `blowcomotion/models.py`, delete lines 1443–1447:

```python
    agreement_signed_date = models.DateField(
        null=True,
        blank=True,
        help_text="Date the rental agreement was signed",
    )
```

- [ ] **Step 6: Delete `LibraryInstrumentDocument` class**

In `blowcomotion/models.py`, delete the entire `LibraryInstrumentDocument` class (lines 1673–~1695, the full class including docstring and all fields). The `ParentalKey` on_delete=CASCADE means Django's migration will drop the table.

- [ ] **Step 7: Update `snippet_viewsets.py`**

In `LibraryInstrumentViewSet.panels`, replace:

```python
        MultiFieldPanel([
            FieldRowPanel([
                'rental_date',
                'agreement_signed_date',
            ]),
        ], heading="Rental Dates"),
```

with:

```python
        MultiFieldPanel([
            'rental_date',
        ], heading="Rental Date"),
```

Also remove this line from panels:

```python
        InlinePanel('rental_documents', label="Rental Documents"),
```

Update `InstrumentRentalRequestSubmissionViewset`:

```python
    list_display = ["name", "email", "instrument", "status", "is_waitlist", "date_submitted"]
    panels = [
        "member",
        "name",
        "email",
        "phone",
        "address",
        "instrument",
        "second_choice",
        "third_choice",
        "is_waitlist",
        "status",
        "admin_message",
        "assigned_unit",
        "message",
        "policy_acknowledged",
    ]
```

- [ ] **Step 8: Clean up dead `LibraryInstrumentDocument` references in `views.py`**

In `blowcomotion/views.py`:

1. Remove `LibraryInstrumentDocument` from the models import block (line 49).

2. Comment out the document-attachment block inside `instrument_library_quick_rent` (lines 181–188):

```python
                    # TODO(#250): remove — LibraryInstrumentDocument dropped in rental v2
                    # rental_document = rent_form.cleaned_data.get('rental_document')
                    # if rental_document:
                    #     LibraryInstrumentDocument.objects.create(
                    #         library_instrument=instrument,
                    #         document=rental_document,
                    #         description=rent_form.cleaned_data.get('document_description', ''),
                    #     )
```

3. Comment out the `agreement_signed_date` assignment lines (166–168 and 218):

```python
                    # TODO(#250): remove — agreement_signed_date dropped in rental v2
                    # instrument.agreement_signed_date = rent_form.cleaned_data[
                    #     'agreement_signed_date'
                    # ]
```

and:

```python
                    # instrument.agreement_signed_date = None  # TODO(#250): remove
```

- [ ] **Step 9: Update existing `__str__` tests**

In `test_instrument_rental.py`, update `InstrumentRentalRequestSubmissionModelTest`:

```python
    def test_str_active_request(self):
        sub = InstrumentRentalRequestSubmission.objects.create(
            name="Sam Player", email="sam@example.com",
            instrument=self.instrument, member=self.member, policy_acknowledged=True,
        )
        self.assertIn("pending", str(sub))
        self.assertIn("Trumpet", str(sub))

    def test_str_waitlist(self):
        sub = InstrumentRentalRequestSubmission.objects.create(
            name="Sam Player", email="sam@example.com",
            instrument=self.instrument, member=self.member,
            is_waitlist=True, policy_acknowledged=True,
        )
        self.assertIn("pending", str(sub))
```

- [ ] **Step 10: Generate migration**

```bash
python manage.py makemigrations --name rental_v2
```

Expected: creates `blowcomotion/migrations/0108_rental_v2.py`

- [ ] **Step 11: Dispatch `wagtail-migration-reviewer` agent**

Pass the generated migration file to the `wagtail-migration-reviewer` agent. Fix any issues it raises before continuing.

- [ ] **Step 12: Apply migration and run tests**

```bash
python manage.py migrate
python manage.py test blowcomotion.tests.test_instrument_rental.InstrumentHideFieldsTest blowcomotion.tests.test_instrument_rental.RentalSubmissionStatusTest blowcomotion.tests.test_instrument_rental.InstrumentRentalRequestSubmissionModelTest
```

Expected: all pass. `InstrumentRentalRequestFormTest` and `InstrumentRentalRequestViewTest` may fail — expected, fixed in later tasks.

- [ ] **Step 13: Commit**

```bash
git add blowcomotion/models.py blowcomotion/snippet_viewsets.py blowcomotion/views.py blowcomotion/migrations/0108_rental_v2.py blowcomotion/tests/test_instrument_rental.py
git commit -S -m "feat: rental v2 model — hide booleans, status/choices, 2nd/3rd choice, remove agreement_signed_date and LibraryInstrumentDocument"
```

---

### Task 2: Form field filtering and 2nd/3rd choice fields

**Files:**
- Modify: `blowcomotion/member_forms.py`
- Modify: `blowcomotion/forms.py`
- Test: `blowcomotion/tests/test_instrument_rental.py`

**Interfaces:**
- Consumes: `Instrument.hide_from_rental`, `Instrument.hide_from_member_forms` from Task 1
- Produces: `InstrumentRentalRequestForm.second_choice` (ModelChoiceField, required=False, same queryset as `instrument`, filtered by `hide_from_rental=False`)
- Produces: `InstrumentRentalRequestForm.third_choice` (ModelChoiceField, required=False, same queryset)
- Produces: `InstrumentRentalRequestForm.instrument` queryset now also filters `hide_from_rental=False`
- Produces: `MemberProfileForm.primary_instrument` and `additional_instruments` querysets filter `hide_from_member_forms=False`
- Produces: `MemberSignupForm.primary_instrument` queryset filters `hide_from_member_forms=False`

- [ ] **Step 1: Write failing form tests**

Add to `blowcomotion/tests/test_instrument_rental.py`:

```python
class InstrumentRentalFormV2Test(TestCase):
    def setUp(self):
        self.visible = make_instrument("Trumpet")
        make_library_instrument(self.visible)
        self.hidden = Instrument.objects.create(name="Vintage Sousaphone", hide_from_rental=True)
        make_library_instrument(self.hidden, serial="RARE001")

    def test_hidden_instrument_excluded_from_rental_form(self):
        form = InstrumentRentalRequestForm()
        pks = list(form.fields["instrument"].queryset.values_list("pk", flat=True))
        self.assertNotIn(self.hidden.pk, pks)
        self.assertIn(self.visible.pk, pks)

    def test_second_choice_optional(self):
        form = InstrumentRentalRequestForm(data={
            "instrument": self.visible.pk,
            "policy_acknowledged": True,
        })
        self.assertTrue(form.is_valid(), form.errors)
        self.assertIsNone(form.cleaned_data["second_choice"])

    def test_second_choice_accepts_valid_instrument(self):
        second = make_instrument("Trombone")
        make_library_instrument(second)
        form = InstrumentRentalRequestForm(data={
            "instrument": self.visible.pk,
            "second_choice": second.pk,
            "policy_acknowledged": True,
        })
        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(form.cleaned_data["second_choice"], second)

    def test_hidden_instrument_excluded_from_second_choice(self):
        form = InstrumentRentalRequestForm()
        pks = list(form.fields["second_choice"].queryset.values_list("pk", flat=True))
        self.assertNotIn(self.hidden.pk, pks)
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
python manage.py test blowcomotion.tests.test_instrument_rental.InstrumentRentalFormV2Test
```

Expected: `AttributeError` — `second_choice` field doesn't exist yet and `hide_from_rental` filter is absent.

- [ ] **Step 3: Replace `InstrumentRentalRequestForm` in `member_forms.py`**

Replace the entire `InstrumentRentalRequestForm` class:

```python
class InstrumentRentalRequestForm(forms.Form):
    instrument = forms.ModelChoiceField(
        queryset=Instrument.objects.none(),
        empty_label="Select an instrument",
        label="Instrument",
        widget=forms.Select(attrs={"class": "form-select"}),
    )
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
            Instrument.objects.filter(hide_from_rental=False)
            .annotate(
                available_count=Count(
                    "library_inventory",
                    filter=Q(library_inventory__status=LibraryInstrument.STATUS_AVAILABLE),
                )
            )
            .filter(library_inventory__isnull=False)
            .distinct()
            .order_by("name")
        )

        def label_fn(obj):
            return (
                f"{obj.name} ({obj.available_count} available)"
                if obj.available_count > 0
                else f"{obj.name} (waitlist — 0 available)"
            )

        for field_name in ("instrument", "second_choice", "third_choice"):
            self.fields[field_name].queryset = qs
            self.fields[field_name].label_from_instance = label_fn
```

- [ ] **Step 4: Update `MemberProfileForm` in `member_forms.py`**

Change the `additional_instruments` class attribute from:

```python
        queryset=Instrument.objects.all().order_by("name"),
```

to:

```python
        queryset=Instrument.objects.filter(hide_from_member_forms=False).order_by("name"),
```

In `MemberProfileForm.__init__`, after `super().__init__(*args, **kwargs)`, add:

```python
        self.fields["primary_instrument"].queryset = Instrument.objects.filter(
            hide_from_member_forms=False
        ).order_by("name")
```

- [ ] **Step 5: Update `MemberSignupForm.primary_instrument` in `forms.py`**

Change the queryset on line 232 from:

```python
        queryset=Instrument.objects.all().order_by('name'),
```

to:

```python
        queryset=Instrument.objects.filter(hide_from_member_forms=False).order_by('name'),
```

- [ ] **Step 6: Run tests**

```bash
python manage.py test blowcomotion.tests.test_instrument_rental.InstrumentRentalFormV2Test blowcomotion.tests.test_instrument_rental.InstrumentRentalRequestFormTest
```

Expected: all pass.

- [ ] **Step 7: Commit**

```bash
git add blowcomotion/member_forms.py blowcomotion/forms.py blowcomotion/tests/test_instrument_rental.py
git commit -S -m "feat: rental v2 forms — hide_from_rental/member_forms filtering, 2nd and 3rd choice fields"
```

---

### Task 3: Member portal view updates

**Files:**
- Modify: `blowcomotion/member_views.py`
- Rename+update: `blowcomotion/templates/emails/instrument_rental_request_confirmation.txt` → `instrument_rental_request_pending.txt`
- Test: `blowcomotion/tests/test_instrument_rental.py`

**Interfaces:**
- Consumes: `InstrumentRentalRequestForm.second_choice`, `.third_choice` from Task 2
- Consumes: `InstrumentRentalRequestSubmission.STATUS_PENDING`, `.second_choice`, `.third_choice` from Task 1
- Produces: `instrument_rental_request` view with: rental policy gate (short-circuits on empty `instrument_rental_policy`), profile completeness guard (redirects to `member-profile` if any of full_name/email/phone/address is empty), saves `second_choice`/`third_choice`/`status=STATUS_PENDING`, sends pending email via `emails/instrument_rental_request_pending.txt`, no `patreon_url` in success context, manager email includes review link via `request.build_absolute_uri(f"/admin/rental-requests/{submission.pk}/")`

- [ ] **Step 1: Update `InstrumentRentalRequestViewTest.setUp` and add failing tests**

In `blowcomotion/tests/test_instrument_rental.py`, update `InstrumentRentalRequestViewTest.setUp` to set a non-empty policy (the new policy gate blocks all requests when empty):

```python
    def setUp(self):
        from wagtail.models import Site
        self.instrument = make_instrument("Trumpet")
        self.li = make_library_instrument(self.instrument, status=LibraryInstrument.STATUS_AVAILABLE)
        self.member = make_member()
        self.user = create_member_user(self.member)
        self.user.set_password("Pass123!")
        self.user.save()
        self.client.login(username="sam@example.com", password="Pass123!")
        self.site_settings = SiteSettings.for_site(Site.objects.get(is_default_site=True))
        self.site_settings.instrument_rental_policy = "You must return the instrument."
        self.site_settings.save()
```

Add new tests to `InstrumentRentalRequestViewTest`:

```python
    def test_get_shows_coming_soon_when_policy_not_set(self):
        self.site_settings.instrument_rental_policy = ""
        self.site_settings.save()
        response = self.client.get(reverse("member-instrument-rental"))
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context["rental_not_configured"])

    def test_post_blocked_when_policy_not_set(self):
        self.site_settings.instrument_rental_policy = ""
        self.site_settings.save()
        self._post()
        self.assertEqual(InstrumentRentalRequestSubmission.objects.count(), 0)

    def test_get_redirects_when_profile_incomplete(self):
        self.member.phone = ""
        self.member.save(sync_go3=False)
        response = self.client.get(reverse("member-instrument-rental"))
        self.assertRedirects(response, reverse("member-profile"), fetch_redirect_response=False)

    def test_post_redirects_when_profile_incomplete(self):
        self.member.address = ""
        self.member.save(sync_go3=False)
        response = self._post()
        self.assertRedirects(response, reverse("member-profile"), fetch_redirect_response=False)

    def test_post_saves_second_and_third_choice(self):
        second = make_instrument("Trombone")
        make_library_instrument(second)
        third = make_instrument("Tuba")
        make_library_instrument(third)
        self.client.post(reverse("member-instrument-rental"), {
            "instrument": self.instrument.pk,
            "second_choice": second.pk,
            "third_choice": third.pk,
            "policy_acknowledged": True,
        })
        sub = InstrumentRentalRequestSubmission.objects.first()
        self.assertEqual(sub.second_choice, second)
        self.assertEqual(sub.third_choice, third)

    def test_post_sets_status_pending(self):
        self._post()
        sub = InstrumentRentalRequestSubmission.objects.first()
        self.assertEqual(sub.status, InstrumentRentalRequestSubmission.STATUS_PENDING)

    def test_post_success_no_patreon_in_context(self):
        response = self._post()
        self.assertNotIn("patreon_url", response.context)
```

- [ ] **Step 2: Run tests to verify new ones fail**

```bash
python manage.py test blowcomotion.tests.test_instrument_rental.InstrumentRentalRequestViewTest
```

Expected: several failures — policy gate, profile guard, second/third choice, patreon context.

- [ ] **Step 3: Rename and update the pending email template**

```bash
git mv blowcomotion/templates/emails/instrument_rental_request_confirmation.txt blowcomotion/templates/emails/instrument_rental_request_pending.txt
```

Update the content of `blowcomotion/templates/emails/instrument_rental_request_pending.txt`:

```
Dear {{ member.full_name }},

Thank you for submitting an instrument rental request. We have received your request for the following:

First choice: {{ instrument.name }}{% if second_choice %}
Second choice: {{ second_choice.name }}{% endif %}{% if third_choice %}
Third choice: {{ third_choice.name }}{% endif %}

{% if notes %}Notes you provided: {{ notes }}

{% endif %}Our library team will review your request and follow up soon. If you have any questions, please reach out.

— Blowcomotion Instrument Library
```

- [ ] **Step 4: Replace `instrument_rental_request` view in `member_views.py`**

Ensure `InstrumentRentalRequestSubmission` is in the import from `blowcomotion.models` (it should already be there from Task 1; add it if missing).

Replace the entire `instrument_rental_request` function (lines 300–389):

```python
@login_required
def instrument_rental_request(request):
    if not hasattr(request.user, "member"):
        return redirect("/")
    member = request.user.member
    site_settings = SiteSettings.for_request(request)

    if not site_settings.instrument_rental_policy:
        return render(request, "member/instrument_rental_request.html", {
            "member": member,
            "rental_not_configured": True,
        })

    required = [member.full_name, member.email, member.phone, member.address]
    if not all(required):
        messages.warning(
            request,
            "Please complete your contact information before requesting an instrument rental.",
        )
        return redirect("member-profile")

    if request.method == "POST":
        form = InstrumentRentalRequestForm(request.POST)
        if form.is_valid():
            instrument = form.cleaned_data["instrument"]
            second_choice = form.cleaned_data.get("second_choice")
            third_choice = form.cleaned_data.get("third_choice")
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
                second_choice=second_choice,
                third_choice=third_choice,
                is_waitlist=is_waitlist,
                message=form.cleaned_data.get("notes") or "",
                policy_acknowledged=True,
                status=InstrumentRentalRequestSubmission.STATUS_PENDING,
            )

            recipients = [
                r.strip()
                for r in (site_settings.instrument_rental_notification_recipients or "").split(",")
                if r.strip()
            ]
            if recipients:
                choices_text = f"1st choice: {instrument.name}"
                if second_choice:
                    choices_text += f"\n2nd choice: {second_choice.name}"
                if third_choice:
                    choices_text += f"\n3rd choice: {third_choice.name}"
                review_url = request.build_absolute_uri(f"/admin/rental-requests/{submission.pk}/")
                manager_body = (
                    f"Instrument Rental Request [PENDING]\n\n"
                    f"Member: {member.full_name}\n"
                    f"Email: {member.email}\n"
                    f"Phone: {member.phone or 'not provided'}\n"
                    f"Address: {member.address or 'not provided'}\n"
                    f"{choices_text}\n"
                    f"Notes: {submission.message or '—'}\n\n"
                    f"Review and approve/deny:\n{review_url}\n"
                )
                _MemberEmail(
                    subject=f"Instrument Rental Request — {member.full_name} ({instrument.name})",
                    body=manager_body,
                    from_email=settings.FROM_EMAIL,
                    to=recipients,
                ).send(fail_silently=True)

            if member.email:
                pending_body = render_to_string(
                    "emails/instrument_rental_request_pending.txt",
                    {
                        "member": member,
                        "instrument": instrument,
                        "second_choice": second_choice,
                        "third_choice": third_choice,
                        "notes": submission.message,
                    },
                )
                _MemberEmail(
                    subject=f"Your instrument rental request — {instrument.name}",
                    body=pending_body,
                    from_email=settings.FROM_EMAIL,
                    to=[member.email],
                ).send(fail_silently=True)

            return render(request, "member/instrument_rental_request.html", {
                "member": member,
                "submitted": True,
                "is_waitlist": is_waitlist,
                "instrument": instrument,
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

- [ ] **Step 5: Run view tests**

```bash
python manage.py test blowcomotion.tests.test_instrument_rental.InstrumentRentalRequestViewTest
```

Expected: all pass.

- [ ] **Step 6: Commit**

```bash
git add blowcomotion/member_views.py blowcomotion/templates/emails/ blowcomotion/tests/test_instrument_rental.py
git commit -S -m "feat: rental v2 view — policy gate, profile guard, 2nd/3rd choice, pending email"
```

---

### Task 4: Wagtail admin views, hooks, and approval/denial email templates

**Files:**
- Modify: `blowcomotion/views.py`
- Modify: `blowcomotion/wagtail_hooks.py`
- Create: `blowcomotion/templates/wagtailadmin/rental_requests_dashboard.html`
- Create: `blowcomotion/templates/wagtailadmin/rental_request_review.html`
- Create: `blowcomotion/templates/emails/instrument_rental_request_approved.txt`
- Create: `blowcomotion/templates/emails/instrument_rental_request_denied.txt`
- Test: `blowcomotion/tests/test_instrument_rental.py`

**Interfaces:**
- Consumes: `InstrumentRentalRequestSubmission.STATUS_*`, `.status`, `.admin_message`, `.assigned_unit`, `.second_choice`, `.third_choice` from Task 1
- Consumes: `LibraryInstrument.STATUS_RENTED`, `Member.renting` — existing fields
- Consumes: `_MemberEmail` — already imported in `views.py` (line 33)
- Produces: URL name `rental_requests_dashboard` → `GET /admin/rental-requests/`
- Produces: URL name `rental_request_review` → `GET/POST /admin/rental-requests/<int:pk>/`

- [ ] **Step 1: Write failing admin view tests**

Add to `blowcomotion/tests/test_instrument_rental.py`:

```python
from unittest.mock import patch

from django.urls import reverse


class RentalRequestsAdminViewTest(TestCase):
    def setUp(self):
        from django.contrib.auth import get_user_model
        User = get_user_model()
        self.instrument = make_instrument("Trumpet")
        self.li = make_library_instrument(self.instrument)
        self.member = make_member()
        self.submission = InstrumentRentalRequestSubmission.objects.create(
            name=self.member.full_name,
            email=self.member.email,
            instrument=self.instrument,
            member=self.member,
            status=InstrumentRentalRequestSubmission.STATUS_PENDING,
            policy_acknowledged=True,
        )
        self.admin_user = User.objects.create_superuser(
            username="admin@example.com",
            email="admin@example.com",
            password="AdminP@ss!",
        )
        self.client.force_login(self.admin_user)

    def test_dashboard_returns_200(self):
        response = self.client.get(reverse("rental_requests_dashboard"))
        self.assertEqual(response.status_code, 200)

    def test_review_get_returns_200(self):
        response = self.client.get(reverse("rental_request_review", args=[self.submission.pk]))
        self.assertEqual(response.status_code, 200)

    def test_dashboard_requires_login(self):
        self.client.logout()
        response = self.client.get(reverse("rental_requests_dashboard"))
        self.assertIn(response.status_code, [302, 403])

    @patch("blowcomotion.views._MemberEmail")
    def test_approve_updates_submission_and_unit(self, mock_email_cls):
        mock_email_cls.return_value.send.return_value = None
        self.client.post(
            reverse("rental_request_review", args=[self.submission.pk]),
            {"action": "approve", "unit": self.li.pk, "message": "Pick up Tuesday."},
        )
        self.submission.refresh_from_db()
        self.assertEqual(self.submission.status, InstrumentRentalRequestSubmission.STATUS_APPROVED)
        self.assertEqual(self.submission.assigned_unit, self.li)
        self.li.refresh_from_db()
        self.assertEqual(self.li.status, LibraryInstrument.STATUS_RENTED)
        self.assertEqual(self.li.member, self.member)

    @patch("blowcomotion.views._MemberEmail")
    def test_approve_sets_member_renting(self, mock_email_cls):
        mock_email_cls.return_value.send.return_value = None
        self.client.post(
            reverse("rental_request_review", args=[self.submission.pk]),
            {"action": "approve", "unit": self.li.pk, "message": "Go ahead."},
        )
        self.member.refresh_from_db()
        self.assertTrue(self.member.renting)

    @patch("blowcomotion.views._MemberEmail")
    def test_approve_sends_email(self, mock_email_cls):
        mock_email_cls.return_value.send.return_value = None
        self.client.post(
            reverse("rental_request_review", args=[self.submission.pk]),
            {"action": "approve", "unit": self.li.pk, "message": "Approved."},
        )
        self.assertEqual(mock_email_cls.call_count, 1)

    @patch("blowcomotion.views._MemberEmail")
    def test_deny_updates_submission(self, mock_email_cls):
        mock_email_cls.return_value.send.return_value = None
        self.client.post(
            reverse("rental_request_review", args=[self.submission.pk]),
            {"action": "deny", "message": "No units available."},
        )
        self.submission.refresh_from_db()
        self.assertEqual(self.submission.status, InstrumentRentalRequestSubmission.STATUS_DENIED)
        self.assertEqual(self.submission.admin_message, "No units available.")

    def test_approve_without_unit_stays_pending(self):
        self.client.post(
            reverse("rental_request_review", args=[self.submission.pk]),
            {"action": "approve", "message": "Approved."},
        )
        self.submission.refresh_from_db()
        self.assertEqual(self.submission.status, InstrumentRentalRequestSubmission.STATUS_PENDING)

    def test_action_on_non_pending_submission_does_nothing(self):
        self.submission.status = InstrumentRentalRequestSubmission.STATUS_APPROVED
        self.submission.save()
        self.client.post(
            reverse("rental_request_review", args=[self.submission.pk]),
            {"action": "deny", "message": "Denied."},
        )
        self.submission.refresh_from_db()
        self.assertEqual(self.submission.status, InstrumentRentalRequestSubmission.STATUS_APPROVED)
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
python manage.py test blowcomotion.tests.test_instrument_rental.RentalRequestsAdminViewTest
```

Expected: `NoReverseMatch` — URLs don't exist yet.

- [ ] **Step 3: Add `RentalRequestReviewForm` and admin views to `views.py`**

Add to the imports in `views.py`:

```python
from django import forms as django_forms
from django.template.loader import render_to_string
```

Add `InstrumentRentalRequestSubmission` to the `from blowcomotion.models import (...)` block.

Append at the bottom of `views.py`:

```python
# ── Rental Request Admin Views ──────────────────────────────────────────────────


class RentalRequestReviewForm(django_forms.Form):
    unit = django_forms.ModelChoiceField(
        queryset=LibraryInstrument.objects.none(),
        required=False,
        empty_label="Select a unit to assign",
        label="Assign instrument unit",
    )
    message = django_forms.CharField(
        widget=django_forms.Textarea(attrs={"rows": 4}),
        label="Message to member",
        required=True,
    )

    def __init__(self, *args, submission=None, **kwargs):
        super().__init__(*args, **kwargs)
        if submission:
            choices = [submission.instrument]
            if submission.second_choice:
                choices.append(submission.second_choice)
            if submission.third_choice:
                choices.append(submission.third_choice)
            qs = LibraryInstrument.objects.filter(
                status=LibraryInstrument.STATUS_AVAILABLE,
                instrument__in=choices,
            ).select_related("instrument")
            self.fields["unit"].queryset = qs
            self.fields["unit"].label_from_instance = (
                lambda obj: f"{obj.instrument.name} — {obj.serial_number}"
            )


def _send_rental_approved_email(request, submission):
    if not (submission.member and submission.member.email):
        return
    site_settings = SiteSettings.for_request(request)
    body = render_to_string(
        "emails/instrument_rental_request_approved.txt",
        {
            "member": submission.member,
            "instrument": submission.instrument,
            "assigned_unit": submission.assigned_unit,
            "admin_message": submission.admin_message,
            "patreon_url": site_settings.patreon_url,
        },
    )
    _MemberEmail(
        subject=f"Your instrument rental request has been approved — {submission.instrument.name}",
        body=body,
        from_email=settings.FROM_EMAIL,
        to=[submission.member.email],
    ).send(fail_silently=True)


def _send_rental_denied_email(submission):
    if not (submission.member and submission.member.email):
        return
    body = render_to_string(
        "emails/instrument_rental_request_denied.txt",
        {
            "member": submission.member,
            "instrument": submission.instrument,
            "admin_message": submission.admin_message,
        },
    )
    _MemberEmail(
        subject=f"Your instrument rental request — {submission.instrument.name}",
        body=body,
        from_email=settings.FROM_EMAIL,
        to=[submission.member.email],
    ).send(fail_silently=True)


def rental_requests_dashboard(request):
    from django.db.models import Case, IntegerField, Value, When
    submissions = (
        InstrumentRentalRequestSubmission.objects.annotate(
            status_order=Case(
                When(status=InstrumentRentalRequestSubmission.STATUS_PENDING, then=Value(0)),
                default=Value(1),
                output_field=IntegerField(),
            )
        )
        .order_by("status_order", "-date_submitted")
        .select_related("member", "instrument", "second_choice", "third_choice")
    )
    return render(request, "wagtailadmin/rental_requests_dashboard.html", {
        "submissions": submissions,
    })


def rental_request_review(request, pk):
    submission = get_object_or_404(InstrumentRentalRequestSubmission, pk=pk)
    form = RentalRequestReviewForm(submission=submission)

    if (
        request.method == "POST"
        and submission.status == InstrumentRentalRequestSubmission.STATUS_PENDING
    ):
        action = request.POST.get("action")
        form = RentalRequestReviewForm(request.POST, submission=submission)
        if form.is_valid():
            unit = form.cleaned_data.get("unit")
            message = form.cleaned_data["message"]
            if action == "approve":
                if not unit:
                    form.add_error("unit", "Please select a unit to assign for approval.")
                else:
                    unit.member = submission.member
                    unit.status = LibraryInstrument.STATUS_RENTED
                    unit.rental_date = date.today()
                    unit.save()
                    if submission.member:
                        submission.member.renting = True
                        submission.member.save()
                    submission.status = InstrumentRentalRequestSubmission.STATUS_APPROVED
                    submission.admin_message = message
                    submission.assigned_unit = unit
                    submission.save()
                    _send_rental_approved_email(request, submission)
                    messages.success(request, f"Approved — {submission.name} has been notified.")
                    return redirect("rental_requests_dashboard")
            elif action == "deny":
                submission.status = InstrumentRentalRequestSubmission.STATUS_DENIED
                submission.admin_message = message
                submission.save()
                _send_rental_denied_email(submission)
                messages.success(request, f"Denied — {submission.name} has been notified.")
                return redirect("rental_requests_dashboard")

    return render(request, "wagtailadmin/rental_request_review.html", {
        "submission": submission,
        "form": form,
    })
```

- [ ] **Step 4: Register URLs and new menu item in `wagtail_hooks.py`**

Add to the imports at the top of `wagtail_hooks.py` (inside the `from blowcomotion.views import (...)` block):

```python
    rental_request_review,
    rental_requests_dashboard,
```

In `register_admin_urls()`, add to the returned list:

```python
        path("rental-requests/", rental_requests_dashboard, name="rental_requests_dashboard"),
        path("rental-requests/<int:pk>/", rental_request_review, name="rental_request_review"),
```

Comment out the existing Quick Rent URL entry in `register_admin_urls()`:

```python
        # TODO(#250): delete — replaced by Rental Requests dashboard
        # path(
        #     "instrument-library/manage/",
        #     instrument_library_quick_rent,
        #     name="instrument_library_quick_rent",
        # ),
```

Remove `instrument_library_quick_rent` from the `from blowcomotion.views import (...)` block at the top of `wagtail_hooks.py`.

Comment out the `register_library_quick_rent_menu_item` hook entirely:

```python
# TODO(#250): delete — replaced by Rental Requests dashboard
# @hooks.register("register_admin_menu_item")
# def register_library_quick_rent_menu_item():
#     return MenuItem(
#         'Library: Quick Rent',
#         reverse('instrument_library_quick_rent'),
#         icon_name='french-horn',
#         order=295,
#     )
```

Add the replacement menu item after the comment block:

```python
@hooks.register("register_admin_menu_item")
def register_rental_requests_menu_item():
    return MenuItem(
        "Rental Requests",
        reverse("rental_requests_dashboard"),
        icon_name="french-horn",
        order=295,
    )
```

- [ ] **Step 5: Create email templates**

Create `blowcomotion/templates/emails/instrument_rental_request_approved.txt`:

```
Dear {{ member.full_name }},

Great news — your instrument rental request has been approved.

Instrument assigned: {{ assigned_unit.instrument.name }} (Serial: {{ assigned_unit.serial_number }})

Message from the library team:
{{ admin_message }}

{% if patreon_url %}To support the instrument library, please ensure your Patreon membership is active before pickup:
{{ patreon_url }}

{% endif %}Please reach out if you have any questions about your rental.

— Blowcomotion Instrument Library
```

Create `blowcomotion/templates/emails/instrument_rental_request_denied.txt`:

```
Dear {{ member.full_name }},

Thank you for your interest in renting a {{ instrument.name }}.

After reviewing your request, we are unable to fulfill it at this time.

Message from the library team:
{{ admin_message }}

If you have any questions, please don't hesitate to reach out.

— Blowcomotion Instrument Library
```

- [ ] **Step 6: Create Wagtail admin templates**

Create `blowcomotion/templates/wagtailadmin/rental_requests_dashboard.html`:

```html
{% extends "wagtailadmin/base.html" %}
{% block titletag %}Rental Requests{% endblock %}
{% block content %}
<div class="nice-padding">
    <h1>Rental Requests</h1>
    <table class="listing">
        <thead>
            <tr>
                <th>Member</th>
                <th>1st Choice</th>
                <th>2nd Choice</th>
                <th>3rd Choice</th>
                <th>Submitted</th>
                <th>Status</th>
                <th></th>
            </tr>
        </thead>
        <tbody>
            {% for sub in submissions %}
            <tr>
                <td>{{ sub.name }}<br><small>{{ sub.email }}</small></td>
                <td>{{ sub.instrument }}</td>
                <td>{{ sub.second_choice|default:"—" }}</td>
                <td>{{ sub.third_choice|default:"—" }}</td>
                <td>{{ sub.date_submitted|date:"Y-m-d" }}</td>
                <td>{{ sub.get_status_display }}</td>
                <td>
                    <a href="{% url 'rental_request_review' sub.pk %}"
                       class="button button-small{% if sub.status != 'pending' %} button-secondary{% endif %}">
                        {% if sub.status == 'pending' %}Review{% else %}View{% endif %}
                    </a>
                </td>
            </tr>
            {% empty %}
            <tr><td colspan="7" class="no-results-message">No rental requests yet.</td></tr>
            {% endfor %}
        </tbody>
    </table>
</div>
{% endblock %}
```

Create `blowcomotion/templates/wagtailadmin/rental_request_review.html`:

```html
{% extends "wagtailadmin/base.html" %}
{% block titletag %}Review Rental Request{% endblock %}
{% block content %}
<div class="nice-padding">
    <h1>Review Rental Request</h1>
    <p><a href="{% url 'rental_requests_dashboard' %}" class="button button-secondary">Back to Rental Requests</a></p>

    <section class="w-panel">
        <header class="w-panel__header"><h2 class="w-panel__heading">Request Details</h2></header>
        <div class="w-panel__content">
            <dl class="dl-horizontal">
                <dt>Member</dt><dd>{{ submission.name }} ({{ submission.email }})</dd>
                <dt>Phone</dt><dd>{{ submission.phone|default:"—" }}</dd>
                <dt>Address</dt><dd>{{ submission.address|default:"—" }}</dd>
                <dt>1st Choice</dt><dd>{{ submission.instrument }}</dd>
                <dt>2nd Choice</dt><dd>{{ submission.second_choice|default:"—" }}</dd>
                <dt>3rd Choice</dt><dd>{{ submission.third_choice|default:"—" }}</dd>
                <dt>Notes</dt><dd>{{ submission.message|default:"—" }}</dd>
                <dt>Submitted</dt><dd>{{ submission.date_submitted|date:"Y-m-d H:i" }}</dd>
                <dt>Status</dt><dd>{{ submission.get_status_display }}</dd>
                {% if submission.admin_message %}
                <dt>Admin Message</dt><dd>{{ submission.admin_message }}</dd>
                {% endif %}
                {% if submission.assigned_unit %}
                <dt>Assigned Unit</dt><dd>{{ submission.assigned_unit }}</dd>
                {% endif %}
            </dl>
        </div>
    </section>

    {% if submission.status == 'pending' %}
    <section class="w-panel" style="margin-top:1.5rem;">
        <header class="w-panel__header"><h2 class="w-panel__heading">Approve or Deny</h2></header>
        <div class="w-panel__content">
            <form method="post">
                {% csrf_token %}
                <div class="field">
                    <label class="field__label">Assign Instrument Unit</label>
                    <div class="field-content">{{ form.unit }}</div>
                    {% if form.unit.errors %}<p class="error-message"><span>{{ form.unit.errors|join:", " }}</span></p>{% endif %}
                </div>
                <div class="field">
                    <label class="field__label required">Message to Member</label>
                    <div class="field-content">{{ form.message }}</div>
                    {% if form.message.errors %}<p class="error-message"><span>{{ form.message.errors|join:", " }}</span></p>{% endif %}
                </div>
                <div style="display:flex;gap:1rem;margin-top:1rem;">
                    <button type="submit" name="action" value="approve" class="button">Approve</button>
                    <button type="submit" name="action" value="deny" class="button warning">Deny</button>
                </div>
            </form>
        </div>
    </section>
    {% endif %}
</div>
{% endblock %}
```

- [ ] **Step 7: Run admin view tests**

```bash
python manage.py test blowcomotion.tests.test_instrument_rental.RentalRequestsAdminViewTest
```

Expected: all pass.

- [ ] **Step 8: Run full instrument rental test suite**

```bash
python manage.py test blowcomotion.tests.test_instrument_rental
```

Expected: all pass.

- [ ] **Step 9: Commit**

```bash
git add blowcomotion/views.py blowcomotion/wagtail_hooks.py \
    blowcomotion/templates/wagtailadmin/ \
    blowcomotion/templates/emails/instrument_rental_request_approved.txt \
    blowcomotion/templates/emails/instrument_rental_request_denied.txt \
    blowcomotion/tests/test_instrument_rental.py
git commit -S -m "feat: rental v2 admin — approve/deny dashboard, Rental Requests menu, deprecate Quick Rent"
```

---

### Task 5: Member-facing template update

**Files:**
- Modify: `blowcomotion/templates/member/instrument_rental_request.html`
- Test: `blowcomotion/tests/test_instrument_rental.py`

**Interfaces:**
- Consumes: `rental_not_configured` context bool from Task 3
- Consumes: `form.second_choice`, `form.third_choice` fields from Task 2
- Consumes: no `patreon_url` in success context (removed in Task 3)

- [ ] **Step 1: Write failing template tests**

Add to `blowcomotion/tests/test_instrument_rental.py`:

```python
class InstrumentRentalTemplateTest(TestCase):
    def setUp(self):
        from wagtail.models import Site
        self.instrument = make_instrument("Trumpet")
        make_library_instrument(self.instrument)
        self.member = make_member()
        self.user = create_member_user(self.member)
        self.user.set_password("Pass123!")
        self.user.save()
        self.client.login(username="sam@example.com", password="Pass123!")
        self.site_settings = SiteSettings.for_site(Site.objects.get(is_default_site=True))
        self.site_settings.instrument_rental_policy = "You must return it."
        self.site_settings.save()

    def test_form_shows_coming_soon_when_policy_not_set(self):
        self.site_settings.instrument_rental_policy = ""
        self.site_settings.save()
        response = self.client.get(reverse("member-instrument-rental"))
        self.assertContains(response, "Coming soon")

    def test_form_shows_second_and_third_choice_fields(self):
        response = self.client.get(reverse("member-instrument-rental"))
        self.assertContains(response, "Second choice")
        self.assertContains(response, "Third choice")

    def test_success_state_has_no_patreon_prompt(self):
        with patch("blowcomotion.member_views._MemberEmail"):
            response = self.client.post(reverse("member-instrument-rental"), {
                "instrument": self.instrument.pk,
                "policy_acknowledged": True,
            })
        self.assertNotContains(response, "Patreon")
        self.assertNotContains(response, "patreon")

    def test_success_state_shows_in_touch(self):
        with patch("blowcomotion.member_views._MemberEmail"):
            response = self.client.post(reverse("member-instrument-rental"), {
                "instrument": self.instrument.pk,
                "policy_acknowledged": True,
            })
        self.assertContains(response, "in touch")
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
python manage.py test blowcomotion.tests.test_instrument_rental.InstrumentRentalTemplateTest
```

Expected: `test_form_shows_coming_soon_when_policy_not_set`, `test_form_shows_second_and_third_choice_fields`, `test_success_state_has_no_patreon_prompt` fail.

- [ ] **Step 3: Replace the template**

Replace `blowcomotion/templates/member/instrument_rental_request.html`:

```html
{% extends "member/portal_base.html" %}
{% load wagtailcore_tags %}
{% block title %}Request an Instrument — Blowcomotion{% endblock %}
{% block portal_content %}
<h2 class="mb-4">Request an Instrument</h2>

{% if rental_not_configured %}
  <div class="alert alert-info">
    <strong>Coming soon.</strong> The instrument rental request form will be available once the rental policy is configured.
  </div>
{% elif submitted %}
  <div class="alert alert-success">
    {% if is_waitlist %}
      You've been added to the waitlist for <strong>{{ instrument.name }}</strong>. The library team will be in touch when one becomes available.
    {% else %}
      Your request for <strong>{{ instrument.name }}</strong> has been received. The library team will review it and be in touch soon.
    {% endif %}
  </div>
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
      {% if form.instrument.errors %}<div class="text-danger small mt-1">{{ form.instrument.errors }}</div>{% endif %}
    </div>

    <div class="mb-3">
      <label class="form-label" for="{{ form.second_choice.id_for_label }}">Second choice (optional)</label>
      {{ form.second_choice }}
      {% if form.second_choice.errors %}<div class="text-danger small mt-1">{{ form.second_choice.errors }}</div>{% endif %}
    </div>

    <div class="mb-3">
      <label class="form-label" for="{{ form.third_choice.id_for_label }}">Third choice (optional)</label>
      {{ form.third_choice }}
      {% if form.third_choice.errors %}<div class="text-danger small mt-1">{{ form.third_choice.errors }}</div>{% endif %}
    </div>

    <div class="mb-3">
      <label class="form-label" for="{{ form.notes.id_for_label }}">Notes (optional)</label>
      {{ form.notes }}
      {% if form.notes.errors %}<div class="text-danger small mt-1">{{ form.notes.errors }}</div>{% endif %}
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
        I have read and agree to the Instrument Lending Policy
      </label>
      {% if form.policy_acknowledged.errors %}<div class="text-danger small mt-1">{{ form.policy_acknowledged.errors }}</div>{% endif %}
    </div>

    <button type="submit" class="site-btn">Submit Request</button>
  </form>
{% endif %}
{% endblock %}
```

- [ ] **Step 4: Run template tests**

```bash
python manage.py test blowcomotion.tests.test_instrument_rental.InstrumentRentalTemplateTest
```

Expected: all pass.

- [ ] **Step 5: Run full test suite**

```bash
python manage.py test blowcomotion.tests.test_instrument_rental
```

Expected: all pass.

- [ ] **Step 6: Commit**

```bash
git add blowcomotion/templates/member/instrument_rental_request.html blowcomotion/tests/test_instrument_rental.py
git commit -S -m "feat: rental v2 template — policy gate, 2nd/3rd choice dropdowns, updated success state"
```
