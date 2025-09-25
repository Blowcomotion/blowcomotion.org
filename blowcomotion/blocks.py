import datetime
import time
from datetime import timedelta, tzinfo

import requests
from wagtail import blocks
from wagtail.images.blocks import ImageChooserBlock

from django.conf import settings
from django.core.cache import cache
from django.utils import timezone

from blowcomotion.chooser_blocks import (
    EventChooserBlock,
    GigoGigChooserBlock,
    SongChooserBlock,
)


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
        icon = "edit"
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
    newsletter_opt_in = blocks.BooleanBlock(
        required=False,
        help_text="Include an opt-in checkbox for the newsletter.",
    )


    class Meta:
        icon = "form"
        template = "blocks/contact_form_block.html"
        label_format = "Contact Form: {title}"
        help_text = "This contact form block displays a form for users to fill out. Submissions are sent to the email address specified in the settings. Submissions are also saved to the admin."


class JoinBandFormBlock(blocks.StructBlock):
    title = blocks.CharBlock(
        required=False,
        help_text="Enter the title for the join band form.",
    )
    description = blocks.RichTextBlock(
        required=False,
        help_text="Enter the description for the join band form.",
    )
    button_text = blocks.CharBlock(
        required=False,
        help_text="Enter the text for the button.",
    )
    instrument_field_label = blocks.CharBlock(
        required=False,
        default="What instrument do you play?",
        help_text="Enter the label for the instrument field.",
    )
    instrument_rental_field_label = blocks.CharBlock(
        required=False,
        default="Would you like to rent an instrument?",
        help_text="Enter the label for the instrument rental field.",
    )
    message_field_label = blocks.CharBlock(
        required=False,
        default="Additional message/notes:",
        help_text="Enter the label for the message field.",
    )
    newsletter_opt_in = blocks.BooleanBlock(
        required=False,
        help_text="Include an opt-in checkbox for the newsletter.",
    )


    class Meta:
        icon = "group"
        template = "blocks/join_band_form_block.html"
        label_format = "Join Band Form: {title}"
        help_text = "This join band form block displays a form for people interested in joining the band. Submissions are sent to the email address specified in the settings. Submissions are also saved to the admin."


class BookingFormBlock(blocks.StructBlock):
    title = blocks.CharBlock(
        required=False,
        help_text="Enter the title for the booking form.",
    )
    description = blocks.RichTextBlock(
        required=False,
        help_text="Enter the description for the booking form.",
    )
    button_text = blocks.CharBlock(
        required=False,
        help_text="Enter the text for the button.",
    )
    name_field_label = blocks.CharBlock(
        required=False,
        default="Your Name:",
        help_text="Enter the label for the name field.",
    )
    email_field_label = blocks.CharBlock(
        required=False,
        default="Your Email:",
        help_text="Enter the label for the email field.",
    )
    message_field_label = blocks.CharBlock(
        required=False,
        default="Tell us about your event:",
        help_text="Enter the label for the message field.",
    )
    newsletter_opt_in = blocks.BooleanBlock(
        required=False,
        help_text="Include an opt-in checkbox for the newsletter.",
    )


    class Meta:
        icon = "calendar-alt"
        template = "blocks/booking_form_block.html"
        label_format = "Booking Form: {title}"
        help_text = "This booking form block displays a form for people interested in booking the band for events. Submissions are sent to the email address specified in the settings. Submissions are also saved to the admin."


class DonateFormBlock(blocks.StructBlock):
    title = blocks.CharBlock(
        required=False,
        help_text="Enter the title for the donate form.",
    )
    description = blocks.RichTextBlock(
        required=False,
        help_text="Enter the description for the donate form.",
    )
    button_text = blocks.CharBlock(
        required=False,
        help_text="Enter the text for the button.",
    )
    name_field_label = blocks.CharBlock(
        required=False,
        default="Your Name:",
        help_text="Enter the label for the name field.",
    )
    email_field_label = blocks.CharBlock(
        required=False,
        default="Your Email:",
        help_text="Enter the label for the email field.",
    )
    message_field_label = blocks.CharBlock(
        required=False,
        default="Message:",
        help_text="Enter the label for the message field.",
    )
    newsletter_opt_in = blocks.BooleanBlock(
        required=False,
        help_text="Include an opt-in checkbox for the newsletter.",
    )


    class Meta:
        icon = "bi-currency-dollar"
        template = "blocks/donate_form_block.html"
        label_format = "Donate Form: {title}"
        help_text = "This donate form block displays a form for people interested in making donations. Submissions are sent to the email address specified in the settings. Submissions are also saved to the admin."


class PayPalDonateButton(blocks.StructBlock):
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
    button_text = blocks.CharBlock(
        required=False,
        default="Donate with PayPal",
        help_text="Enter the text for the button.",
    )

    class Meta:
        icon = "bi-paypal"
        template = "blocks/paypal_donate_button.html"
        label = "PayPal Donate Button"
        help_text = "This PayPal donate button is used to make Paypal donations. The PayPal url is set in the settings if your admin account has permission to change it. The button will be aligned according to the selected alignment."


class VenmoDonateButton(blocks.StructBlock):
    button_text = blocks.CharBlock(
        required=False,
        help_text="Enter the text for the button.",
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
        icon = "bi-currency-dollar"
        template = "blocks/venmo_donate_button.html"
        label = "Venmo Donate Button"
        help_text = "This is Venmo donate button adds a button for making Venmo donations. The Venmo url is set in the settings if your admin account has permission to change it. The button will be aligned according to the selected alignment."


class PatreonButton(blocks.StructBlock):
    button_text = blocks.CharBlock(
        required=False,
        help_text="Enter the text for the button.",
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
        icon = "bi-currency-dollar"
        template = "blocks/patreon_button.html"
        label = "Patreon Button"
        help_text = "This is Patreon button adds a button for making Patreon donations. The Patreon url is set in the settings if your admin account has permission to change it. The button will be aligned according to the selected alignment."


class SquareDonateButton(blocks.StructBlock):
    button_text = blocks.CharBlock(
        required=False,
        help_text="Enter the text for the button.",
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
        icon = "bi-currency-dollar"
        template = "blocks/square_donate_button.html"
        label = "Square Donate Button"
        help_text = "This is Square donate button adds a button for making Square donations. The Square url is set in the settings if your admin account has permission to change it. The button will be aligned according to the selected alignment."


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


class JukeBoxBlock(blocks.StructBlock):
    foreground_text = blocks.CharBlock(
        required=False,
        help_text="Enter the foreground title text for the jukebox.",
    )
    background_text = blocks.CharBlock(
        required=False,
        help_text="Enter the background title text for the jukebox.",
    )
    jukebox_image = ImageChooserBlock(
        required=False,
        help_text="Select the image for the jukebox.",
    )
    lazy_loading = blocks.BooleanBlock(
        default=True,
        required=False,
        help_text="Enable lazy loading for better performance. Audio files will only load when the user clicks play.",
    )
    preload_first_track = blocks.BooleanBlock(
        default=True,
        required=False,
        help_text="Preload the first track's metadata for immediate playback. Only applies when lazy loading is enabled.",
    )

    tracks = blocks.ListBlock(
        SongChooserBlock(),
        help_text="Select the songs for the jukebox. A song must have a recording for it to show up in the jukebox.",
        min_num=1,
    )

    class Meta:
        icon = "bi-music-note-beamed"
        template = "blocks/jukebox_block.html"
        


class ImageBlock(blocks.StructBlock):
    image = ImageChooserBlock()
    url = blocks.URLBlock(required=False, help_text="Optional: Link the image to a URL (e.g. merch page)")

    class Meta:
        icon = "image"
        template = "blocks/image_block.html"
        label_format = "Image: {image}"


class ColumnContentBlock(blocks.StreamBlock):
    accordion_list = AccordionListBlock()
    booking_form = BookingFormBlock(group="Forms")
    button = ButtonBlock()
    contact_form = ContactFormBlock(group="Forms")
    donate_form = DonateFormBlock(group="Forms")
    join_band_form = JoinBandFormBlock(group="Forms")
    horizontal_rule = HorizontalRuleBlock()
    image = ImageBlock()
    rich_text = AlignableRichtextBlock()
    adjustable_spacer = AdjustableSpacerBlock()
    spacer = SpacerBlock()
    paypal_donate_button = PayPalDonateButton()
    venmo_donate_button = VenmoDonateButton()
    square_donate_button = SquareDonateButton()
    patreon_button = PatreonButton()

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

    class Meta:
        template = "blocks/four_column_block.html"
        label_format = "Four Columns"


class ColumnLayoutBlock(blocks.StreamBlock):
    spacer = AdjustableSpacerBlock()
    horizontal_rule = HorizontalRuleBlock()
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
                validated_gigs = []
                for gig in context['gigs']:
                    # Parse and validate date; skip if invalid
                    try:
                        parsed_date = datetime.datetime.strptime(gig.get('date', ''), "%Y-%m-%d")
                    except (ValueError, TypeError):  # includes missing or malformed date
                        continue

                    # Prefer set_time; fallback to call_time if set_time is missing (None)
                    raw_time = gig.get('set_time') if gig.get('set_time') is not None else gig.get('call_time')
                    parsed_time = None
                    if raw_time:
                        try:
                            parsed_time = datetime.datetime.strptime(raw_time, "%H:%M").replace(tzinfo=datetime.timezone.utc)
                            parsed_time = parsed_time + timedelta(hours=localtime.tm_isdst)
                        except (ValueError, TypeError):
                            parsed_time = None

                    gig['date'] = parsed_date  # overwrite with datetime object for downstream usage
                    gig['set_time'] = parsed_time
                    validated_gigs.append(gig)

                validated_gigs.sort(key=lambda gig: gig['date'])
                context['gigs'] = validated_gigs

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
    subheader = blocks.RichTextBlock(required=False)
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
    url = blocks.URLBlock(required=False, help_text="Optional: Link the image to a URL (e.g. merch page)")

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

