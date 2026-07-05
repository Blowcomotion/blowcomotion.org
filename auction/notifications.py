import logging

from twilio.rest import Client
from wagtail.models import Site

from django.conf import settings
from django.contrib.auth.models import Group

from members.auth import _MemberEmail

logger = logging.getLogger(__name__)


def _root_url():
    site = Site.objects.filter(is_default_site=True).first() or Site.objects.first()
    return site.root_url if site else ""


def item_url(item):
    return f"{_root_url()}/auction/{item.auction_id}/item/{item.number}/"


def send_sms(to_phone, body):
    sid = getattr(settings, "TWILIO_ACCOUNT_SID", None)
    token = getattr(settings, "TWILIO_AUTH_TOKEN", None)
    from_number = getattr(settings, "TWILIO_FROM_NUMBER", None)
    if not (sid and token and from_number):
        logger.debug("Twilio not configured; SMS to %s skipped", to_phone)
        return
    try:
        Client(sid, token).messages.create(to=to_phone, from_=from_number, body=body)
    except Exception:
        logger.exception("Failed to send SMS to %s", to_phone)


def _send_email(subject, body, to):
    _MemberEmail(
        subject=subject, body=body, from_email=settings.FROM_EMAIL, to=to
    ).send(fail_silently=True)


def notify_outbid(previous_top_bid, new_bid):
    item = new_bid.item
    bidder = previous_top_bid.bidder
    url = item_url(item)
    next_min = item.minimum_bid
    _send_email(
        subject=f"You've been outbid on #{item.number} {item.title}",
        body=(
            f"Hi {bidder.name},\n\n"
            f"Someone bid ${new_bid.amount} on #{item.number} {item.title} — "
            f"you're no longer in the lead.\n\n"
            f"Bid again (at least ${next_min}): {url}\n"
        ),
        to=[bidder.email],
    )
    if bidder.sms_opt_in:
        send_sms(
            bidder.phone,
            f"You've been outbid on #{item.number} {item.title} — now ${new_bid.amount}. "
            f"Reply BID {item.number} {next_min} to retake the lead, or see it here: {url}",
        )


def notify_winner(item):
    bid = item.winning_bid
    if not bid:
        return
    bidder = bid.bidder
    instructions = item.auction.payment_instructions or ""
    _send_email(
        subject=f"You won #{item.number} {item.title}!",
        body=(
            f"Congratulations {bidder.name}!\n\n"
            f"You won #{item.number} {item.title} with a bid of ${bid.amount}.\n\n"
            f"{instructions}\n\n{item_url(item)}\n"
        ),
        to=[bidder.email],
    )
    if bidder.sms_opt_in:
        send_sms(
            bidder.phone,
            f"You won #{item.number} {item.title} for ${bid.amount}! {instructions}".strip(),
        )


def send_auction_summary(auction):
    try:
        group = Group.objects.get(name="Auctioneer")
    except Group.DoesNotExist:
        return
    recipients = [e for e in group.user_set.values_list("email", flat=True) if e]
    if not recipients:
        return
    lines, total = [], 0
    for item in auction.items.order_by("number"):
        if item.winning_bid:
            total += item.winning_bid.amount
            backup = item.backup_bid
            lines.append(
                f"#{item.number} {item.title}: ${item.winning_bid.amount} — "
                f"{item.winning_bid.bidder.name} ({item.winning_bid.bidder.email}, {item.winning_bid.bidder.phone})"
                + (f" [backup: {backup.bidder.name} ${backup.amount}]" if backup else "")
            )
        else:
            lines.append(f"#{item.number} {item.title}: no bids")
    body = f"{auction.name} — final results\n\n" + "\n".join(lines) + f"\n\nTotal raised: ${total}\n"
    _send_email(subject=f"Auction results: {auction.name}", body=body, to=recipients)
