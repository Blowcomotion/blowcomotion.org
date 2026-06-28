import datetime

from wagtail.models import Site

from django.core import mail
from django.core.signing import TimestampSigner
from django.test import TestCase, override_settings

from blowcomotion.models import (
    Instrument,
    LibraryInstrument,
    Member,
    Section,
    SiteSettings,
)


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
        self.client.get(f"/instrument-rental/staying/?t={self._token()}")
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn("Returning to Rehearsal", mail.outbox[0].subject)
        self.assertIn("admin@blowcomotion.org", mail.outbox[0].to)

    def test_return_sends_admin_email(self):
        self.client.get(f"/instrument-rental/return/?t={self._token()}")
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn("Return", mail.outbox[0].subject)
        self.assertIn("admin@blowcomotion.org", mail.outbox[0].to)
