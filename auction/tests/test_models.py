from datetime import timedelta
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.test import TestCase
from django.utils import timezone

from auction.models import Auction, AuctionItem, Bid, Bidder, normalize_phone


def make_auction(**kwargs):
    defaults = dict(name="Fall Fundraiser", close_time=timezone.now() + timedelta(days=7))
    defaults.update(kwargs)
    return Auction.objects.create(**defaults)


def make_item(auction, **kwargs):
    defaults = dict(title="Yeti Cooler", starting_bid=Decimal("25"), bid_increment=Decimal("5"))
    defaults.update(kwargs)
    return AuctionItem.objects.create(auction=auction, **defaults)


def make_bidder(auction, **kwargs):
    defaults = dict(name="Robin Player", email="robin@example.com", phone="512-555-1234")
    defaults.update(kwargs)
    return Bidder.objects.create(auction=auction, **defaults)


class PhoneNormalizationTests(TestCase):
    def test_ten_digit_us(self):
        self.assertEqual(normalize_phone("512-555-1234"), "+15125551234")

    def test_eleven_digit_with_country_code(self):
        self.assertEqual(normalize_phone("1 (512) 555-1234"), "+15125551234")

    def test_international_plus_kept(self):
        self.assertEqual(normalize_phone("+44 20 7946 0958"), "+442079460958")

    def test_garbage_raises(self):
        with self.assertRaises(ValidationError):
            normalize_phone("123")


class AuctionItemTests(TestCase):
    def setUp(self):
        self.auction = make_auction()

    def test_number_auto_assigned_sequentially(self):
        a = make_item(self.auction)
        b = make_item(self.auction, title="Gift Card")
        self.assertEqual((a.number, b.number), (1, 2))

    def test_effective_close_time_falls_back_to_auction(self):
        item = make_item(self.auction)
        self.assertEqual(item.effective_close_time, self.auction.close_time)
        override = timezone.now() + timedelta(days=9)
        item.close_time = override
        self.assertEqual(item.effective_close_time, override)

    def test_minimum_bid_starting_then_increment(self):
        item = make_item(self.auction)
        self.assertEqual(item.minimum_bid, Decimal("25"))
        bidder = make_bidder(self.auction)
        Bid.objects.create(item=item, bidder=bidder, amount=Decimal("30"))
        self.assertEqual(item.top_bid.amount, Decimal("30"))
        self.assertEqual(item.minimum_bid, Decimal("35"))


class BidderTests(TestCase):
    def setUp(self):
        self.auction = make_auction()

    def test_phone_normalized_on_save(self):
        bidder = make_bidder(self.auction)
        self.assertEqual(bidder.phone, "+15125551234")

    def test_display_name(self):
        self.assertEqual(make_bidder(self.auction).display_name, "Robin P.")

    def test_phone_unique_per_auction(self):
        make_bidder(self.auction)
        with self.assertRaises(Exception):
            make_bidder(self.auction, email="other@example.com")

    def test_same_phone_ok_in_other_auction(self):
        make_bidder(self.auction)
        other = make_auction(name="Spring Fundraiser")
        self.assertIsNotNone(make_bidder(other))
