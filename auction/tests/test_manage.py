from datetime import timedelta
from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from auction.models import Bid
from auction.services import close_expired_items
from auction.tests.test_models import make_auction, make_bidder, make_item

User = get_user_model()


class ManageViewTests(TestCase):
    def setUp(self):
        self.auction = make_auction(close_time=timezone.now() - timedelta(minutes=1))
        self.item = make_item(self.auction)
        self.alice = make_bidder(self.auction)
        self.bob = make_bidder(self.auction, name="Bob Jones", email="bob@example.com", phone="512-555-9999")
        Bid.objects.create(item=self.item, bidder=self.alice, amount=Decimal("30"))
        Bid.objects.create(item=self.item, bidder=self.bob, amount=Decimal("25"))
        with patch("auction.notifications.notify_winner"), patch(
            "auction.notifications.send_auction_summary"
        ):
            with self.captureOnCommitCallbacks(execute=True):
                close_expired_items()
        self.item.refresh_from_db()

        self.auctioneer = User.objects.create_user(username="beej", password="Pass123!")
        self.auctioneer.user_permissions.add(
            Permission.objects.get(codename="change_auctionitem")
        )

    def test_anonymous_denied(self):
        response = self.client.get(reverse("auction-manage"))
        self.assertEqual(response.status_code, 302)  # to login

    def test_anonymous_promote_denied(self):
        original_bid = self.item.winning_bid.pk
        response = self.client.post(reverse("auction-promote", args=[self.item.pk]))
        self.assertEqual(response.status_code, 302)  # to login
        self.item.refresh_from_db()
        self.assertEqual(self.item.winning_bid.pk, original_bid)  # no mutation

    def test_unprivileged_user_manage_denied(self):
        unprivileged = User.objects.create_user(username="alice", password="Pass123!")
        self.client.login(username="alice", password="Pass123!")
        response = self.client.get(reverse("auction-manage"))
        self.assertEqual(response.status_code, 403)

    def test_unprivileged_user_promote_denied(self):
        unprivileged = User.objects.create_user(username="alice", password="Pass123!")
        self.client.login(username="alice", password="Pass123!")
        original_bid = self.item.winning_bid.pk
        response = self.client.post(reverse("auction-promote", args=[self.item.pk]))
        self.assertEqual(response.status_code, 403)
        self.item.refresh_from_db()
        self.assertEqual(self.item.winning_bid.pk, original_bid)  # no mutation

    def test_auctioneer_sees_winner_and_backup(self):
        self.client.login(username="beej", password="Pass123!")
        response = self.client.get(reverse("auction-manage"))
        self.assertContains(response, "Robin P.")
        self.assertContains(response, "Bob J.")
        self.assertContains(response, "Promote")

    @patch("auction.notifications.notify_winner")
    def test_promote_swaps_and_notifies(self, mock_notify):
        self.client.login(username="beej", password="Pass123!")
        with self.captureOnCommitCallbacks(execute=True):
            response = self.client.post(reverse("auction-promote", args=[self.item.pk]))
        self.assertRedirects(response, reverse("auction-manage"))
        self.item.refresh_from_db()
        self.assertEqual(self.item.winning_bid.bidder, self.bob)
        self.assertIsNone(self.item.backup_bid)
        mock_notify.assert_called_once_with(self.item)
