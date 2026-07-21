import logging

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required, permission_required
from django.db import IntegrityError
from django.http import HttpResponseNotFound
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from auction.forms import BidderRegistrationForm, BidForm
from auction.models import Auction, AuctionItem, Bidder
from auction.services import BidError, close_expired_items, place_bid, promote_backup
from blowcomotion import views as blowcomotion_views

logger = logging.getLogger(__name__)

BIDDER_COOKIE_SALT = "auction-bidder"
BIDDER_COOKIE_MAX_AGE = 60 * 60 * 24 * 30


def _cookie_name(auction):
    return f"auction_bidder_{auction.pk}"


def resolve_bidder(request, auction):
    if request.user.is_authenticated and hasattr(request.user, "member"):
        bidder = auction.bidders.filter(member=request.user.member).first()
        if bidder:
            return bidder
    try:
        bidder_id = request.get_signed_cookie(
            _cookie_name(auction), default=None, salt=BIDDER_COOKIE_SALT
        )
    except Exception:
        bidder_id = None
    if bidder_id:
        return auction.bidders.filter(pk=bidder_id).first()
    return None


def _lazy_close(auction):
    from django.db.models import Q
    from django.utils import timezone

    now = timezone.now()
    pending = auction.items.filter(winner_notified_at__isnull=True).filter(
        Q(close_time__lte=now) | Q(close_time__isnull=True, auction__close_time__lte=now)
    )
    if pending.exists():
        close_expired_items(auction)


def _registration_initial(request):
    if request.user.is_authenticated and hasattr(request.user, "member"):
        member = request.user.member
        return {"name": member.full_name, "email": member.email, "phone": member.phone or ""}
    return {}


def item_detail(request, auction_id, number):
    auction = get_object_or_404(Auction, pk=auction_id)
    _lazy_close(auction)
    item = get_object_or_404(
        AuctionItem.objects.select_related("auction"), auction=auction, number=number
    )
    bidder = resolve_bidder(request, auction)
    return render(request, "auction/item_detail.html", {
        "auction": auction,
        "item": item,
        "bidder": bidder,
        "bids": item.bids.select_related("bidder").order_by("-amount"),
        "registration_form": BidderRegistrationForm(initial=_registration_initial(request)),
        "bid_form": BidForm(initial={"amount": item.minimum_bid}),
        "include_form_js": True,
    })


def grid_partial(request, auction_id):
    if request.headers.get("HX-Request") != "true":
        return HttpResponseNotFound()
    auction = get_object_or_404(Auction, pk=auction_id)
    _lazy_close(auction)
    items = list(auction.items.prefetch_related("images", "bids"))
    return render(request, "auction/_grid.html", {
        "auction": auction,
        "open_items": [i for i in items if i.is_open],
        "closed_items": [i for i in items if not i.is_open],
    })


def _get_or_register_bidder(request, auction):
    """Returns (bidder, error_message)."""
    bidder = resolve_bidder(request, auction)
    if bidder:
        return bidder, None
    form = BidderRegistrationForm(request.POST)
    if not form.is_valid():
        return None, "; ".join(f"{f}: {e[0]}" for f, e in form.errors.items())
    data = form.cleaned_data
    member = request.user.member if (
        request.user.is_authenticated and hasattr(request.user, "member")
    ) else None
    if member:
        existing = Bidder.objects.filter(
            auction=auction, email__iexact=data["email"], phone=data["phone"]
        ).first()
        if existing and not existing.member_id:
            existing.member = member
            existing.save(update_fields=["member"])
            return existing, None
        try:
            bidder, created = Bidder.objects.get_or_create(
                auction=auction, member=member,
                defaults=dict(name=data["name"], email=data["email"],
                              phone=data["phone"], sms_opt_in=data["sms_opt_in"]),
            )
        except IntegrityError:
            return None, (
                "That email or phone is already registered in this auction. "
                "Enter the exact same email AND phone you registered with."
            )
        if not created:
            return bidder, None
    else:
        bidder = Bidder.objects.filter(
            auction=auction, email__iexact=data["email"], phone=data["phone"]
        ).first()
        if not bidder:
            try:
                bidder = Bidder.objects.create(
                    auction=auction, name=data["name"], email=data["email"],
                    phone=data["phone"], sms_opt_in=data["sms_opt_in"],
                )
            except Exception:
                return None, (
                    "That email or phone is already registered in this auction. "
                    "Enter the exact same email AND phone you registered with."
                )
    return bidder, None


@require_POST
def place_bid_view(request, auction_id, number):
    auction = get_object_or_404(Auction, pk=auction_id)
    item = get_object_or_404(AuctionItem, auction=auction, number=number)
    detail = redirect("auction-item-detail", auction_id=auction.pk, number=item.number)

    is_valid, error = blowcomotion_views._validate_recaptcha(request)
    if not is_valid:
        messages.error(request, error or "reCAPTCHA validation failed. Please try again.")
        return detail

    bidder, reg_error = _get_or_register_bidder(request, auction)
    if reg_error:
        messages.error(request, reg_error)
        return detail

    bid_form = BidForm(request.POST)
    if not bid_form.is_valid():
        messages.error(request, "Enter a valid bid amount.")
        return detail

    try:
        bid = place_bid(item.pk, bidder, bid_form.cleaned_data["amount"])
    except BidError as exc:
        messages.error(request, str(exc))
        return detail

    messages.success(request, f"You're the top bid on #{item.number} {item.title} at ${bid.amount}!")
    if not bidder.member_id:
        detail.set_signed_cookie(
            _cookie_name(auction), bidder.pk,
            salt=BIDDER_COOKIE_SALT, max_age=BIDDER_COOKIE_MAX_AGE, httponly=True, samesite="Lax",
            secure=not settings.DEBUG,
        )
    return detail


@login_required
@permission_required("auction.change_auctionitem", raise_exception=True)
def manage(request):
    auctions = Auction.objects.prefetch_related(
        "items__winning_bid__bidder", "items__backup_bid__bidder", "items__bids"
    )
    return render(request, "auction/manage.html", {"auctions": auctions})


@login_required
@permission_required("auction.change_auctionitem", raise_exception=True)
@require_POST
def promote(request, pk):
    item = get_object_or_404(AuctionItem, pk=pk)
    try:
        promote_backup(item)
        messages.success(request, f"Backup promoted to winner on #{item.number} {item.title}.")
    except BidError as exc:
        messages.error(request, str(exc))
    return redirect("auction-manage")
