from datetime import timedelta

from django.db import transaction
from django.utils import timezone

from auction.models import AuctionItem, Bid


class BidError(Exception):
    """User-facing bid rejection; str(exc) is safe to show/text back."""


def place_bid(item_id, bidder, amount, source=Bid.SOURCE_WEB):
    with transaction.atomic():
        item = (
            AuctionItem.objects.select_for_update()
            .select_related("auction")
            .get(pk=item_id)
        )
        now = timezone.now()
        if item.winner_notified_at or item.effective_close_time <= now:
            raise BidError(f"Bidding on #{item.number} {item.title} has closed.")
        previous_top = item.top_bid
        minimum = item.minimum_bid
        if amount < minimum:
            raise BidError(f"Your bid on #{item.number} must be at least ${minimum}.")
        bid = Bid.objects.create(item=item, bidder=bidder, amount=amount, source=source)

        auction = item.auction
        if auction.soft_close_enabled:
            window = timedelta(minutes=auction.soft_close_minutes)
            if item.effective_close_time - now < window:
                item.close_time = now + window
                item.save(update_fields=["close_time"])

        if previous_top and previous_top.bidder_id != bidder.pk:
            from auction import notifications

            transaction.on_commit(lambda: notifications.notify_outbid(previous_top, bid))
        return bid
