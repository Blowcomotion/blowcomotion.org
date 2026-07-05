from decimal import Decimal
from unittest.mock import patch

from django.core import mail
from django.test import TestCase, override_settings

from auction import notifications
from auction.models import Bid
from auction.tests.test_models import make_auction, make_bidder, make_item


class NotificationTests(TestCase):
    def setUp(self):
        self.auction = make_auction(payment_instructions="Pay at the merch table.")
        self.item = make_item(self.auction)
        self.alice = make_bidder(self.auction, sms_opt_in=True)
        self.bob = make_bidder(self.auction, name="Bob Jones", email="bob@example.com", phone="512-555-9999")
        self.first = Bid.objects.create(item=self.item, bidder=self.alice, amount=Decimal("25"))
        self.second = Bid.objects.create(item=self.item, bidder=self.bob, amount=Decimal("30"))

    @patch("auction.notifications.send_sms")
    def test_outbid_sends_email_and_sms_when_opted_in(self, mock_sms):
        notifications.notify_outbid(self.first, self.second)
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn("robin@example.com", mail.outbox[0].to)
        self.assertIn("outbid", mail.outbox[0].subject.lower())
        mock_sms.assert_called_once()
        body = mock_sms.call_args.args[1]
        self.assertIn("BID 1 35", body)          # next minimum: 30 + 5
        self.assertIn("/auction/", body)          # item link included

    @patch("auction.notifications.send_sms")
    def test_outbid_no_sms_without_opt_in(self, mock_sms):
        notifications.notify_outbid(self.second, self.first)  # bob has sms_opt_in=False
        mock_sms.assert_not_called()

    @patch("auction.notifications.send_sms")
    def test_winner_notice_includes_payment_instructions(self, mock_sms):
        self.item.winning_bid = self.second
        self.item.save()
        notifications.notify_winner(self.item)
        self.assertIn("merch table", mail.outbox[0].body)

    def test_send_sms_noop_without_settings(self):
        notifications.send_sms("+15125551234", "hello")  # must not raise

    @override_settings(
        TWILIO_ACCOUNT_SID="sid", TWILIO_AUTH_TOKEN="tok", TWILIO_FROM_NUMBER="+15550000000"
    )
    @patch("auction.notifications.Client")
    def test_send_sms_calls_twilio(self, mock_client):
        notifications.send_sms("+15125551234", "hello")
        mock_client.assert_called_once_with("sid", "tok")
        mock_client.return_value.messages.create.assert_called_once_with(
            to="+15125551234", from_="+15550000000", body="hello"
        )
