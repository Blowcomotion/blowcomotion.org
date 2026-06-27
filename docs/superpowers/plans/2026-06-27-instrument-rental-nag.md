# Instrument Rental Nag Email Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a daily management command that emails instrument renters who haven't shown up to rehearsal or whose Patreon membership is inactive, with CTA links that trigger admin notification emails.

**Architecture:** Three independent layers — (1) DB models/migration, (2) management command with per-renter emails and admin summary, (3) unauthenticated CTA views with signed tokens. The command drives the flow; the views are stateless handlers for renter responses.

**Tech Stack:** Django management commands, `django.core.signing.TimestampSigner`, `django.core.mail.send_mail`, Wagtail `SiteSettings`, Bootstrap + site template.

## Global Constraints

- GPG-sign all commits: `git commit -S`
- No emoji anywhere in commits or PR bodies
- No `Co-Authored-By:` lines in commits
- Target branch: `development`
- Commit prefix: `feat:` for new features, `fix:` for corrections
- Edit files under `blowcomotion/static/` never `static/`
- Run `python manage.py test` before each commit; all tests must pass
- `FORM_TEST_EMAIL` copy on all admin emails: `send_mail(..., [settings.FORM_TEST_EMAIL])` after main send, guarded by `hasattr(settings, 'FORM_TEST_EMAIL')`
- Patreon check is a stub — reads `LibraryInstrument.patreon_active` field only; no API calls; mark with `# ponytail: stub — real validation in issue #246`
- Site base URL for emails: `Site.objects.filter(is_default_site=True).first().root_url`

---

## Task 1: DB fields, audit model, and migration

**Files:**
- Modify: `blowcomotion/models.py`
- Create: `blowcomotion/migrations/0114_nag_fields_and_log.py`
- Modify: `blowcomotion/tests/test_nag_instrument_renters_command.py` (create this file — tests live here for all three tasks)

**Interfaces:**
- Produces:
  - `SiteSettings.nag_cooldown_days` — `IntegerField(default=7)`
  - `LibraryInstrument.last_nag_sent` — `DateField(null=True, blank=True)`
  - `LibraryInstrument.save()` — clears `last_nag_sent` when status changes away from `STATUS_RENTED`
  - `InstrumentRentalNagLog` model with fields: `library_instrument` (FK), `member_name`, `member_email`, `reasons`, `sent_at`

- [ ] **Step 1: Add `nag_cooldown_days` to `SiteSettings` in `models.py`**

In `blowcomotion/models.py`, update `attendance_cleanup_days` help text (line ~154) to mention the nag system:

```python
    attendance_cleanup_days = models.IntegerField(
        default=90,
        help_text=(
            "Number of days since last seeing a member before they are marked inactive "
            "(attendance cleanup) and before instrument renters receive a nag email."
        ),
    )
```

Then after that field, add:

```python
    nag_cooldown_days = models.IntegerField(
        default=7,
        help_text="Days to wait before sending another nag email to the same renter.",
    )
```

In the `panels` list, inside the `"Attendance Cleanup Notifications"` `MultiFieldPanel` (line ~213), add after `FieldPanel('attendance_cleanup_days')`:

```python
            FieldPanel('nag_cooldown_days'),
```

- [ ] **Step 2: Add `last_nag_sent` to `LibraryInstrument` in `models.py`**

In `LibraryInstrument`, after the `patreon_amount` field (around line 1508):

```python
    last_nag_sent = models.DateField(
        null=True,
        blank=True,
        help_text="Date the most recent nag email was sent to this renter.",
    )
```

- [ ] **Step 3: Clear `last_nag_sent` in `LibraryInstrument.save()` on return**

In `LibraryInstrument.save()`, inside the `if old_status and old_status != self.status:` block (line ~1611), add **before** the `self._create_status_change_log(...)` call:

```python
        if old_status and old_status != self.status:
            if old_status == self.STATUS_RENTED and self.status != self.STATUS_RENTED:
                self.last_nag_sent = None
                # Use update to avoid recursion; save() already called above via super()
                LibraryInstrument.objects.filter(pk=self.pk).update(last_nag_sent=None)
            self._create_status_change_log(old_status, self.status)
```

- [ ] **Step 4: Add `InstrumentRentalNagLog` model to `models.py`**

Add after the `LibraryInstrumentPhoto` class (around line 1676):

```python
class InstrumentRentalNagLog(models.Model):
    library_instrument = models.ForeignKey(
        "blowcomotion.LibraryInstrument",
        on_delete=models.CASCADE,
        related_name="nag_logs",
    )
    member_name = models.CharField(max_length=255)
    member_email = models.EmailField()
    reasons = models.CharField(
        max_length=255,
        help_text='Comma-separated trigger reasons: "attendance", "patreon", or "attendance+patreon"',
    )
    sent_at = models.DateField()

    class Meta:
        ordering = ["-sent_at"]

    def __str__(self):
        return f"{self.member_name} — {self.sent_at} ({self.reasons})"
```

- [ ] **Step 5: Write tests for the new model fields**

Create `blowcomotion/tests/test_nag_instrument_renters_command.py`:

```python
import datetime
from io import StringIO

from wagtail.models import Site

from django.test import TestCase

from blowcomotion.models import (
    Instrument,
    InstrumentRentalNagLog,
    LibraryInstrument,
    Member,
    Section,
    SiteSettings,
)


def make_member(first_name="Jane", last_name="Doe", email="jane@example.com", last_seen=None, is_active=True):
    section = Section.objects.get_or_create(name="Test Section")[0]
    instrument = Instrument.objects.get_or_create(name="Test Instrument", section=section)[0]
    return Member.objects.create(
        first_name=first_name,
        last_name=last_name,
        email=email,
        primary_instrument=instrument,
        last_seen=last_seen,
        is_active=is_active,
    )


def make_library_instrument(member, patreon_active=True, last_nag_sent=None):
    section = Section.objects.get_or_create(name="Test Section")[0]
    instrument = Instrument.objects.get_or_create(name="Test Instrument", section=section)[0]
    return LibraryInstrument.objects.create(
        instrument=instrument,
        serial_number="SN001",
        status=LibraryInstrument.STATUS_RENTED,
        member=member,
        patreon_active=patreon_active,
        last_nag_sent=last_nag_sent,
    )


class NagFieldsTest(TestCase):
    def setUp(self):
        self.site = Site.objects.get(is_default_site=True)
        self.settings = SiteSettings.for_site(self.site)

    def test_nag_cooldown_days_default(self):
        self.assertEqual(self.settings.nag_cooldown_days, 7)

    def test_last_nag_sent_defaults_null(self):
        member = make_member()
        li = make_library_instrument(member)
        self.assertIsNone(li.last_nag_sent)

    def test_last_nag_sent_clears_on_return(self):
        member = make_member()
        li = make_library_instrument(member, last_nag_sent=datetime.date.today())
        li.status = LibraryInstrument.STATUS_AVAILABLE
        li.save()
        li.refresh_from_db()
        self.assertIsNone(li.last_nag_sent)

    def test_last_nag_sent_not_cleared_when_stays_rented(self):
        member = make_member()
        today = datetime.date.today()
        li = make_library_instrument(member, last_nag_sent=today)
        li.serial_number = "SN002"  # change something else
        li.save()
        li.refresh_from_db()
        self.assertEqual(li.last_nag_sent, today)

    def test_nag_log_creation(self):
        member = make_member()
        li = make_library_instrument(member)
        log = InstrumentRentalNagLog.objects.create(
            library_instrument=li,
            member_name=member.full_name,
            member_email=member.email,
            reasons="attendance",
            sent_at=datetime.date.today(),
        )
        self.assertEqual(InstrumentRentalNagLog.objects.count(), 1)
        self.assertEqual(str(log), f"{member.full_name} — {datetime.date.today()} (attendance)")
```

- [ ] **Step 6: Run tests**

```bash
python manage.py test blowcomotion.tests.test_nag_instrument_renters_command
```

Expected: FAIL — `InstrumentRentalNagLog` does not exist yet (expected — models not migrated).

- [ ] **Step 7: Generate migration**

```bash
python manage.py makemigrations blowcomotion --name nag_fields_and_log
```

Expected output: `blowcomotion/migrations/0114_nag_fields_and_log.py`

- [ ] **Step 8: Apply migration**

```bash
python manage.py migrate
```

Expected: OK

- [ ] **Step 9: Run tests again**

```bash
python manage.py test blowcomotion.tests.test_nag_instrument_renters_command
```

Expected: All pass.

- [ ] **Step 10: Commit**

```bash
git add blowcomotion/models.py blowcomotion/migrations/0114_nag_fields_and_log.py blowcomotion/tests/test_nag_instrument_renters_command.py
git commit -S -m "feat: add nag_cooldown_days, last_nag_sent, and InstrumentRentalNagLog for rental nag emails"
```

---

## Task 2: Management command `nag_instrument_renters`

**Files:**
- Create: `blowcomotion/management/commands/nag_instrument_renters.py`
- Modify: `blowcomotion/tests/test_nag_instrument_renters_command.py` (add command tests)

**Interfaces:**
- Consumes: `SiteSettings.nag_cooldown_days`, `SiteSettings.attendance_cleanup_days`, `SiteSettings.instrument_rental_notification_recipients`, `LibraryInstrument.last_nag_sent`, `LibraryInstrument.patreon_active`, `Member.last_seen`, `Member.is_active`, `Member.email`, `Member.first_name`, `InstrumentRentalNagLog`
- Produces: `nag_instrument_renters` management command callable via `call_command('nag_instrument_renters')`

- [ ] **Step 1: Write the failing command tests**

Append to `blowcomotion/tests/test_nag_instrument_renters_command.py`:

```python
from django.core.management import call_command
from django.test import override_settings

TODAY_WEEKDAY = datetime.date.today().weekday()


@override_settings(
    FROM_EMAIL="test@blowcomotion.org",
    FORM_TEST_EMAIL="copy@blowcomotion.org",
)
class NagInstrumentRentersCommandTest(TestCase):
    def setUp(self):
        self.site = Site.objects.get(is_default_site=True)
        self.settings = SiteSettings.for_site(self.site)
        self.settings.instrument_rental_notification_recipients = "admin@blowcomotion.org"
        self.settings.attendance_cleanup_days = 90
        self.settings.nag_cooldown_days = 7
        self.settings.save()

        self.old_member = make_member(
            first_name="Old",
            email="old@example.com",
            last_seen=datetime.date.today() - datetime.timedelta(days=100),
        )
        self.recent_member = make_member(
            first_name="Recent",
            last_name="Smith",
            email="recent@example.com",
            last_seen=datetime.date.today() - datetime.timedelta(days=10),
        )
        self.old_li = make_library_instrument(self.old_member, patreon_active=True)
        self.recent_li = make_library_instrument(self.recent_member, patreon_active=True)

    def test_wrong_day_skips(self):
        wrong_day = (TODAY_WEEKDAY + 1) % 7
        out = StringIO()
        call_command("nag_instrument_renters", f"--day-to-run={wrong_day}", stdout=out)
        self.assertEqual(InstrumentRentalNagLog.objects.count(), 0)

    def test_attendance_inactive_triggers_nag(self):
        out = StringIO()
        call_command(
            "nag_instrument_renters",
            f"--day-to-run={TODAY_WEEKDAY}",
            stdout=out,
        )
        self.old_li.refresh_from_db()
        self.assertEqual(self.old_li.last_nag_sent, datetime.date.today())
        self.assertEqual(InstrumentRentalNagLog.objects.filter(library_instrument=self.old_li).count(), 1)
        log = InstrumentRentalNagLog.objects.get(library_instrument=self.old_li)
        self.assertIn("attendance", log.reasons)

    def test_recent_member_not_nagged(self):
        out = StringIO()
        call_command(
            "nag_instrument_renters",
            f"--day-to-run={TODAY_WEEKDAY}",
            stdout=out,
        )
        self.recent_li.refresh_from_db()
        self.assertIsNone(self.recent_li.last_nag_sent)
        self.assertEqual(InstrumentRentalNagLog.objects.filter(library_instrument=self.recent_li).count(), 0)

    def test_patreon_inactive_triggers_nag(self):
        self.recent_li.patreon_active = False
        self.recent_li.save()
        out = StringIO()
        call_command(
            "nag_instrument_renters",
            f"--day-to-run={TODAY_WEEKDAY}",
            stdout=out,
        )
        self.recent_li.refresh_from_db()
        self.assertEqual(self.recent_li.last_nag_sent, datetime.date.today())
        log = InstrumentRentalNagLog.objects.get(library_instrument=self.recent_li)
        self.assertIn("patreon", log.reasons)

    def test_cooldown_skips_recently_nagged(self):
        self.old_li.last_nag_sent = datetime.date.today() - datetime.timedelta(days=3)
        self.old_li.save()
        out = StringIO()
        call_command(
            "nag_instrument_renters",
            f"--day-to-run={TODAY_WEEKDAY}",
            stdout=out,
        )
        self.old_li.refresh_from_db()
        # last_nag_sent unchanged (still 3 days ago, not today)
        self.assertNotEqual(self.old_li.last_nag_sent, datetime.date.today())
        self.assertEqual(InstrumentRentalNagLog.objects.count(), 0)

    def test_dry_run_does_not_write_db(self):
        out = StringIO()
        call_command(
            "nag_instrument_renters",
            f"--day-to-run={TODAY_WEEKDAY}",
            "--dry-run",
            stdout=out,
        )
        self.old_li.refresh_from_db()
        self.assertIsNone(self.old_li.last_nag_sent)
        self.assertEqual(InstrumentRentalNagLog.objects.count(), 0)

    def test_member_without_email_skipped(self):
        no_email_member = make_member(first_name="NoEmail", last_name="X", email="", last_seen=datetime.date.today() - datetime.timedelta(days=100))
        no_email_member.email = None
        no_email_member.save()
        make_library_instrument(no_email_member)
        out = StringIO()
        call_command("nag_instrument_renters", f"--day-to-run={TODAY_WEEKDAY}", stdout=out)
        # Only old_li should be nagged, not no_email instrument
        self.assertEqual(InstrumentRentalNagLog.objects.count(), 1)
```

- [ ] **Step 2: Run tests to see them fail**

```bash
python manage.py test blowcomotion.tests.test_nag_instrument_renters_command.NagInstrumentRentersCommandTest
```

Expected: `CommandError` or `ModuleNotFoundError` — command doesn't exist yet.

- [ ] **Step 3: Create the management command**

Create `blowcomotion/management/commands/nag_instrument_renters.py`:

```python
import datetime
import re

from wagtail.models import Site

from django.conf import settings
from django.core.mail import send_mail
from django.core.management.base import BaseCommand
from django.core.signing import BadSignature, TimestampSigner

from blowcomotion.models import InstrumentRentalNagLog, LibraryInstrument, SiteSettings


class Command(BaseCommand):
    help = "Send nag emails to instrument renters who are attendance-inactive or patreon-inactive"

    def add_arguments(self, parser):
        parser.add_argument("--dry-run", action="store_true", help="Print actions without sending emails or writing to DB")
        parser.add_argument(
            "--day-to-run",
            type=int,
            choices=range(7),
            help="Day of week to run (0=Monday, 6=Sunday)",
        )

    def handle(self, *args, **options):
        today = datetime.date.today()
        day_to_run = options["day_to_run"]
        if day_to_run is not None and today.weekday() != day_to_run:
            days = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
            self.stdout.write(self.style.WARNING(f"Intended to run on {days[day_to_run]} only. Exiting."))
            return

        dry_run = options["dry_run"]
        site_settings = self._get_site_settings()
        if not site_settings:
            return

        admin_recipients = self._parse_recipients(site_settings.instrument_rental_notification_recipients)
        if not admin_recipients and not dry_run:
            self.stdout.write(self.style.ERROR("No instrument_rental_notification_recipients configured. Exiting."))
            return

        site = Site.objects.filter(is_default_site=True).first() or Site.objects.first()
        base_url = site.root_url if site else "https://blowcomotion.org"

        cutoff = today - datetime.timedelta(days=site_settings.attendance_cleanup_days)
        cooldown_days = site_settings.nag_cooldown_days

        instruments = LibraryInstrument.objects.filter(
            status=LibraryInstrument.STATUS_RENTED,
            member__isnull=False,
            member__email__isnull=False,
        ).exclude(member__email="").select_related("member", "instrument")

        nagged = []
        skipped_cooldown = 0

        for li in instruments:
            if li.last_nag_sent and (today - li.last_nag_sent).days < cooldown_days:
                skipped_cooldown += 1
                continue

            member = li.member
            reasons = []

            if not member.is_active or not member.last_seen or member.last_seen < cutoff:
                reasons.append("attendance")

            # ponytail: stub — real validation in issue #246; reads field set manually or by future API sync
            if not li.patreon_active:
                reasons.append("patreon")

            if not reasons:
                continue

            reason_str = "+".join(reasons)
            self._send_renter_nag(li, member, base_url, reasons, dry_run)

            if not dry_run:
                LibraryInstrument.objects.filter(pk=li.pk).update(last_nag_sent=today)
                InstrumentRentalNagLog.objects.create(
                    library_instrument=li,
                    member_name=member.full_name,
                    member_email=member.email,
                    reasons=reason_str,
                    sent_at=today,
                )

            nagged.append({"instrument": li, "member": member, "reasons": reasons})
            self.stdout.write(self.style.SUCCESS(f"Nagged {member.full_name} ({li.instrument.name}) — {reason_str}"))

        if nagged:
            self._send_admin_summary(nagged, skipped_cooldown, admin_recipients, today, dry_run)
        else:
            self.stdout.write(self.style.SUCCESS(f"Nothing to nag today ({skipped_cooldown} skipped by cooldown)."))

    def _send_renter_nag(self, li, member, base_url, reasons, dry_run):
        signer = TimestampSigner()
        token = signer.sign(str(li.pk))
        first_name = member.first_name or member.full_name

        lines = [
            f"Hi {first_name},",
            "",
            f"We wanted to check in about the {li.instrument.name} you're renting from Blowcomotion.",
            "",
        ]
        if "attendance" in reasons:
            last_seen_str = str(member.last_seen) if member.last_seen else "unknown"
            lines += [
                f"We haven't seen you at rehearsal in a while (last seen: {last_seen_str}). We'd love to have you back!",
                "",
            ]
        if "patreon" in reasons:
            lines += [
                "Our records show your Patreon membership may not be current. Keeping it active helps us maintain the instrument library.",
                "",
            ]
        lines += [
            "Please let us know your plans:",
            "",
            "I'll be back at rehearsal soon:",
            f"{base_url}/instrument-rental/staying/?t={token}",
            "",
            "I'd like to return the instrument:",
            f"{base_url}/instrument-rental/return/?t={token}",
            "",
            "Start Wearing Purple,",
            "Blowcomotion",
        ]
        message = "\n".join(lines)
        subject = "A note from Blowcomotion about your instrument rental"

        if dry_run:
            self.stdout.write(self.style.NOTICE(f"[Dry Run] Would email {member.email}:\nSubject: {subject}\n{message}\n"))
        else:
            send_mail(subject, message, settings.FROM_EMAIL, [member.email], fail_silently=False)

    def _send_admin_summary(self, nagged, skipped_cooldown, recipients, today, dry_run):
        lines = [
            f"Instrument Rental Nag Summary — {today}",
            "=" * 50,
            "",
            f"Nag emails sent to {len(nagged)} renter(s):",
            "",
        ]
        for item in nagged:
            member = item["member"]
            reason_label = " + ".join(item["reasons"])
            last_seen_note = f", last seen {member.last_seen}" if member.last_seen and "attendance" in item["reasons"] else ""
            lines.append(f"  * {member.full_name} — {item['instrument'].instrument.name} (Reason: {reason_label}{last_seen_note})")
        lines += ["", f"Skipped (cooldown active): {skipped_cooldown} renter(s)"]
        message = "\n".join(lines)
        subject = f"Instrument Rental Nag Summary — {today}"

        if dry_run:
            self.stdout.write(self.style.NOTICE(f"[Dry Run] Admin summary:\nSubject: {subject}\n{message}"))
            return

        if recipients:
            send_mail(subject, message, settings.FROM_EMAIL, recipients, fail_silently=False)
            extra = getattr(settings, "FORM_TEST_EMAIL", None)
            if extra:
                send_mail(f"[COPY] {subject}", message, settings.FROM_EMAIL, [extra], fail_silently=False)

    def _get_site_settings(self):
        try:
            site = (
                Site.objects.filter(is_default_site=True).select_related("root_page").first()
                or Site.objects.select_related("root_page").first()
            )
            if not site:
                self.stdout.write(self.style.ERROR("No Site configured. Cannot load SiteSettings."))
                return None
            return SiteSettings.for_site(site)
        except Exception as exc:
            self.stdout.write(self.style.ERROR(f"Error retrieving SiteSettings: {exc}"))
            return None

    def _parse_recipients(self, raw):
        if not raw:
            return []
        return [r.strip() for r in re.split(r"[,\n]", raw) if r.strip()]
```

- [ ] **Step 4: Run tests**

```bash
python manage.py test blowcomotion.tests.test_nag_instrument_renters_command.NagInstrumentRentersCommandTest
```

Expected: All pass.

- [ ] **Step 5: Run full test suite**

```bash
python manage.py test
```

Expected: All pass.

- [ ] **Step 6: Commit**

```bash
git add blowcomotion/management/commands/nag_instrument_renters.py blowcomotion/tests/test_nag_instrument_renters_command.py
git commit -S -m "feat: add nag_instrument_renters management command"
```

---

## Task 3: CTA views, URLs, and templates

**Files:**
- Modify: `blowcomotion/views.py`
- Modify: `blowcomotion/urls.py`
- Create: `blowcomotion/templates/instrument_rental_staying.html`
- Create: `blowcomotion/templates/instrument_rental_return.html`
- Create: `blowcomotion/templates/instrument_rental_token_error.html`
- Create: `blowcomotion/tests/test_instrument_rental_cta_views.py`

**Interfaces:**
- Consumes: `TimestampSigner` (same signer used in command — `django.core.signing.TimestampSigner`), `LibraryInstrument`, `SiteSettings`, `send_mail`
- Produces:
  - `GET /instrument-rental/staying/?t=<token>` → `instrument_rental_staying` view
  - `GET /instrument-rental/return/?t=<token>` → `instrument_rental_return` view

Token format: `TimestampSigner().sign(str(instrument_pk))` — max_age 30 days on unsign.

- [ ] **Step 1: Write failing view tests**

Create `blowcomotion/tests/test_instrument_rental_cta_views.py`:

```python
import datetime

from wagtail.models import Site

from django.core.signing import TimestampSigner
from django.test import TestCase, override_settings

from blowcomotion.models import Instrument, LibraryInstrument, Member, Section, SiteSettings


def make_renter():
    section = Section.objects.get_or_create(name="Test Section")[0]
    instrument = Instrument.objects.get_or_create(name="Trombone", section=section)[0]
    member = Member.objects.create(
        first_name="Jane",
        last_name="Doe",
        email="jane@example.com",
        primary_instrument=instrument,
        last_seen=datetime.date.today() - datetime.timedelta(days=5),
    )
    li = LibraryInstrument.objects.create(
        instrument=instrument,
        serial_number="SN999",
        status=LibraryInstrument.STATUS_RENTED,
        member=member,
        patreon_active=True,
    )
    return li


@override_settings(FROM_EMAIL="test@blowcomotion.org")
class InstrumentRentalCTAViewsTest(TestCase):
    def setUp(self):
        self.site = Site.objects.get(is_default_site=True)
        self.settings = SiteSettings.for_site(self.site)
        self.settings.instrument_rental_notification_recipients = "admin@blowcomotion.org"
        self.settings.save()
        self.li = make_renter()
        self.signer = TimestampSigner()

    def _token(self):
        return self.signer.sign(str(self.li.pk))

    def test_staying_valid_token_returns_200(self):
        response = self.client.get(f"/instrument-rental/staying/?t={self._token()}")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "see you soon")

    def test_return_valid_token_returns_200(self):
        response = self.client.get(f"/instrument-rental/return/?t={self._token()}")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "in touch")

    def test_staying_bad_token_returns_400(self):
        response = self.client.get("/instrument-rental/staying/?t=bad-token")
        self.assertEqual(response.status_code, 400)

    def test_return_bad_token_returns_400(self):
        response = self.client.get("/instrument-rental/return/?t=bad-token")
        self.assertEqual(response.status_code, 400)

    def test_staying_missing_token_returns_400(self):
        response = self.client.get("/instrument-rental/staying/")
        self.assertEqual(response.status_code, 400)

    def test_return_missing_token_returns_400(self):
        response = self.client.get("/instrument-rental/return/")
        self.assertEqual(response.status_code, 400)

    def test_staying_sends_admin_email(self):
        from django.core import mail
        self.client.get(f"/instrument-rental/staying/?t={self._token()}")
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn("Returning to Rehearsal", mail.outbox[0].subject)
        self.assertIn("admin@blowcomotion.org", mail.outbox[0].to)

    def test_return_sends_admin_email(self):
        from django.core import mail
        self.client.get(f"/instrument-rental/return/?t={self._token()}")
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn("Return", mail.outbox[0].subject)
        self.assertIn("admin@blowcomotion.org", mail.outbox[0].to)
```

- [ ] **Step 2: Run tests to see them fail**

```bash
python manage.py test blowcomotion.tests.test_instrument_rental_cta_views
```

Expected: FAIL — URLs don't exist yet (404s).

- [ ] **Step 3: Add views to `views.py`**

At the end of `blowcomotion/views.py`, add:

```python
def _get_site_settings_for_view():
    from wagtail.models import Site
    site = Site.objects.filter(is_default_site=True).first() or Site.objects.first()
    if not site:
        return None
    return SiteSettings.for_site(site)


def instrument_rental_staying(request):
    from django.core.signing import BadSignature, TimestampSigner
    token = request.GET.get("t", "")
    try:
        signer = TimestampSigner()
        instrument_pk = signer.unsign(token, max_age=30 * 24 * 3600)
        li = LibraryInstrument.objects.select_related("member", "instrument").get(pk=instrument_pk)
    except Exception:
        return render(request, "instrument_rental_token_error.html", status=400)

    site_settings = _get_site_settings_for_view()
    if site_settings and li.member:
        raw = site_settings.instrument_rental_notification_recipients or ""
        recipients = [r.strip() for r in raw.replace("\n", ",").split(",") if r.strip()]
        if recipients:
            send_mail(
                subject=f"Instrument Renter Confirmed: Returning to Rehearsal — {li.member.full_name}",
                message=(
                    f"Renter {li.member.full_name} confirmed they are returning to rehearsal soon.\n\n"
                    f"Instrument: {li.instrument.name}\n"
                    f"Serial: {li.serial_number}\n"
                    f"Member email: {li.member.email}"
                ),
                from_email=settings.FROM_EMAIL,
                recipient_list=recipients,
                fail_silently=True,
            )

    return render(request, "instrument_rental_staying.html", {"instrument": li})


def instrument_rental_return(request):
    from django.core.signing import BadSignature, TimestampSigner
    token = request.GET.get("t", "")
    try:
        signer = TimestampSigner()
        instrument_pk = signer.unsign(token, max_age=30 * 24 * 3600)
        li = LibraryInstrument.objects.select_related("member", "instrument").get(pk=instrument_pk)
    except Exception:
        return render(request, "instrument_rental_token_error.html", status=400)

    site_settings = _get_site_settings_for_view()
    if site_settings and li.member:
        raw = site_settings.instrument_rental_notification_recipients or ""
        recipients = [r.strip() for r in raw.replace("\n", ",").split(",") if r.strip()]
        if recipients:
            send_mail(
                subject=f"Instrument Return Request — {li.member.full_name}",
                message=(
                    f"Renter {li.member.full_name} would like to return their instrument — please follow up.\n\n"
                    f"Instrument: {li.instrument.name}\n"
                    f"Serial: {li.serial_number}\n"
                    f"Member email: {li.member.email}\n"
                    f"Member phone: {li.member.phone or 'N/A'}"
                ),
                from_email=settings.FROM_EMAIL,
                recipient_list=recipients,
                fail_silently=True,
            )

    return render(request, "instrument_rental_return.html", {"instrument": li})
```

`re` is already imported in `views.py`. `LibraryInstrument` and `SiteSettings` are already imported in `views.py`. `send_mail` and `settings` are already imported.

- [ ] **Step 4: Wire URLs in `urls.py`**

In `blowcomotion/urls.py`, before the `path("member/", ...)` line, add:

```python
    path("instrument-rental/staying/", blowcomotion_views.instrument_rental_staying, name="instrument-rental-staying"),
    path("instrument-rental/return/", blowcomotion_views.instrument_rental_return, name="instrument-rental-return"),
```

- [ ] **Step 5: Create template `instrument_rental_staying.html`**

Create `blowcomotion/templates/instrument_rental_staying.html`:

```html
{% extends "base.html" %}
{% load static %}

{% block title %}Thanks — Blowcomotion{% endblock %}

{% block content %}
<div class="container py-5">
    <div class="row justify-content-center">
        <div class="col-lg-8 text-center">
            <div class="card shadow-sm">
                <div class="card-body p-5">
                    <h1 class="mb-4">See you soon!</h1>
                    <p class="lead mb-4">
                        Thanks for letting us know you'll be back at rehearsal.
                        We look forward to seeing you there!
                    </p>
                    {% if instrument.member %}
                    <p class="text-muted">
                        If you have any questions about your rental of the
                        <strong>{{ instrument.instrument.name }}</strong>,
                        please reach out to the instrument library team.
                    </p>
                    {% endif %}
                    <div class="mt-4">
                        <a href="/" class="site-btn btn-lg px-5">Return Home</a>
                    </div>
                </div>
            </div>
        </div>
    </div>
</div>
{% endblock %}
```

- [ ] **Step 6: Create template `instrument_rental_return.html`**

Create `blowcomotion/templates/instrument_rental_return.html`:

```html
{% extends "base.html" %}
{% load static %}

{% block title %}We'll Be in Touch — Blowcomotion{% endblock %}

{% block content %}
<div class="container py-5">
    <div class="row justify-content-center">
        <div class="col-lg-8 text-center">
            <div class="card shadow-sm">
                <div class="card-body p-5">
                    <h1 class="mb-4">We'll be in touch!</h1>
                    <p class="lead mb-4">
                        We've let the instrument library team know you'd like to return
                        the <strong>{{ instrument.instrument.name }}</strong>.
                        Someone will reach out to arrange the return.
                    </p>
                    <p class="text-muted">
                        Thank you for being part of Blowcomotion!
                    </p>
                    <div class="mt-4">
                        <a href="/" class="site-btn btn-lg px-5">Return Home</a>
                    </div>
                </div>
            </div>
        </div>
    </div>
</div>
{% endblock %}
```

- [ ] **Step 7: Create template `instrument_rental_token_error.html`**

Create `blowcomotion/templates/instrument_rental_token_error.html`:

```html
{% extends "base.html" %}

{% block title %}Link Expired — Blowcomotion{% endblock %}

{% block content %}
<div class="container py-5">
    <div class="row justify-content-center">
        <div class="col-lg-8 text-center">
            <div class="card shadow-sm">
                <div class="card-body p-5">
                    <h1 class="mb-4">This link has expired</h1>
                    <p class="lead mb-4">
                        This link is no longer valid. Rental notification links expire after 30 days.
                    </p>
                    <p class="text-muted">
                        If you need to get in touch with us about your instrument rental,
                        please contact the instrument library team directly.
                    </p>
                    <div class="mt-4">
                        <a href="/" class="site-btn btn-lg px-5">Return Home</a>
                    </div>
                </div>
            </div>
        </div>
    </div>
</div>
{% endblock %}
```

- [ ] **Step 8: Run view tests**

```bash
python manage.py test blowcomotion.tests.test_instrument_rental_cta_views
```

Expected: All pass.

- [ ] **Step 9: Run full test suite**

```bash
python manage.py test
```

Expected: All pass.

- [ ] **Step 10: Commit**

```bash
git add blowcomotion/views.py blowcomotion/urls.py \
    blowcomotion/templates/instrument_rental_staying.html \
    blowcomotion/templates/instrument_rental_return.html \
    blowcomotion/templates/instrument_rental_token_error.html \
    blowcomotion/tests/test_instrument_rental_cta_views.py
git commit -S -m "feat: add instrument rental CTA views and confirmation templates"
```

---

## Task 4: Update issue #246 with stub details

**Files:** None (GitHub only)

- [ ] **Step 1: Post comment on issue #246**

```bash
gh issue comment 246 --repo Blowcomotion/blowcomotion.org --body "$(cat <<'EOF'
## Stub implemented in #158

The nag_instrument_renters management command (merged in #158) includes a patreon check that is currently stubbed. Here is what the stub does and what the real implementation must replace.

### What the stub does

Reads `LibraryInstrument.patreon_active` (a manually-set BooleanField) and treats `False` as "patreon inactive." No API calls are made. The field must be set manually in the Wagtail admin or via migration until #246 is implemented.

Marked in code with:
```
# ponytail: stub — real validation in issue #246; reads field set manually or by future API sync
```

### What #246 must implement to replace the stub

Before (or as part of) `nag_instrument_renters` running each day, the Patreon API v2 must:

1. Look up the renter's email against Patreon members in the campaign
2. Check for an active pledge at or above the required tier
3. Update `LibraryInstrument.patreon_active` (and optionally `patreon_amount`) on the instrument record

Once `patreon_active` is kept current by #246, the nag command stub becomes real validation automatically — no changes to `nag_instrument_renters` needed.

### Prerequisites (unchanged from original issue)

- Patreon Creator Access Token in `local.py` as `PATREON_ACCESS_TOKEN`
- Campaign ID in `local.py` as `PATREON_CAMPAIGN_ID`
EOF
)"
```

- [ ] **Step 2: Verify comment posted**

```bash
gh issue view 246 --repo Blowcomotion/blowcomotion.org --comments | tail -20
```

Expected: Comment text visible.

---

## Task 5: Branch checkout and PR

- [ ] **Step 1: Ensure branch is up to date**

```bash
git log --oneline development..HEAD
```

Expected: 3 commits (models/migration, command, views).

- [ ] **Step 2: Push branch**

```bash
git push -u origin HEAD
```

- [ ] **Step 3: Open PR**

```bash
gh pr create \
  --base development \
  --title "feat: email nag for overdue instrument rentals (#158)" \
  --body "$(cat <<'EOF'
Closes #158

## Summary

- Adds `nag_instrument_renters` management command that emails renters who haven't been seen at rehearsal (per `SiteSettings.attendance_cleanup_days`) or whose `patreon_active` is false (stub pending #246)
- Per-renter plain-text email includes two CTA links (staying / returning) that trigger admin notification emails when clicked
- Links are signed with `TimestampSigner` and expire after 30 days
- Admin summary email sent to `instrument_rental_notification_recipients` after each run, with `FORM_TEST_EMAIL` copy
- `InstrumentRentalNagLog` records every nag sent (instrument, member, reasons, date)
- `SiteSettings.nag_cooldown_days` (default 7) prevents re-nagging within the cooldown window
- `LibraryInstrument.last_nag_sent` cleared automatically when instrument is returned
- `--dry-run` flag prints all actions without sending email or writing to DB
- Updated issue #246 with stub details and upgrade path

## Test plan

- [ ] Run `python manage.py nag_instrument_renters --dry-run` and verify output lists inactive renters without writing to DB
- [ ] Confirm a renter with `last_seen` older than `attendance_cleanup_days` appears in output
- [ ] Set a `LibraryInstrument.patreon_active = False` and confirm that renter appears in output
- [ ] Click the "staying" CTA link from a test email and confirm admin notification email arrives
- [ ] Click the "return" CTA link from a test email and confirm admin notification email arrives
- [ ] Paste a malformed token into the CTA URL and confirm the error page loads (HTTP 400)
- [ ] Run full test suite: `python manage.py test`
EOF
)"
```
