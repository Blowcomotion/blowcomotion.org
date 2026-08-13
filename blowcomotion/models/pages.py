import datetime

from modelcluster.fields import ParentalKey
from wagtail.admin.panels import FieldPanel, MultipleChooserPanel
from wagtail.fields import StreamField
from wagtail.models import Orderable, Page
from wagtailseo.models import SeoMixin

from django.db import models

from blowcomotion import blocks as blowcomotion_blocks
from blowcomotion.models.core import NotificationBanner


class BasePage(SeoMixin, Page):
    promote_panels = SeoMixin.seo_panels
    class Meta:
        abstract = True


class BlankCanvasPage(BasePage):
    template = "pages/blank_canvas_page.html"
    sticky_content = StreamField(
        [
            ("column_layout", blowcomotion_blocks.ColumnLayoutBlock()),
            ("hero", blowcomotion_blocks.HeroBlock()),
            ("horizontal_rule", blowcomotion_blocks.HorizontalRuleBlock()),
            ("image", blowcomotion_blocks.ImageBlock()),
            ("rich_text", blowcomotion_blocks.AlignableRichtextBlock()),
            ("adjustable_spacer", blowcomotion_blocks.AdjustableSpacerBlock()),
            ("quote", blowcomotion_blocks.QuoteBlock()),
        ],
        blank=True,
        null=True,
        help_text="Content in this field will be fixed at the top of the page, above the main body content. Ideal for hero sections or important announcements that should always be visible."
    )
    body = StreamField(
        [
            ("accordion_list", blowcomotion_blocks.AccordionListBlock()),
            ("auction", blowcomotion_blocks.AuctionBlock()),
            ("booking_form", blowcomotion_blocks.BookingFormBlock(group="Forms")),
            ("button", blowcomotion_blocks.ButtonBlock()),
            ("chart_library", blowcomotion_blocks.ChartLibraryBlock()),
            ("column_layout", blowcomotion_blocks.ColumnLayoutBlock()),
            ("contact_form", blowcomotion_blocks.ContactFormBlock(group="Forms")),
            ("countdown", blowcomotion_blocks.CountdownBlock()),
            ("donate_form", blowcomotion_blocks.DonateFormBlock(group="Forms")),
            ("events", blowcomotion_blocks.EventsBlock()),
            ("full_width_image", blowcomotion_blocks.FullWidthImageBlock()),
            ("hero", blowcomotion_blocks.HeroBlock()),
            ("horizontal_rule", blowcomotion_blocks.HorizontalRuleBlock()),
            ("image", blowcomotion_blocks.ImageBlock()),
            ("image_carousel", blowcomotion_blocks.ImageCarouselBlock()),
            ("join_band_form", blowcomotion_blocks.JoinBandFormBlock(group="Forms")),
            ("member_signup_form", blowcomotion_blocks.MemberSignupFormBlock(group="Forms")),
            ("jukebox", blowcomotion_blocks.JukeBoxBlock()),
            ("multi_image_banner", blowcomotion_blocks.MultiImageBannerBlock()),
            ("patreon_button", blowcomotion_blocks.PatreonButton()),
            ("paypal_donate_button", blowcomotion_blocks.PayPalDonateButton()),
            ("quoted_image", blowcomotion_blocks.QuotedImageBlock()),
            ("rich_text", blowcomotion_blocks.AlignableRichtextBlock()),
            ("adjustable_spacer", blowcomotion_blocks.AdjustableSpacerBlock()),
            ("spacer", blowcomotion_blocks.SpacerBlock()),
            ("square_donate_button", blowcomotion_blocks.SquareDonateButton()),
            ("timeline", blowcomotion_blocks.TimelineBlock()),
            ("upcoming_events", blowcomotion_blocks.UpcomingPublicGigs()),
            ("venmo_donate_button", blowcomotion_blocks.VenmoDonateButton()),
            ("video_feed", blowcomotion_blocks.VideoFeedBlock()),
            ("quote", blowcomotion_blocks.QuoteBlock()),
        ],
        block_counts={
            "hero": {"max_num": 1},
        },
        blank=True,
        null=True,
    )

    content_panels = Page.content_panels + [
        "sticky_content",
        "body",
    ]

    def get_context(self, request):
        context = super().get_context(request)
        context["include_countdown_js"] = False
        context["include_form_js"] = True # set to True for the feedback form

        if self.body:
            has_notification_banner = NotificationBanner.for_request(request).message and (not NotificationBanner.for_request(request).expiration_date or NotificationBanner.for_request(request).expiration_date > datetime.date.today())
            context["hero_header"] = self.body[0].block_type == "hero" and not has_notification_banner
            context["bottom_countdown"] = self.body[-1].block_type == "countdown" and self.body[-1].value.get('countdown_date') and self.body[-1].value.get('countdown_date') > datetime.date.today()

            for block in self.body:
                if block.block_type == "countdown":
                    context["include_countdown_js"] = True
                # if block.block_type == "contact_form":
                #     context["include_form_js"] = True
                if context["include_form_js"] and context["include_countdown_js"]:
                    break
        else:
            context["hero_header"] = False
            context["bottom_countdown"] = False
            context["include_quote_css"] = False

        return context


class WikiIndexPage(BlankCanvasPage):
    """
    Model for wiki index page

    Attributes:
        title: CharField
        body: StreamField
    """

    template = "pages/blank_canvas_page.html"
    subpage_types = ["blowcomotion.WikiPage"]
    max_count = 1

    class Meta:
        verbose_name = "Wiki Index Page"
        verbose_name_plural = "Wiki Index Pages"

    def __str__(self):
        return self.title


class WikiAuthor(Orderable):
    """
    Model for authors of wiki pages

    Attributes:
        page: ParentalKey
        author: ForeignKey
    """

    page = ParentalKey("blowcomotion.WikiPage", related_name="authors")
    author = models.ForeignKey("blowcomotion.Member", on_delete=models.CASCADE)

    panels = [
        FieldPanel("author"),
    ]

    def __str__(self):
        return str(self.author)


class WikiPage(BlankCanvasPage):
    """
    Model for wiki pages

    Attributes:
        title: CharField
        body: StreamField
    """

    template = "pages/blank_canvas_page.html"
    parent_page_types = ["blowcomotion.WikiIndexPage"]
    subpage_types = ["blowcomotion.WikiPage"]

    content_panels = [
        MultipleChooserPanel("authors", chooser_field_name="author"),
    ] + BlankCanvasPage.content_panels


    class Meta:
        verbose_name = "Wiki Page"
        verbose_name_plural = "Wiki Pages"

    def __str__(self):
        return self.title
