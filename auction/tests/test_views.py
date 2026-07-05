from datetime import timedelta
from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from auction.models import Bidder
from auction.tests.test_models import make_auction, make_bidder, make_item
from blowcomotion.models import Member
from members.auth import create_member_user

User = get_user_model()


@patch("blowcomotion.views._validate_recaptcha", return_value=(True, None))
class BidViewTests(TestCase):
    def setUp(self):
        self.auction = make_auction()
        self.item = make_item(self.auction)
        self.detail_url = reverse("auction-item-detail", args=[self.auction.pk, self.item.number])
        self.bid_url = reverse("auction-place-bid", args=[self.auction.pk, self.item.number])

    def register_and_bid(self, amount="25", **extra):
        data = dict(
            name="Robin Player", email="robin@example.com", phone="512-555-1234",
            sms_opt_in="on", amount=amount,
        )
        data.update(extra)
        return self.client.post(self.bid_url, data)

    def test_detail_renders(self, _):
        response = self.client.get(self.detail_url)
        self.assertContains(response, "Yeti Cooler")
        self.assertContains(response, "data-recaptcha")

    def test_guest_first_bid_registers_and_sets_cookie(self, _):
        response = self.register_and_bid()
        self.assertRedirects(response, self.detail_url)
        bidder = Bidder.objects.get(auction=self.auction, email="robin@example.com")
        self.assertTrue(bidder.sms_opt_in)
        self.assertIn(f"auction_bidder_{self.auction.pk}", response.cookies)

    def test_cookie_bidder_skips_registration_fields(self, _):
        self.register_and_bid()
        response = self.client.post(self.bid_url, {"amount": "30"})
        self.assertRedirects(response, self.detail_url)
        self.assertEqual(self.item.bids.count(), 2)

    def test_same_email_phone_reattaches_existing_bidder(self, _):
        self.register_and_bid()
        self.client.cookies.clear()
        self.register_and_bid(amount="30")
        self.assertEqual(Bidder.objects.filter(auction=self.auction).count(), 1)

    def test_too_low_bid_shows_error(self, _):
        # follow=True so the redirect is rendered once; Django flash messages are
        # single-consumption, so a separate second GET would see the message already
        # cleared. (Brief's original used assertRedirects + a second GET, which fails
        # for that reason -- see task-6-report.md.)
        response = self.client.post(
            self.bid_url,
            dict(name="Robin Player", email="robin@example.com", phone="512-555-1234",
                 sms_opt_in="on", amount="1"),
            follow=True,
        )
        self.assertContains(response, "at least $25")
        self.assertEqual(self.item.bids.count(), 0)

    def test_logged_in_member_prefills_and_links(self, _):
        member = Member.objects.create(
            first_name="Sam", last_name="Horn", email="sam@example.com", phone="512-555-8888"
        )
        user = create_member_user(member)
        user.set_password("Pass123!")
        user.save()
        self.client.login(username="sam@example.com", password="Pass123!")

        response = self.client.get(self.detail_url)
        self.assertContains(response, "sam@example.com")  # prefilled form

        self.client.post(self.bid_url, {
            "name": "Sam Horn", "email": "sam@example.com", "phone": "512-555-8888",
            "amount": "25",
        })
        bidder = Bidder.objects.get(auction=self.auction, member=member)
        self.assertEqual(self.item.bids.first().bidder, bidder)

    def test_guest_bidder_reattaches_to_member_on_login(self, _):
        # Guest registers and bids first.
        self.register_and_bid()
        self.client.cookies.clear()

        # Same person later logs in as a member with the same email/phone and bids
        # again. This must not 500 with an IntegrityError, and the guest Bidder row
        # should be reattached to the member rather than duplicated.
        member = Member.objects.create(
            first_name="Robin", last_name="Player", email="robin@example.com",
            phone="512-555-1234",
        )
        user = create_member_user(member)
        user.set_password("Pass123!")
        user.save()
        self.client.login(username="robin@example.com", password="Pass123!")

        response = self.client.post(self.bid_url, {
            "name": "Robin Player", "email": "robin@example.com", "phone": "512-555-1234",
            "amount": "30",
        })
        self.assertRedirects(response, self.detail_url)

        self.assertEqual(Bidder.objects.filter(auction=self.auction).count(), 1)
        bidder = Bidder.objects.get(auction=self.auction)
        self.assertEqual(bidder.member_id, member.pk)

    def test_expired_item_lazily_closed_on_view(self, _):
        self.item.close_time = timezone.now() - timedelta(minutes=1)
        self.item.save()
        make_bidder(self.auction)
        self.client.get(self.detail_url)
        self.item.refresh_from_db()
        self.assertIsNotNone(self.item.winner_notified_at)

    def test_recaptcha_failure_rejects(self, mock_captcha):
        mock_captcha.return_value = (False, "reCAPTCHA validation failed")
        response = self.register_and_bid()
        self.assertRedirects(response, self.detail_url)
        self.assertEqual(self.item.bids.count(), 0)
