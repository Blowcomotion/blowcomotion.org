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
