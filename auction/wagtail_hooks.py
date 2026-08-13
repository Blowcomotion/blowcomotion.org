from wagtail.admin.panels import FieldPanel, InlinePanel
from wagtail.snippets.models import register_snippet
from wagtail.snippets.views.snippets import SnippetViewSet, SnippetViewSetGroup

from auction.models import Auction, AuctionItem, Bid, Bidder


class AuctionViewSet(SnippetViewSet):
    model = Auction
    menu_label = "Auctions"
    icon = "tag"
    list_display = ["name", "close_time", "soft_close_enabled"]
    panels = [
        FieldPanel("name"),
        FieldPanel("description"),
        FieldPanel("close_time"),
        FieldPanel("soft_close_enabled"),
        FieldPanel("soft_close_minutes"),
        FieldPanel("payment_instructions"),
    ]


class AuctionItemViewSet(SnippetViewSet):
    model = AuctionItem
    menu_label = "Items"
    icon = "clipboard-list"
    list_display = ["title", "number", "auction", "starting_bid"]
    list_filter = ["auction"]
    panels = [
        FieldPanel("auction"),
        FieldPanel("number", help_text="Leave blank to auto-assign the next number."),
        FieldPanel("title"),
        FieldPanel("description"),
        FieldPanel("starting_bid"),
        FieldPanel("bid_increment"),
        FieldPanel("close_time"),
        InlinePanel("images", label="Images (first one is the cover)"),
    ]


class BidderViewSet(SnippetViewSet):
    model = Bidder
    menu_label = "Bidders"
    icon = "user"
    list_display = ["name", "email", "phone", "sms_opt_in", "auction"]
    list_filter = ["auction"]


class BidViewSet(SnippetViewSet):
    model = Bid
    menu_label = "Bids"
    icon = "form"
    list_display = ["item", "bidder", "amount", "source", "created_at"]
    list_filter = ["item__auction", "source"]


class AuctionGroup(SnippetViewSetGroup):
    menu_label = "Auction"
    menu_icon = "tag"
    items = (AuctionViewSet, AuctionItemViewSet, BidderViewSet, BidViewSet)


register_snippet(AuctionGroup)
