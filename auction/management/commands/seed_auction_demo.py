"""
Seed a demo auction with items modeled on the fall-2025 fundraiser merchants
(per Beej's request in issue #116). Safe to re-run: skips if the demo auction
already exists. Dev only.
"""
from datetime import timedelta
from decimal import Decimal

from wagtail.images import get_image_model

from django.core.management.base import BaseCommand
from django.utils import timezone

from auction.models import Auction, AuctionItem, AuctionItemImage

ITEMS = [
    ("Yeti Cooler", Decimal("50"), Decimal("5")),
    ("Restaurant Gift Card - Dinner for Two", Decimal("25"), Decimal("5")),
    ("Local Brewery Tour + Tasting", Decimal("30"), Decimal("5")),
    ("Yoga Studio 10-Class Pass", Decimal("40"), Decimal("5")),
    ("Coffee Shop Gift Basket", Decimal("15"), Decimal("2")),
    ("Record Store Vinyl Bundle", Decimal("20"), Decimal("2")),
    ("Tattoo Shop Gift Certificate", Decimal("60"), Decimal("10")),
]


class Command(BaseCommand):
    help = "Create a demo auction with sample items for development/testing"

    def handle(self, *args, **options):
        name = "Demo Fall Fundraiser Auction"
        if Auction.objects.filter(name=name).exists():
            self.stdout.write("Demo auction already exists, skipping")
            return
        auction = Auction.objects.create(
            name=name,
            description="Demo data seeded for development.",
            close_time=timezone.now() + timedelta(days=14),
            soft_close_enabled=True,
            payment_instructions="Pay at the merch table after the show.",
        )
        Image = get_image_model()
        for title, start, increment in ITEMS:
            item = AuctionItem.objects.create(
                auction=auction, title=title, starting_bid=start, bid_increment=increment
            )
            image = Image.objects.filter(title__icontains=title.split()[0]).first()
            if image:
                AuctionItemImage.objects.create(item=item, image=image)
        self.stdout.write(self.style.SUCCESS(f"Seeded '{name}' with {len(ITEMS)} items"))
