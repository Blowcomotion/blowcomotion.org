from decimal import Decimal
from unittest.mock import patch

from django.test import TestCase, override_settings
from django.urls import reverse

from auction.tests.test_models import make_auction, make_bidder, make_item


# Django forces DEBUG=False during tests; the signature-skip-without-token path
# depends on DEBUG, so behavioral tests run with DEBUG=True (mirroring the
# existing pattern in blowcomotion/tests/test_recaptcha.py). The two rejection
# tests below re-override DEBUG=False at method level, which takes precedence.
@override_settings(DEBUG=True)
class SmsWebhookTests(TestCase):
    def setUp(self):
        self.auction = make_auction()
        self.item = make_item(self.auction)  # number 1, starting 25
        self.bidder = make_bidder(self.auction)  # +15125551234
        self.url = reverse("auction-sms-webhook")

    def sms(self, body, from_="+15125551234"):
        return self.client.post(self.url, {"From": from_, "Body": body})

    def test_valid_bid_places_and_confirms(self):
        response = self.sms("BID 1 25")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "top bid")
        bid = self.item.bids.get()
        self.assertEqual((bid.amount, bid.source), (Decimal("25"), "sms"))

    def test_bid_with_symbols_and_case(self):
        response = self.sms("bid #1 $25")
        self.assertEqual(self.item.bids.count(), 1)

    def test_too_low_bid_explains_minimum(self):
        response = self.sms("BID 1 5")
        self.assertContains(response, "at least $25")
        self.assertEqual(self.item.bids.count(), 0)

    def test_unknown_item(self):
        response = self.sms("BID 99 25")
        self.assertContains(response, "No item #99")

    def test_unknown_number_prompts_registration(self):
        response = self.sms("BID 1 25", from_="+15129990000")
        self.assertContains(response, "register")
        self.assertEqual(self.item.bids.count(), 0)

    def test_help_and_garbage_get_usage(self):
        for body in ("HELP", "what is this"):
            response = self.sms(body)
            self.assertContains(response, "BID")

    @override_settings(DEBUG=False, TWILIO_AUTH_TOKEN="secret-token")
    def test_invalid_signature_rejected(self):
        response = self.sms("BID 1 25")  # no/garbage signature header
        self.assertEqual(response.status_code, 403)
        self.assertEqual(self.item.bids.count(), 0)

    @override_settings(DEBUG=False)
    def test_no_token_in_production_rejected(self):
        response = self.sms("BID 1 25")
        self.assertEqual(response.status_code, 403)
