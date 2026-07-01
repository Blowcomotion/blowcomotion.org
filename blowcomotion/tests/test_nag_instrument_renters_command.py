import datetime
from io import StringIO

from wagtail.models import Site

from django.core.management import call_command
from django.test import TestCase, override_settings

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

    def test_inactive_member_triggers_nag(self):
        self.recent_member.is_active = False
        self.recent_member.save()
        out = StringIO()
        call_command(
            "nag_instrument_renters",
            f"--day-to-run={TODAY_WEEKDAY}",
            stdout=out,
        )
        self.recent_li.refresh_from_db()
        self.assertEqual(self.recent_li.last_nag_sent, datetime.date.today())
        log = InstrumentRentalNagLog.objects.get(library_instrument=self.recent_li)
        self.assertIn("attendance", log.reasons)

    def test_renter_email_is_sent(self):
        from django.core import mail
        call_command(
            "nag_instrument_renters",
            f"--day-to-run={TODAY_WEEKDAY}",
            stdout=StringIO(),
        )
        # old_member is attendance-inactive and should receive a nag
        renter_emails = [m for m in mail.outbox if self.old_member.email in m.to]
        self.assertTrue(renter_emails, "No nag email sent to renter")
        self.assertIn("instrument", renter_emails[0].subject.lower())
