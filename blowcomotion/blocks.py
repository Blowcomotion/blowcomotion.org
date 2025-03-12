from wagtail import blocks
from wagtail.images.blocks import ImageChooserBlock

from blowcomotion.chooser_blocks import EventChooserBlock, GigoGigChooserBlock


class HeroBlock(blocks.StructBlock):
    image = ImageChooserBlock()

    class Meta:
        icon = "image"
        label = "Hero"
        template = "blocks/hero_block.html"


class EventsBlock(blocks.StructBlock):
    scroller_title = blocks.CharBlock()
    gigo_gigs = blocks.ListBlock(
        blocks.StructBlock(
            [
                ("details", GigoGigChooserBlock()),
                ("event_scroller_image", ImageChooserBlock(required=False)),
            ]
        )
    )
    events = blocks.ListBlock(
        EventChooserBlock(), help_text="Events that are not associated with Gig-o-Matic"
    )

    class Meta:
        icon = "date"
        label = "Event Scroller"
        template = "blocks/events_block.html"
