from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
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


class AuctionSummaryTests(TestCase):
    def setUp(self):
        self.auction = make_auction(name="Fall Fundraiser")
        self.item1 = make_item(self.auction, title="Yeti Cooler")
        self.item2 = make_item(self.auction, title="Gift Card")
        self.alice = make_bidder(self.auction, name="Alice Smith", email="alice@example.com")
        self.bob = make_bidder(self.auction, name="Bob Jones", email="bob@example.com", phone="512-555-9999")

        self.winning_bid = Bid.objects.create(item=self.item1, bidder=self.alice, amount=Decimal("100"))
        self.backup_bid = Bid.objects.create(item=self.item1, bidder=self.bob, amount=Decimal("90"))
        self.item1.winning_bid = self.winning_bid
        self.item1.backup_bid = self.backup_bid
        self.item1.save()
        # item2 has no bids at all.

        self.auctioneer_group = Group.objects.create(name="Auctioneer")
        self.auctioneer = get_user_model().objects.create_user(
            username="auctioneer", email="auctioneer@example.com", password="password"
        )
        self.auctioneer.groups.add(self.auctioneer_group)

    def test_summary_sent_to_auctioneer_group_with_formatted_body(self):
        notifications.send_auction_summary(self.auction)

        self.assertEqual(len(mail.outbox), 1)
        message = mail.outbox[0]
        self.assertIn("auctioneer@example.com", message.to)
        self.assertEqual(message.subject, "Auction results: Fall Fundraiser")

        self.assertIn("Fall Fundraiser — final results", message.body)
        self.assertIn(
            f"#{self.item1.number} Yeti Cooler: $100.00 — Alice Smith (alice@example.com, +15125551234)"
            " [backup: Bob Jones $90.00]",
            message.body,
        )
        self.assertIn(f"#{self.item2.number} Gift Card: no bids", message.body)
        self.assertIn("Total raised: $100.00", message.body)

    def test_no_email_when_auctioneer_group_missing(self):
        self.auctioneer_group.delete()
        notifications.send_auction_summary(self.auction)  # must not raise
        self.assertEqual(len(mail.outbox), 0)

    def test_no_email_when_auctioneer_group_has_no_users_with_email(self):
        self.auctioneer.email = ""
        self.auctioneer.save()
        notifications.send_auction_summary(self.auction)  # must not raise
        self.assertEqual(len(mail.outbox), 0)
