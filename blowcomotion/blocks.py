from wagtail import blocks
from wagtail.images.blocks import ImageChooserBlock

from blowcomotion import chooser_blocks


class HeroBlock(blocks.StructBlock):
    image = ImageChooserBlock()

    class Meta:
        icon = 'image'
        label = 'Hero'
        template = 'blocks/hero_block.html'

class EventsBlock(blocks.StructBlock):
    scroller_title = blocks.CharBlock()
    events = blocks.ListBlock(
        chooser_blocks.EventChooserBlock(),
    )

    class Meta:
        icon = 'date'
        label = 'Event Scroller'
        template = 'blocks/events_block.html'
