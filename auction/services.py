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


def close_expired_items(auction=None):
    """Pick winner + backup for every expired, unprocessed item. Idempotent."""
    from django.db.models import Q

    from auction import notifications
    from auction.models import Auction

    now = timezone.now()
    closed = 0
    qs = AuctionItem.objects.filter(winner_notified_at__isnull=True).filter(
        Q(close_time__lte=now) | Q(close_time__isnull=True, auction__close_time__lte=now)
    )
    if auction is not None:
        qs = qs.filter(auction=auction)
    touched_auction_ids = set()
    with transaction.atomic():
        for item in qs.select_for_update().select_related("auction"):
            top = item.top_bid
            if top:
                item.winning_bid = top
                item.backup_bid = (
                    item.bids.exclude(bidder=top.bidder).order_by("-amount", "created_at").first()
                )
            item.winner_notified_at = now
            item.save(update_fields=["winning_bid", "backup_bid", "winner_notified_at"])
            touched_auction_ids.add(item.auction_id)
            closed += 1
            if top:
                transaction.on_commit(lambda i=item: notifications.notify_winner(i))
        for a in Auction.objects.select_for_update().filter(
            pk__in=touched_auction_ids, summary_sent_at__isnull=True
        ):
            if not a.items.filter(winner_notified_at__isnull=True).exists():
                a.summary_sent_at = now
                a.save(update_fields=["summary_sent_at"])
                transaction.on_commit(lambda a=a: notifications.send_auction_summary(a))
    return closed


def promote_backup(item):
    """Auctioneer action: the winner flaked, promote the backup and notify them."""
    from auction import notifications

    with transaction.atomic():
        item = AuctionItem.objects.select_for_update().get(pk=item.pk)
        if not item.backup_bid:
            raise BidError("This item has no backup bidder to promote.")
        item.winning_bid = item.backup_bid
        item.backup_bid = None
        item.winner_notified_at = timezone.now()
        item.save(update_fields=["winning_bid", "backup_bid", "winner_notified_at"])
        transaction.on_commit(lambda: notifications.notify_winner(item))
