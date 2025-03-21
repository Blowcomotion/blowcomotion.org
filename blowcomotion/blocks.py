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


class AlignableRichtextBlock(blocks.StructBlock):
    rich_text = blocks.RichTextBlock()
    align = blocks.ChoiceBlock(
        choices=[
            ("left", "Left"),
            ("center", "Center"),
            ("right", "Right"),
        ],
        default="left",
    )

    class Meta:
        template = "blocks/alignable_richtext_block.html"


class ColumnContentBlock(blocks.StreamBlock):
    rich_text = AlignableRichtextBlock()
    image = ImageChooserBlock(template="blocks/image_block.html")

    class Meta:
        template = "blocks/column_content_block.html"


class ThreeColumnBlock(blocks.StructBlock):
    left_column = ColumnContentBlock()
    middle_column = ColumnContentBlock()
    right_column = ColumnContentBlock()

    class Meta:
        template = "blocks/three_column_block.html"


class TwoColumnBlock(ThreeColumnBlock):
    middle_column = None

    class Meta:
        template = "blocks/two_column_block.html"


class FourColumnBlock(ThreeColumnBlock):
    left_column = ColumnContentBlock()
    middle_left_column = ColumnContentBlock()
    middle_right_column = ColumnContentBlock()
    right_column = ColumnContentBlock()

    class Meta:
        template = "blocks/four_column_block.html"


class ColumnLayoutBlock(blocks.StreamBlock):
    two_column = TwoColumnBlock()
    three_column = ThreeColumnBlock()
    four_column = FourColumnBlock()
