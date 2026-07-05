from wagtail import blocks

from auction.blocks import AuctionBlock
from blowcomotion.blocks.content import (
    AlignableRichtextBlock,
    ButtonBlock,
    ImageBlock,
    ImageCarouselBlock,
)
from blowcomotion.blocks.forms import (
    BookingFormBlock,
    ContactFormBlock,
    DonateFormBlock,
    JoinBandFormBlock,
    PatreonButton,
    PayPalDonateButton,
    SquareDonateButton,
    VenmoDonateButton,
)
from blowcomotion.blocks.media import VideoFeedBlock


class HorizontalRuleBlock(blocks.StaticBlock):
    class Meta:
        template = "blocks/horizontal_rule_block.html"
        icon = "minus"
        label = "Horizontal Rule"
        help_text = "This is a horizontal rule block, it adds a horizontal line."
        help_text = "This block adds a horizontal rule."


class SpacerBlock(blocks.StaticBlock):
    class Meta:
        icon = "bi-arrows-expand"
        label = "Spacer"
        template = "blocks/spacer_block.html"
        help_text = "This is a spacer block, it adds 50px of vertical space. It does not display anything."


class AdjustableSpacerBlock(blocks.StructBlock):
    height = blocks.IntegerBlock(
        default=20,
        min_value=1,
        help_text="Enter the height of the spacer in pixels.",
    )

    class Meta:
        icon = "bi-arrows-expand"
        label = "Adjustable Spacer"
        template = "blocks/spacer_block.html"
        help_text = "This is a spacer block, it adds a vertical space between blocks. You can set the height of the spacer in pixels."


class AccordionListBlock(blocks.StructBlock):
    title = blocks.CharBlock(required=False)
    content = blocks.ListBlock(
        blocks.StructBlock(
            [
                ("title", blocks.CharBlock(required=False)),
                ("content", blocks.RichTextBlock(required=False)),
            ]
        )
    )


    class Meta:
        icon = "list-ul"
        template = "blocks/accordion_list_block.html"
        label_format = "Accordion List: {title}"
        help_text = "This is an accordion list block, it displays a list of items that can be expanded or collapsed."


class ColumnContentBlock(blocks.StreamBlock):
    accordion_list = AccordionListBlock()
    auction = AuctionBlock()
    booking_form = BookingFormBlock(group="Forms")
    button = ButtonBlock()
    contact_form = ContactFormBlock(group="Forms")
    donate_form = DonateFormBlock(group="Forms")
    join_band_form = JoinBandFormBlock(group="Forms")
    horizontal_rule = HorizontalRuleBlock()
    image = ImageBlock()
    image_carousel = ImageCarouselBlock()
    rich_text = AlignableRichtextBlock()
    adjustable_spacer = AdjustableSpacerBlock()
    spacer = SpacerBlock()
    paypal_donate_button = PayPalDonateButton()
    venmo_donate_button = VenmoDonateButton()
    square_donate_button = SquareDonateButton()
    patreon_button = PatreonButton()
    video_feed = VideoFeedBlock()

    class Meta:
        template = "blocks/column_content_block.html"


class ThreeColumnBlock(blocks.StructBlock):
    left_column = ColumnContentBlock(required=False)
    middle_column = ColumnContentBlock(required=False)
    right_column = ColumnContentBlock(required=False)
    show_left_border = blocks.BooleanBlock(
        required=False,
        default=False,
        help_text="Show vertical border on the right side of the left column"
    )
    show_right_border = blocks.BooleanBlock(
        required=False,
        default=False,
        help_text="Show vertical border on the right side of the middle column"
    )
    border_width = blocks.IntegerBlock(
        required=False,
        default=3,
        min_value=1,
        help_text="Border width in pixels"
    )
    border_color = blocks.CharBlock(
        required=False,
        default="#5b1a76",
        help_text="Border color (e.g., #5b1a76 or rgb(91, 26, 118))"
    )
    border_style = blocks.ChoiceBlock(
        choices=[
            ("solid", "Solid"),
            ("dashed", "Dashed"),
            ("dotted", "Dotted"),
        ],
        default="solid",
        help_text="Select the border style"
    )

    class Meta:
        template = "blocks/three_column_block.html"
        label_format = "Three Columns"


class TwoColumnBlock(ThreeColumnBlock):
    middle_column = None
    show_left_border = None
    show_right_border = None
    show_vertical_border = blocks.BooleanBlock(
        required=False,
        default=False,
        help_text="Show vertical border between the two columns"
    )
    left_column_width = blocks.ChoiceBlock(choices=[
            ("one-half", "One Half"),
            ("one-third", "One Third"),
            ("two-thirds", "Two Thirds"),
    ], default="one-half")

    def get_context(self, value, parent_context=None):
        context = super().get_context(value, parent_context)
        left_column_width = value["left_column_width"]

        width_map = {
            "one-half": ("6", "6"),
            "one-third": ("4", "8"),
            "two-thirds": ("8", "4"),
        }

        if left_column_width in width_map:
            context["left_column_width"], context["right_column_width"] = width_map[left_column_width]

        return context

    class Meta:
        template = "blocks/two_column_block.html"
        label_format = "Two Columns"


class FourColumnBlock(blocks.StructBlock):
    left_column = ColumnContentBlock(required=False)
    middle_left_column = ColumnContentBlock(required=False)
    middle_right_column = ColumnContentBlock(required=False)
    right_column = ColumnContentBlock(required=False)
    show_left_border = blocks.BooleanBlock(
        required=False,
        default=False,
        help_text="Show vertical border on the right side of the left column"
    )
    show_middle_border = blocks.BooleanBlock(
        required=False,
        default=False,
        help_text="Show vertical border on the right side of the middle-left column"
    )
    show_right_border = blocks.BooleanBlock(
        required=False,
        default=False,
        help_text="Show vertical border on the right side of the middle-right column"
    )
    border_width = blocks.IntegerBlock(
        required=False,
        default=3,
        min_value=1,
        help_text="Border width in pixels"
    )
    border_color = blocks.CharBlock(
        required=False,
        default="#5b1a76",
        help_text="Border color (e.g., #5b1a76 or rgb(91, 26, 118))"
    )
    border_style = blocks.ChoiceBlock(
        choices=[
            ("solid", "Solid"),
            ("dashed", "Dashed"),
            ("dotted", "Dotted"),
        ],
        default="solid",
        help_text="Select the border style"
    )

    class Meta:
        template = "blocks/four_column_block.html"
        label_format = "Four Columns"


class ColumnLayoutBlock(blocks.StreamBlock):
    spacer = AdjustableSpacerBlock()
    horizontal_rule = HorizontalRuleBlock()
    two_column = TwoColumnBlock()
    three_column = ThreeColumnBlock()
    four_column = FourColumnBlock()
