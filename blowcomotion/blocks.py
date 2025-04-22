import datetime
import time
from datetime import timedelta, tzinfo

import requests
from django.conf import settings
from django.core.cache import cache
from django.utils import timezone
from wagtail import blocks
from wagtail.images.blocks import ImageChooserBlock

from blowcomotion.chooser_blocks import EventChooserBlock, GigoGigChooserBlock


class HeroBlock(blocks.StructBlock):
    image = ImageChooserBlock()
    top_line = blocks.CharBlock(required=False)
    middle_line = blocks.CharBlock(required=False)
    bottom_line = blocks.CharBlock(required=False)
    youtube_url = blocks.URLBlock(required=False)

    class Meta:
        icon = "image"
        template = "blocks/hero_block.html"
        label_format = "Hero: {top_line} {middle_line} {bottom_line}"


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
        template = "blocks/events_block.html"
        label_format = "Event Scroller: {scroller_title}"


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
        label_format = "({align}-aligned) {rich_text}"


class HorizontalRuleBlock(blocks.StaticBlock):
    class Meta:
        template = "blocks/horizontal_rule_block.html"
        icon = "minus"
        label = "Horizontal Rule"
        help_text = "This is a horizontal rule block, it adds a horizontal line."
        help_text = "This block adds a horizontal rule."


class SpacerBlock(blocks.StaticBlock):
    class Meta:
        icon = "placeholder"
        label = "Spacer"
        template = "blocks/spacer_block.html"
        help_text = "This is a spacer block, it adds 50px of vertical space. It does not display anything."


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


class ContactFormBlock(blocks.StructBlock):
    title = blocks.CharBlock(
        required=False,
        help_text="Enter the title for the contact form.",
    )
    description = blocks.RichTextBlock(
        required=False,
        help_text="Enter the description for the contact form.",
    )
    button_text = blocks.CharBlock(
        required=False,
        help_text="Enter the text for the button.",
    )


    class Meta:
        icon = "form"
        template = "blocks/contact_form_block.html"
        label_format = "Contact Form: {title}"
        help_text = "This contact form block displays a form for users to fill out. Submissions are sent to the email address specified in the settings. Submissions are also saved to the admin."


class PayPalDonateButton(blocks.StructBlock):
    alignment = blocks.ChoiceBlock(
        choices=[
            ("left", "Left"),
            ("center", "Center"),
            ("right", "Right"),
        ],
        default="center",
        help_text="Select the alignment for the button.",
    )

    class Meta:
        icon = "bi-paypal"
        template = "blocks/paypal_donate_button.html"
        label = "PayPal Donate Button"
        help_text = "This PayPal donate button is used to make Paypal donations."


class VenmoDonateButton(blocks.StructBlock):
    button_text = blocks.CharBlock(
        required=False,
        help_text="Enter the text for the button.",
    )
    alignment = blocks.ChoiceBlock(
        choices=[
            ("left", "Left"),
            ("center", "Center"),
            ("right", "Right"),
        ],
        default="center",
        help_text="Select the alignment for the button.",
    )

    class Meta:
        icon = "bi-currency-dollar"
        template = "blocks/venmo_donate_button.html"
        label = "Venmo Donate Button"
        help_text = "This is Venmo donate button adds a button for making Venmo donations. The Venmo url is set in the settings if your admin account has permission to change it."


class ButtonBlock(blocks.StructBlock):
    button_text = blocks.CharBlock(
        required=False,
        help_text="Enter the text for the button.",
    )
    button_url = blocks.URLBlock(
        required=False,
        help_text="Enter the URL for the button.",
    )
    button_target = blocks.ChoiceBlock(
        choices=[
            ("_self", "Same Tab"),
            ("_blank", "New Tab"),
        ],
        default="_self",
        help_text="Select the target for the button.",
    )
    button_alignment = blocks.ChoiceBlock(
        choices=[
            ("left", "Left"),
            ("center", "Center"),
            ("right", "Right"),
        ],
        default="center",
        help_text="Select the alignment for the button.",
    )
    button_width = blocks.ChoiceBlock(
        choices=[
            ("half", "Half"),
            ("full", "Full"),
        ],
        default="half",
        help_text="Select the width for the button.",
    )

    class Meta:
        icon = "link"
        template = "blocks/button_block.html"
        label_format = "Button: {button_text}"


class ColumnContentBlock(blocks.StreamBlock):
    accordion_list = AccordionListBlock()
    button = ButtonBlock()
    contact_form = ContactFormBlock()
    horizontal_rule = HorizontalRuleBlock()
    image = ImageChooserBlock(template="blocks/image_block.html")
    paypal_donate_button = PayPalDonateButton()
    rich_text = AlignableRichtextBlock()
    spacer = SpacerBlock()
    venmo_donate_button = VenmoDonateButton()

    class Meta:
        template = "blocks/column_content_block.html"


class ThreeColumnBlock(blocks.StructBlock):
    left_column = ColumnContentBlock(required=False)
    middle_column = ColumnContentBlock(required=False)
    right_column = ColumnContentBlock(required=False)

    class Meta:
        template = "blocks/three_column_block.html"
        label_format = "Three Columns"


class TwoColumnBlock(ThreeColumnBlock):
    middle_column = None

    class Meta:
        template = "blocks/two_column_block.html"
        label_format = "Two Columns"


class FourColumnBlock(ThreeColumnBlock):
    left_column = ColumnContentBlock(required=False)
    middle_left_column = ColumnContentBlock(required=False)
    middle_right_column = ColumnContentBlock(required=False)
    right_column = ColumnContentBlock(required=False)

    class Meta:
        template = "blocks/four_column_block.html"
        label_format = "Four Columns"


class ColumnLayoutBlock(blocks.StreamBlock):
    two_column = TwoColumnBlock()
    three_column = ThreeColumnBlock()
    four_column = FourColumnBlock()


class MenuItemBlock(blocks.StructBlock):
    page = blocks.PageChooserBlock()
    label = blocks.CharBlock(required=False)
    


class MenuItem(blocks.StructBlock):
    page = blocks.PageChooserBlock()
    label = blocks.CharBlock(required=False)
    submenus = blocks.ListBlock(MenuItemBlock, required=False, collapsed=True)


class UpcomingPublicGigs(blocks.StructBlock):
    headline = blocks.CharBlock(
        required=False,
        help_text="Enter the headline for the upcoming public gigs.",
    )

    def get_context(self, value, parent_context=None):
        context = super().get_context(value, parent_context)
        try:
            context['gigs'] = cache.get('upcoming_public_gigs')
            if context['gigs'] is None:
                r = requests.get(
                        f"{settings.GIGO_API_URL}/gigs",
                        headers={"X-API-KEY": settings.GIGO_API_KEY},
                    )
                context['gigs'] = [gig for gig in r.json()['gigs'] if gig['gig_status'].lower() == 'confirmed' and gig['band'].lower() == 'blowcomotion' and gig["date"] >= datetime.date.today().isoformat() and gig['is_private'] == False and gig["hide_from_calendar"] == False and gig["is_archived"] == False and gig["is_in_trash"] == False]
                localtime = time.localtime()
                for gig in context['gigs']:
                    gig['date'] = datetime.datetime.strptime(gig['date'], "%Y-%m-%d")
                    gig['set_time'] = datetime.datetime.strptime(gig['set_time'], "%H:%M").replace(tzinfo=datetime.timezone.utc)
                    gig['set_time'] = gig['set_time'] + timedelta(hours=localtime.tm_isdst)
                context['gigs'].sort(key=lambda gig: gig['date'])

                cache.set('upcoming_public_gigs', context['gigs'], 60 * 60) # cache for 1 hour
        except Exception as e:
            context['error'] = str(e)
            context['gigs'] = []
        return context

    class Meta:
        icon = "date"
        label = "Upcoming Public Gigs"
        help_text = "This displays a list of confirmed upcoming public Blowco gigs as a list."
        template = "blocks/upcoming_public_gigs.html"
        preview_value = {}


class QuotedImageBlock(blocks.StructBlock):
    image = ImageChooserBlock()
    header = blocks.CharBlock(required=False)
    subheader = blocks.TextBlock(required=False)
    author = blocks.CharBlock(required=False)

    class Meta:
        icon = "image"
        label = "Quoted Image"
        template = "blocks/quoted_image_block.html"
        preview_value = {
            "header": "This is a header",
            "subheader": "This is a subheader",
            "author": "This is an author",
        }


class MultiImageBannerBlock(blocks.StructBlock):
    images = blocks.ListBlock(
        ImageChooserBlock(),
        help_text="Select images to display in the banner.",
        min_num=7,
        max_num=7,
    )

    class Meta:
        icon = "image"
        template = "blocks/multi_image_banner_block.html"
        preview_template = "blocks/previews/multi_image_banner_block.html"
        label_format = "Multi Image Banner"


class FullWidthImageBlock(blocks.StructBlock):
    image = ImageChooserBlock()

    class Meta:
        icon = "image"
        template = "blocks/full_width_image_block.html"
        label_format = "Full Width Image: {image}"


class CountdownBlock(blocks.StructBlock):
    background_image = ImageChooserBlock(required=False)
    countdown_date = blocks.DateBlock(
        help_text="Enter the date for the countdown."
    )
    head_line = blocks.CharBlock(
        required=False,
        help_text="Enter the top line text for the countdown.",
    )
    sub_line = blocks.CharBlock(
        required=False,
        help_text="Enter the sub line text for the countdown.",
    )
    button_text = blocks.CharBlock(
        required=False,
        help_text="Enter the text for the button.",
    )
    button_url = blocks.URLBlock(
        required=False,
        help_text="Enter the URL for the button.",
    )
    button_target = blocks.ChoiceBlock(
        choices=[
            ("_self", "Same Tab"),
            ("_blank", "New Tab"),
        ],
        default="_self",
        help_text="Select the target for the button.",
    )

    
    class Meta:
        icon = "calendar-alt"
        template = "blocks/countdown_block.html"
        label_format = "Countdown to {countdown_date}"

