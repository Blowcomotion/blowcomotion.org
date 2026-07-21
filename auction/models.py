import re

from modelcluster.fields import ParentalKey
from modelcluster.models import ClusterableModel
from wagtail.images import get_image_model_string
from wagtail.models import Orderable

from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Max
from django.utils import timezone


def normalize_phone(raw):
    """Normalize to E.164 so Twilio 'From' matching works. US default."""
    digits = re.sub(r"\D", "", raw or "")
    if (raw or "").strip().startswith("+") and len(digits) >= 8:
        return "+" + digits
    if len(digits) == 10:
        return "+1" + digits
    if len(digits) == 11 and digits.startswith("1"):
        return "+" + digits
    raise ValidationError("Enter a valid phone number (10 digits for US).")


class Auction(ClusterableModel):
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    close_time = models.DateTimeField(
        help_text="When bidding closes. Individual items may run longer if soft close extends them."
    )
    soft_close_enabled = models.BooleanField(
        default=False,
        help_text=(
            "Anti-sniping: a bid placed in the final minutes pushes that item's "
            "deadline out by the same window, so auctions end when bidding truly stops."
        ),
    )
    soft_close_minutes = models.PositiveIntegerField(default=5)
    payment_instructions = models.TextField(
        blank=True, help_text="Included in winner notifications (where/how to pay and pick up)."
    )
    summary_sent_at = models.DateTimeField(null=True, blank=True, editable=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return self.name

    def open_items_list(self):
        return [i for i in self.items.prefetch_related("images", "bids") if i.is_open]

    def closed_items_list(self):
        return [i for i in self.items.prefetch_related("images", "bids") if not i.is_open]

    def get_page(self):
        """The live page that embeds this auction via an AuctionBlock, if any."""
        from wagtail.models import Page, ReferenceIndex

        from django.contrib.contenttypes.models import ContentType

        ref = ReferenceIndex.get_references_to(self).filter(
            base_content_type=ContentType.objects.get_for_model(Page)
        ).first()
        if not ref:
            return None
        return Page.objects.live().filter(pk=ref.object_id).first()


class AuctionItem(ClusterableModel):
    auction = models.ForeignKey(Auction, on_delete=models.CASCADE, related_name="items")
    number = models.PositiveIntegerField(
        null=True,
        blank=True,
        help_text="Item number used on printed cards and in SMS bids (auto-assigned if blank).",
    )
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    starting_bid = models.DecimalField(max_digits=8, decimal_places=2)
    bid_increment = models.DecimalField(max_digits=8, decimal_places=2, default=1)
    close_time = models.DateTimeField(
        null=True, blank=True, help_text="Leave blank to use the auction's close time."
    )
    winning_bid = models.ForeignKey(
        "auction.Bid", null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    backup_bid = models.ForeignKey(
        "auction.Bid", null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    winner_notified_at = models.DateTimeField(null=True, blank=True, editable=False)

    class Meta:
        ordering = ["number"]
        constraints = [
            models.UniqueConstraint(fields=["auction", "number"], name="unique_item_number_per_auction"),
        ]

    def __str__(self):
        return f"#{self.number} {self.title}"

    def save(self, *args, **kwargs):
        if self.number is None:
            current = AuctionItem.objects.filter(auction=self.auction).aggregate(m=Max("number"))["m"] or 0
            self.number = current + 1
        super().save(*args, **kwargs)

    @property
    def effective_close_time(self):
        return self.close_time or self.auction.close_time

    @property
    def is_open(self):
        return self.winner_notified_at is None and self.effective_close_time > timezone.now()

    @property
    def top_bid(self):
        return self.bids.order_by("-amount", "created_at").first()

    @property
    def minimum_bid(self):
        top = self.top_bid
        return top.amount + self.bid_increment if top else self.starting_bid


class AuctionItemImage(Orderable):
    item = ParentalKey(AuctionItem, on_delete=models.CASCADE, related_name="images")
    image = models.ForeignKey(get_image_model_string(), on_delete=models.CASCADE, related_name="+")

    panels = ["image"]


class Bidder(models.Model):
    auction = models.ForeignKey(Auction, on_delete=models.CASCADE, related_name="bidders")
    member = models.ForeignKey(
        "blowcomotion.Member", null=True, blank=True, on_delete=models.SET_NULL, related_name="auction_bidders"
    )
    name = models.CharField(max_length=255)
    email = models.EmailField()
    phone = models.CharField(max_length=20)
    sms_opt_in = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["auction", "phone"], name="unique_bidder_phone_per_auction"),
            models.UniqueConstraint(fields=["auction", "email"], name="unique_bidder_email_per_auction"),
            models.UniqueConstraint(
                fields=["auction", "member"],
                condition=models.Q(member__isnull=False),
                name="unique_bidder_member_per_auction",
            ),
        ]

    def __str__(self):
        return f"{self.name} ({self.auction})"

    def save(self, *args, **kwargs):
        self.phone = normalize_phone(self.phone)
        super().save(*args, **kwargs)

    @property
    def display_name(self):
        parts = self.name.split()
        if len(parts) > 1:
            return f"{parts[0]} {parts[-1][0]}."
        return self.name


class Bid(models.Model):
    SOURCE_WEB = "web"
    SOURCE_SMS = "sms"
    item = models.ForeignKey(AuctionItem, on_delete=models.CASCADE, related_name="bids")
    bidder = models.ForeignKey(Bidder, on_delete=models.CASCADE, related_name="bids")
    amount = models.DecimalField(max_digits=8, decimal_places=2)
    source = models.CharField(
        max_length=3, choices=[(SOURCE_WEB, "Web"), (SOURCE_SMS, "SMS")], default=SOURCE_WEB
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"${self.amount} on {self.item} by {self.bidder.display_name}"
