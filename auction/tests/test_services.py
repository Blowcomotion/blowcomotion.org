from datetime import timedelta
from decimal import Decimal
from unittest.mock import patch

from django.test import TestCase
from django.utils import timezone

from auction.models import Bid
from auction.services import BidError, place_bid
from auction.tests.test_models import make_auction, make_bidder, make_item


@patch("auction.notifications.notify_outbid")
class PlaceBidTests(TestCase):
    def setUp(self):
        self.auction = make_auction()
        self.item = make_item(self.auction)  # starting 25, increment 5
        self.alice = make_bidder(self.auction)
        self.bob = make_bidder(self.auction, name="Bob Jones", email="bob@example.com", phone="512-555-9999")

    def test_first_bid_must_meet_starting_bid(self, mock_notify):
        with self.assertRaises(BidError):
            place_bid(self.item.pk, self.alice, Decimal("20"))
        bid = place_bid(self.item.pk, self.alice, Decimal("25"))
        self.assertEqual(bid.amount, Decimal("25"))
        mock_notify.assert_not_called()

    def test_subsequent_bid_needs_increment_and_notifies_previous_leader(self, mock_notify):
        first = place_bid(self.item.pk, self.alice, Decimal("25"))
        with self.assertRaises(BidError):
            place_bid(self.item.pk, self.bob, Decimal("29"))
        with self.captureOnCommitCallbacks(execute=True):
            place_bid(self.item.pk, self.bob, Decimal("30"))
        mock_notify.assert_called_once()
        self.assertEqual(mock_notify.call_args.args[0], first)

    def test_self_outbid_sends_no_notification(self, mock_notify):
        place_bid(self.item.pk, self.alice, Decimal("25"))
        with self.captureOnCommitCallbacks(execute=True):
            place_bid(self.item.pk, self.alice, Decimal("30"))
        mock_notify.assert_not_called()

    def test_closed_item_rejects_bids(self, mock_notify):
        self.item.close_time = timezone.now() - timedelta(minutes=1)
        self.item.save()
        with self.assertRaises(BidError):
            place_bid(self.item.pk, self.alice, Decimal("25"))

    def test_soft_close_extends_deadline(self, mock_notify):
        self.auction.soft_close_enabled = True
        self.auction.soft_close_minutes = 5
        self.auction.save()
        self.item.close_time = timezone.now() + timedelta(minutes=2)
        self.item.save()
        place_bid(self.item.pk, self.alice, Decimal("25"))
        self.item.refresh_from_db()
        remaining = self.item.close_time - timezone.now()
        self.assertGreater(remaining, timedelta(minutes=4))

    def test_no_soft_close_when_disabled(self, mock_notify):
        original = self.item.effective_close_time
        place_bid(self.item.pk, self.alice, Decimal("25"))
        self.item.refresh_from_db()
        self.assertEqual(self.item.effective_close_time, original)

    def test_sms_source_recorded(self, mock_notify):
        bid = place_bid(self.item.pk, self.alice, Decimal("25"), source=Bid.SOURCE_SMS)
        self.assertEqual(bid.source, "sms")
