from django.core.exceptions import ValidationError
from django.db import models
from modelcluster.contrib.taggit import ClusterTaggableManager
from modelcluster.fields import ParentalKey, ParentalManyToManyField
from modelcluster.models import ClusterableModel
from taggit.models import ItemBase, TagBase
from wagtail import blocks
from wagtail.admin.panels import FieldPanel, MultipleChooserPanel
from wagtail.contrib.settings.models import BaseSiteSetting, register_setting
from wagtail.documents import get_document_model
from wagtail.fields import StreamField
from wagtail.images.models import AbstractImage, AbstractRendition, Image
from wagtail.models import Orderable, Page
from wagtail.search import index

from blowcomotion import blocks as blowcomotion_blocks


@register_setting
class SiteSettings(BaseSiteSetting):
    logo = models.ForeignKey(
        "blowcomotion.CustomImage",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
    )
    footer_text = models.CharField(
        max_length=255,
        blank=True,
        null=True,
        help_text="Text to display in the footer",
    )
    email = models.EmailField(blank=True, null=True)
    instagram = models.URLField(blank=True, null=True)
    facebook = models.URLField(blank=True, null=True)
    header_menus = StreamField(
        [
            ("menu_item", blowcomotion_blocks.MenuItem()),
        ],
        blank=True,
        null=True,
    )
    contact_form_email_recipients = models.CharField(
        max_length=1024,
        blank=True,
        null=True,
        help_text="Comma-separated list of email addresses to receive contact form submissions",
    )
    venmo_donate_url = models.URLField(
        blank=True,
        null=True,
        help_text="URL to Venmo donation page",
    )


class CustomImage(AbstractImage):
    # Add any extra fields to image here

    # To add a caption field:
    caption = models.CharField(max_length=255, blank=True)

    admin_form_fields = Image.admin_form_fields + (
        # Then add the field names here to make them appear in the form:
        "caption",
    )

    @property
    def default_alt_text(self):
        # Force editors to add specific alt text if description is empty.
        # Do not use image title which is typically derived from file name.
        return getattr(self, "description", None)


class CustomRendition(AbstractRendition):
    image = models.ForeignKey(
        CustomImage, on_delete=models.CASCADE, related_name="renditions"
    )

    class Meta:
        unique_together = (("image", "filter_spec", "focal_point_key"),)


class Chart(models.Model):
    song = ParentalKey("blowcomotion.Song", related_name="charts")
    pdf = models.ForeignKey(
        get_document_model(),
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
    )
    part = models.CharField(
        max_length=255,
        blank=True,
        null=True,
        help_text=" e.g. '2nd Trombone' If left blank, instrument name will be used.",
    )
    instrument = models.ForeignKey("blowcomotion.Instrument", on_delete=models.CASCADE)
    is_part_uploaded = models.BooleanField(default=False)

    def __str__(self):
        return f"{self.song.title} - {self.instrument.name} - {self.part}"


class SongConductor(Orderable):
    song = ParentalKey("blowcomotion.Song", related_name="conductors")
    member = models.ForeignKey("blowcomotion.Member", on_delete=models.CASCADE)


class SongSoloist(Orderable):
    song = ParentalKey("blowcomotion.Song", related_name="soloists")
    member = models.ForeignKey("blowcomotion.Member", on_delete=models.CASCADE)


time_signature_choices = [
    ("4/4", "4/4"),
    ("3/4", "3/4"),
    ("2/4", "2/4"),
    ("2/2", "2/2"),
    ("6/8", "6/8"),
    ("12/8", "12/8"),
    ("5/4", "5/4"),
    ("7/8", "7/8"),
    ("9/8", "9/8"),
]

key_signature_choices = [
    ("C", "C"),
    ("F", "F"),
    ("Bb", "Bb"),
    ("Eb", "Eb"),
    ("Ab", "Ab"),
    ("Db", "Db"),
    ("Gb", "Gb"),
    ("G", "G"),
    ("D", "D"),
    ("A", "A"),
    ("E", "E"),
    ("B", "B"),
    ("F#", "F#"),
    ("C#", "C#"),
]


tonality_choices = [
    ("major", "Major"),
    ("minor", "Minor"),
    ("blues", "Blues"),
]

class Song(ClusterableModel, index.Indexed):
    title = models.CharField(max_length=255)
    time_signature = models.CharField(max_length=255, blank=True, null=True, choices=time_signature_choices)
    key_signature = models.CharField(max_length=255, blank=True, null=True, choices=key_signature_choices)
    tonality = models.CharField(
        max_length=255,
        blank=True,
        null=True,
        choices=tonality_choices,
    )
    tempo = models.IntegerField(
        blank=True,
        null=True,
        help_text="Tempo in BPM (Beats Per Minute)",
    )
    style = models.CharField(max_length=255, blank=True, null=True)
    composer = models.CharField(max_length=255, blank=True, null=True)
    arranger = models.CharField(max_length=255, blank=True, null=True)
    form = models.TextField(blank=True, null=True, help_text="e.g. 'Intro, Verse, Chorus, Bridge, Outro or AABA'")
    description = models.TextField(blank=True, null=True)
    music_video_url = models.URLField(blank=True, null=True)
    source_band = models.CharField(
        max_length=255,
        blank=True,
        null=True,
        help_text="e.g. 'Rebirth Brass Band', 'The Beatles', 'The Rolling Stones', etc.",
    )
    active = models.BooleanField(default=True)

    search_fields = [
        index.SearchField("title"),
        index.SearchField("time_signature"),
        index.SearchField("key_signature"),
        index.SearchField("tonality"),
        index.SearchField("arranger"),
        index.SearchField("composer"),
        index.SearchField("description"),
        index.SearchField("style"),
        index.SearchField("music_video_url"),
        index.SearchField("tempo"),
        index.SearchField("source_band"),
        index.SearchField("active"),
    ]

    def __str__(self):
        return self.title


class EventSetlistSong(Orderable):
    event = ParentalKey("blowcomotion.Event", related_name="setlist")
    song = models.ForeignKey("blowcomotion.Song", on_delete=models.CASCADE)


class Event(ClusterableModel, index.Indexed):
    """
    Model for events

    Attributes:
        title: CharField
        date: DateField
        time: TimeField
        location: CharField
        location_url: URLField
        description: TextField
        setlist: inline panel for songs
    """

    title = models.CharField(max_length=255)
    date = models.DateField(blank=True, null=True)
    time = models.TimeField(blank=True, null=True)
    event_scroller_image = models.ForeignKey(
        "blowcomotion.CustomImage",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
        help_text="Image to be used in the event scroller component",
    )
    location = models.CharField(
        blank=True,
        null=True,
        max_length=255,
        help_text="e.g. 'Mueller Lake Park, Austin, TX'",
    )
    location_url = models.URLField(
        blank=True, null=True, help_text="URL for a map of the location"
    )
    description = models.TextField(blank=True, null=True)

    search_fields = [
        index.SearchField("title"),
        index.SearchField("location"),
        index.SearchField("description"),
    ]

    def __str__(self):
        attributes = []
        if self.date:
            attributes.append(str(self.date))
        if self.location:
            attributes.append(self.location)
        date_location = f" ({', '.join(attributes)})" if attributes else ""
        return f"{self.title}{date_location}"


class Section(ClusterableModel, index.Indexed):
    name = models.CharField(max_length=255)

    search_fields = [
        index.SearchField("name"),
    ]

    def __str__(self):
        return self.name

    class Meta:
        verbose_name = "Section"
        verbose_name_plural = "Sections"


class SectionMember(Orderable):
    section = ParentalKey("blowcomotion.Section", related_name="members")
    member = models.ForeignKey("blowcomotion.Member", on_delete=models.CASCADE)

    panels = [
        "member",
    ]


class SectionInstructor(Orderable):
    section = ParentalKey("blowcomotion.Section", related_name="instructors")
    instructor = models.ForeignKey("blowcomotion.Member", on_delete=models.CASCADE)

    panels = [
        "instructor",
    ]


class Instrument(models.Model, index.Indexed):
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True, null=True)
    section = models.ForeignKey(
        "blowcomotion.Section",
        null=True,
        on_delete=models.SET_NULL,
        related_name="+",
    )
    image = models.ForeignKey(
        "blowcomotion.CustomImage",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
    )

    search_fields = [
        index.SearchField("name"),
        index.SearchField("description"),
    ]

    def __str__(self):
        return self.name

    class Meta:
        verbose_name = "Instrument"
        verbose_name_plural = "Instruments"


class MemberInstrument(Orderable):
    member = ParentalKey("blowcomotion.Member", related_name="instruments")
    instrument = models.ForeignKey("blowcomotion.Instrument", on_delete=models.CASCADE)

    panels = [
        "instrument",
    ]


class Member(ClusterableModel, index.Indexed):
    """
    Model for members of the organization

    Attributes:
        first_name: CharField
        last_name: CharField
        instruments: ManyToManyField
        birthday: DateField
        join_date: DateField
        is_active: BooleanField
        bio: TextField
        image: ForeignKey
        instructor: BooleanField
        board_member: BooleanField
        renting: BooleanField
        last_seen: DateField
        separation_date: DateField
        email: EmailField
        phone: CharField
        address: CharField
        city: CharField
        state: CharField
        zip_code: CharField
        country: CharField
        notes: TextField
    """

    first_name = models.CharField(max_length=255)
    last_name = models.CharField(max_length=255)
    birthday = models.DateField(blank=True, null=True)
    join_date = models.DateField(blank=True, null=True)
    is_active = models.BooleanField(default=True)
    bio = models.TextField(blank=True, null=True)
    image = models.ForeignKey(
        "blowcomotion.CustomImage",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
    )
    instructor = models.BooleanField(default=False)
    board_member = models.BooleanField(default=False)
    renting = models.BooleanField(default=False, help_text="Is the member renting an instrument?")
    last_seen = models.DateField(blank=True, null=True, help_text="This field auto-populates whenever attendance is taken.")
    separation_date = models.DateField(blank=True, null=True, help_text="Date of separation from the organization.")
    email = models.EmailField(blank=True, null=True)
    phone = models.CharField(max_length=255, blank=True, null=True)
    address = models.CharField(max_length=255, blank=True, null=True)
    city = models.CharField(max_length=255, blank=True, null=True)
    state = models.CharField(max_length=255, blank=True, null=True)
    zip_code = models.CharField(max_length=255, blank=True, null=True)
    country = models.CharField(max_length=255, blank=True, null=True)
    notes = models.TextField(blank=True, null=True)
    emergency_contact = models.TextField(
        blank=True,
        null=True,
        help_text="Name and phone number of emergency contact",
    )

    search_fields = [
        index.SearchField("first_name"),
        index.SearchField("last_name"),
        index.SearchField("bio"),
        index.SearchField("email"),
        index.SearchField("phone"),
        index.SearchField("address"),
        index.SearchField("city"),
        index.SearchField("state"),
        index.SearchField("zip_code"),
        index.SearchField("country"),
        index.SearchField("notes"),
    ]

    def __str__(self):
        return f"{self.first_name} {self.last_name}"


class BasePage(Page):
    class Meta:
        abstract = True


class BlankCanvasPage(BasePage):
    template = "pages/blank_canvas_page.html"
    body = StreamField(
        [
            ("accordion_list", blowcomotion_blocks.AccordionListBlock()),
            ("button", blowcomotion_blocks.ButtonBlock()),
            ("column_layout", blowcomotion_blocks.ColumnLayoutBlock()),
            ("contact_form", blowcomotion_blocks.ContactFormBlock()),
            ("countdown", blowcomotion_blocks.CountdownBlock()),
            ("events", blowcomotion_blocks.EventsBlock()),
            ("full_width_image", blowcomotion_blocks.FullWidthImageBlock()),
            ("hero", blowcomotion_blocks.HeroBlock()),
            ("horizontal_rule", blowcomotion_blocks.HorizontalRuleBlock()),
            ("multi_image_banner", blowcomotion_blocks.MultiImageBannerBlock()),
            ("paypal_donate_button", blowcomotion_blocks.PayPalDonateButton()),
            ("quoted_image", blowcomotion_blocks.QuotedImageBlock()),
            ("rich_text", blowcomotion_blocks.AlignableRichtextBlock()),
            ("spacer", blowcomotion_blocks.SpacerBlock()),
            ("upcoming_events", blowcomotion_blocks.UpcomingPublicGigs()),
            ("venmo_donate_button", blowcomotion_blocks.VenmoDonateButton()),
        ],
        block_counts={
            "hero": {"max_num": 1},
        },
        blank=True,
        null=True,
    )

    content_panels = Page.content_panels + [
        "body",
    ]

    def get_context(self, request):
        context = super().get_context(request)
        context["include_countdown_js"] = False
        context["include_form_js"] = True # set to True for the feedback form
        if self.body:
            context["hero_header"] = self.body[0].block_type == "hero"
            context["bottom_countdown"] = self.body[-1].block_type == "countdown"

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
    

class BaseFormSubmission(models.Model):
    """
    Base model for form submissions

    Attributes:
        name: CharField
        email: EmailField
        message: TextField
        date_submitted: DateTimeField
    This is an abstract model that can be inherited by other form submission models.
    """

    name = models.CharField(blank=True, null=True, max_length=255)
    email = models.EmailField(blank=True, null=True, )
    message = models.TextField(blank=True, null=True, )
    date_submitted = models.DateTimeField(auto_now_add=True)

    class Meta:
        abstract = True
    

class ContactFormSubmission(BaseFormSubmission):
    """
        Model for contact form submissions
    """
    def __str__(self):
        return f"Contact Form Submission from {self.name} on {self.date_submitted}"
    

class FeedbackFormSubmission(BaseFormSubmission):
    """
        Model for feedback form submissions
    """
    submitted_from_page = models.CharField(
        blank=True,
        null=True,
        max_length=255,
        help_text="The URL of the page from which the feedback was submitted",
    )

    def __str__(self):
        return f"Feedback Form Submission from {self.name} on {self.date_submitted}"