# Member Profile Revision Logging Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Record a full Wagtail revision snapshot each time a member saves their profile at `/member/profile`, visible in the existing Wagtail admin history page.

**Architecture:** Add `RevisionMixin` to the `Member` model (migration required), then call `save_revision()` in `profile_view` after additional instruments are rebuilt so the snapshot captures the full member state.

**Tech Stack:** Django, Wagtail (RevisionMixin, Revision), modelcluster (ClusterableModel, ParentalKey)

## Global Constraints

- `RevisionMixin` is already imported in `blowcomotion/models.py` — do not add a duplicate import
- GPG-sign all commits (`git commit -S`)
- No `Co-Authored-By` or AI sign-off in commit messages
- No emojis anywhere

---

### Task 1: Add `RevisionMixin` to `Member` and generate migration

**Files:**
- Modify: `blowcomotion/models.py:517`
- Create: `blowcomotion/migrations/XXXX_member_latest_revision.py` (generated)

**Interfaces:**
- Produces: `Member` model with `RevisionMixin`, `latest_revision` FK, and `save_revision()` method available on instances

- [ ] **Step 1: Add `RevisionMixin` to `Member`**

In `blowcomotion/models.py`, line 517, change:

```python
class Member(ClusterableModel, index.Indexed):
```

to:

```python
class Member(RevisionMixin, ClusterableModel, index.Indexed):
```

`RevisionMixin` is already imported on line 19 — no import change needed.

- [ ] **Step 2: Generate the migration**

```bash
python manage.py makemigrations blowcomotion --name member_latest_revision
```

Expected output: `Migrations for 'blowcomotion': blowcomotion/migrations/XXXX_member_latest_revision.py`

The migration adds a `latest_revision` FK to `wagtailcore_revision` on the `Member` table.

- [ ] **Step 3: Apply the migration**

```bash
python manage.py migrate blowcomotion
```

Expected output: `Applying blowcomotion.XXXX_member_latest_revision... OK`

- [ ] **Step 4: Confirm no existing tests break**

```bash
python manage.py test blowcomotion.tests.test_member_portal --verbosity=2
```

Expected: all existing tests pass.

- [ ] **Step 5: Commit**

```bash
git add blowcomotion/models.py blowcomotion/migrations/
git commit -S -m "feat: add RevisionMixin to Member model"
```

---

### Task 2: Call `save_revision()` in `profile_view` and add a test

**Files:**
- Modify: `blowcomotion/member_views.py:240-258`
- Modify: `blowcomotion/tests/test_member_portal.py`

**Interfaces:**
- Consumes: `Member.save_revision(user, log_action)` from Task 1
- Consumes: `wagtail.models.Revision` for test assertion

- [ ] **Step 1: Write the failing test**

In `blowcomotion/tests/test_member_portal.py`, add this import at the top:

```python
from wagtail.models import Revision
```

Add this test to the existing `ProfileViewTests` class:

```python
def test_profile_save_creates_revision(self):
    self.client.post(
        reverse("member-profile"),
        {
            "first_name": "Robin",
            "last_name": "Player",
            "preferred_name": "Robbie",
            "email": "robin@example.com",
            "notify_rental_updates": True,
            "notify_reminders": True,
            "notify_announcements": True,
        },
    )
    self.assertEqual(Revision.objects.for_instance(self.member).count(), 1)
    revision = Revision.objects.for_instance(self.member).first()
    self.assertEqual(revision.user, self.user)
```

- [ ] **Step 2: Run the test to verify it fails**

```bash
python manage.py test blowcomotion.tests.test_member_portal.ProfileViewTests.test_profile_save_creates_revision --verbosity=2
```

Expected: FAIL — `AssertionError: 0 != 1` (no revision created yet)

- [ ] **Step 3: Add `save_revision()` call in `profile_view`**

In `blowcomotion/member_views.py`, find the block starting at line 246 (after the `additional_instruments` rebuild). The current code looks like:

```python
            # Rebuild additional instruments
            member.additional_instruments.all().delete()
            for instrument in form.cleaned_data.get("additional_instruments", []):
                MemberInstrument.objects.create(member=member, instrument=instrument)

            if email_changed:
```

Change it to:

```python
            # Rebuild additional instruments
            member.additional_instruments.all().delete()
            for instrument in form.cleaned_data.get("additional_instruments", []):
                MemberInstrument.objects.create(member=member, instrument=instrument)

            instance.save_revision(user=request.user, log_action="wagtail.edit")

            if email_changed:
```

- [ ] **Step 4: Run the test to verify it passes**

```bash
python manage.py test blowcomotion.tests.test_member_portal.ProfileViewTests.test_profile_save_creates_revision --verbosity=2
```

Expected: PASS

- [ ] **Step 5: Run the full portal test suite**

```bash
python manage.py test blowcomotion.tests.test_member_portal --verbosity=2
```

Expected: all tests pass.

- [ ] **Step 6: Commit**

```bash
git add blowcomotion/member_views.py blowcomotion/tests/test_member_portal.py
git commit -S -m "feat: save revision on member profile update"
```

---

## Manual Verification

After both tasks are complete:

1. Log into the member portal at `/member/profile` as a member and save a change
2. In Wagtail admin, navigate to `Snippets > Members`, open that member, and click `History`
3. Confirm a new "edited" entry appears with the member's user and timestamp
