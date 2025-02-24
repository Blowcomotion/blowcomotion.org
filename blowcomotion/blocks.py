from wagtail import blocks
from wagtail.images.blocks import ImageChooserBlock


class HeroBlock(blocks.StructBlock):
    image = ImageChooserBlock()

    class Meta:
        icon = 'image'
        label = 'Hero'
        template = 'blocks/hero_block.html'

class EventsBlock(blocks.StructBlock):
    title = blocks.CharBlock()
    date = blocks.DateBlock()
    location = blocks.CharBlock()
    description = blocks.RichTextBlock()

    class Meta:
        icon = 'date'
        label = 'Event'
        template = 'blocks/events_block.html'
