from datetime import timedelta

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from auction.tests.test_models import make_auction, make_item


class GridPartialTests(TestCase):
    def setUp(self):
        self.auction = make_auction()
        self.open_item = make_item(self.auction)
        self.closed_item = make_item(
            self.auction, title="Gift Card", close_time=timezone.now() - timedelta(minutes=1)
        )

    def test_grid_splits_open_and_completed(self):
        response = self.client.get(reverse("auction-grid", args=[self.auction.pk]))
        self.assertContains(response, "Yeti Cooler")
        self.assertContains(response, "Gift Card")
        self.assertContains(response, "Completed")
        self.assertContains(response, "Last refreshed")

    def test_blank_canvas_page_offers_auction_block(self):
        from blowcomotion.models.pages import BlankCanvasPage

        body_field = BlankCanvasPage._meta.get_field("body")
        self.assertIn("auction", body_field.stream_block.child_blocks)
