import logging
import re
from decimal import Decimal

from twilio.request_validator import RequestValidator
from twilio.twiml.messaging_response import MessagingResponse

from django.conf import settings
from django.http import HttpResponse, HttpResponseForbidden
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from auction import notifications
from auction.models import AuctionItem, Bidder
from auction.services import BidError, place_bid

logger = logging.getLogger(__name__)

BID_RE = re.compile(r"^\s*bid\s+#?(\d+)\s+\$?(\d+(?:\.\d{1,2})?)\s*$", re.IGNORECASE)
USAGE = 'To bid, text: BID <item number> <amount> — for example "BID 12 60".'


def _signature_valid(request):
    token = getattr(settings, "TWILIO_AUTH_TOKEN", None)
    if not token:
        # Dev convenience only; production must have the token configured.
        return settings.DEBUG
    validator = RequestValidator(token)
    return validator.validate(
        request.build_absolute_uri(),
        request.POST.dict(),
        request.headers.get("X-Twilio-Signature", ""),
    )


def _twiml(text):
    response = MessagingResponse()
    response.message(text)
    return HttpResponse(str(response), content_type="text/xml")


def _handle_bid(bidder, item_number, amount):
    item = AuctionItem.objects.filter(auction=bidder.auction, number=item_number).first()
    if item is None:
        return f"No item #{item_number} in {bidder.auction.name}. {USAGE}"
    try:
        bid = place_bid(item.pk, bidder, amount, source="sms")
    except BidError as exc:
        return str(exc)
    return (
        f"You're the top bid on #{item.number} {item.title} at ${bid.amount}! "
        f"{notifications.item_url(item)}"
    )


@csrf_exempt
@require_POST
def sms_webhook(request):
    if not _signature_valid(request):
        logger.warning("Rejected SMS webhook call with invalid signature")
        return HttpResponseForbidden()

    from_number = request.POST.get("From", "")
    body = request.POST.get("Body", "")

    bidder = Bidder.objects.filter(phone=from_number).order_by("-created_at").first()
    if bidder is None:
        return _twiml(
            "We don't recognize this number. Place your first bid on the auction "
            "page to register, then you can bid by text."
        )

    match = BID_RE.match(body)
    if match:
        return _twiml(_handle_bid(bidder, int(match.group(1)), Decimal(match.group(2))))
    return _twiml(USAGE)
