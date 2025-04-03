import time
import datetime
from datetime import tzinfo, timedelta

import requests
from django.conf import settings
from django.core.cache import cache
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
    left_column = ColumnContentBlock(required=False)
    middle_column = ColumnContentBlock(required=False)
    right_column = ColumnContentBlock(required=False)

    class Meta:
        template = "blocks/three_column_block.html"


class TwoColumnBlock(ThreeColumnBlock):
    middle_column = None

    class Meta:
        template = "blocks/two_column_block.html"


class FourColumnBlock(ThreeColumnBlock):
    left_column = ColumnContentBlock(required=False)
    middle_left_column = ColumnContentBlock(required=False)
    middle_right_column = ColumnContentBlock(required=False)
    right_column = ColumnContentBlock(required=False)

    class Meta:
        template = "blocks/four_column_block.html"


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


class UpcomingPublicGigs(blocks.StaticBlock):
    def get_context(self, value, parent_context=None):
        context = super().get_context(value, parent_context)
        try:
            context['gigs'] = cache.get('upcoming_public_gigs')
            if context['gigs'] is None:
                r = requests.get(
                        f"{settings.GIGO_API_URL}/gigs",
                        headers={"X-API-KEY": settings.GIGO_API_KEY},
                    )
                context['gigs'] = [gig for gig in r.json()['gigs'] if gig['gig_status'].lower() == 'confirmed' and gig['band'].lower() == 'blowcomotion' and gig["date"] >= datetime.date.today().isoformat() and gig['is_private'] == False and gig["hide_from_calendar"] == False and gig["is_archived"] == False]
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
        admin_text = "This displays a list of confirmed upcoming public Blowco gigs as a list."
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
        label = "Multi Image Banner"
        template = "blocks/multi_image_banner_block.html"