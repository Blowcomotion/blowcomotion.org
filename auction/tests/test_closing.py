from datetime import timedelta
from decimal import Decimal
from unittest.mock import patch

from django.core.management import call_command
from django.test import TestCase
from django.utils import timezone

from auction.models import Bid
from auction.services import close_expired_items
from auction.tests.test_models import make_auction, make_bidder, make_item


@patch("auction.notifications.send_auction_summary")
@patch("auction.notifications.notify_winner")
class CloseExpiredItemsTests(TestCase):
    def setUp(self):
        self.auction = make_auction(close_time=timezone.now() - timedelta(minutes=1))
        self.item = make_item(self.auction)
        self.alice = make_bidder(self.auction)
        self.bob = make_bidder(self.auction, name="Bob Jones", email="bob@example.com", phone="512-555-9999")

    def _close(self):
        with self.captureOnCommitCallbacks(execute=True):
            return close_expired_items()

    def test_picks_winner_and_backup(self, mock_winner, mock_summary):
        Bid.objects.create(item=self.item, bidder=self.alice, amount=Decimal("25"))
        Bid.objects.create(item=self.item, bidder=self.bob, amount=Decimal("30"))
        Bid.objects.create(item=self.item, bidder=self.alice, amount=Decimal("35"))
        closed = self._close()
        self.item.refresh_from_db()
        self.assertEqual(closed, 1)
        self.assertEqual(self.item.winning_bid.bidder, self.alice)
        self.assertEqual(self.item.winning_bid.amount, Decimal("35"))
        self.assertEqual(self.item.backup_bid.bidder, self.bob)  # highest by a DIFFERENT bidder
        mock_winner.assert_called_once_with(self.item)

    def test_no_bids_closes_silently(self, mock_winner, mock_summary):
        self._close()
        self.item.refresh_from_db()
        self.assertIsNotNone(self.item.winner_notified_at)
        self.assertIsNone(self.item.winning_bid)
        mock_winner.assert_not_called()

    def test_idempotent(self, mock_winner, mock_summary):
        Bid.objects.create(item=self.item, bidder=self.alice, amount=Decimal("25"))
        self._close()
        self.assertEqual(self._close(), 0)
        mock_winner.assert_called_once()

    def test_open_items_untouched(self, mock_winner, mock_summary):
        self.item.close_time = timezone.now() + timedelta(days=1)
        self.item.save()
        self.assertEqual(self._close(), 0)

    def test_summary_sent_once_when_auction_fully_closed(self, mock_winner, mock_summary):
        self._close()
        mock_summary.assert_called_once_with(self.auction)
        self._close()
        mock_summary.assert_called_once()

    def test_management_command_runs(self, mock_winner, mock_summary):
        call_command("close_auction_items")
        self.item.refresh_from_db()
        self.assertIsNotNone(self.item.winner_notified_at)
