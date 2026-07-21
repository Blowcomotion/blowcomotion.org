from wagtail import blocks
from wagtail.snippets.blocks import SnippetChooserBlock


class AuctionBlock(blocks.StructBlock):
    intro = blocks.RichTextBlock(required=False)
    auction = SnippetChooserBlock("auction.Auction")

    class Meta:
        template = "auction/blocks/auction_block.html"
        icon = "tag"
        label = "Auction"
