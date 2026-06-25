from django.db.models import Count, Q
from django.test import TestCase

from blowcomotion.member_forms import InstrumentRentalRequestForm
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
