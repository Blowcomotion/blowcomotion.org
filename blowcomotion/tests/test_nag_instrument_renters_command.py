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
