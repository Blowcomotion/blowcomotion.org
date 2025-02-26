from django.core.exceptions import ValidationError
from django.db import models
from modelcluster.contrib.taggit import ClusterTaggableManager
from modelcluster.fields import ParentalKey, ParentalManyToManyField
from modelcluster.models import ClusterableModel
from taggit.models import ItemBase, TagBase
from wagtail import blocks
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
    facebook = models.URLField(blank=True, null=True)


class CustomImage(AbstractImage):
    # Add any extra fields to image here

    # To add a caption field:
    caption = models.CharField(max_length=255, blank=True)

    admin_form_fields = Image.admin_form_fields + (
        # Then add the field names here to make them appear in the form:
        'caption',
    )

    @property
    def default_alt_text(self):
        # Force editors to add specific alt text if description is empty.
        # Do not use image title which is typically derived from file name.
        return getattr(self, "description", None)
    

class CustomRendition(AbstractRendition):
    image = models.ForeignKey(CustomImage, on_delete=models.CASCADE, related_name='renditions')

    class Meta:
        unique_together = (
            ('image', 'filter_spec', 'focal_point_key'),
        )


class Chart(models.Model):
    song = ParentalKey("blowcomotion.Song", related_name="charts")
    pdf = models.ForeignKey(
        get_document_model(),
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
    )
    part = models.CharField(max_length=255, blank=True, null=True, help_text=" e.g. '2nd Trombone' If left blank, instrument name will be used.")
    instrument = models.ForeignKey("blowcomotion.Instrument", on_delete=models.CASCADE)
    is_part_uploaded = models.BooleanField(default=False)

    def __str__(self):
        return f"{self.song.title} - {self.instrument.name} - {self.part}"
    

class SongConductor(Orderable):
    song = ParentalKey("blowcomotion.Song", related_name="conductors")
    member = models.ForeignKey("blowcomotion.Member", on_delete=models.CASCADE)


class Song(ClusterableModel, index.Indexed):
    title = models.CharField(max_length=255)
    time_signature = models.CharField(max_length=255, blank=True, null=True)
    key_signature = models.CharField(max_length=255, blank=True, null=True)
    style = models.CharField(max_length=255, blank=True, null=True)
    composer = models.CharField(max_length=255, blank=True, null=True)
    arranger = models.CharField(max_length=255, blank=True, null=True)
    description = models.TextField(blank=True, null=True)
    music_video_url = models.URLField(blank=True, null=True)

    search_fields = [
        index.SearchField("title"),
        index.SearchField("arranger"),
        index.SearchField("composer"),
        index.SearchField("description"),
        index.SearchField("style"),
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
    # gigomatic_url = models.URLField(blank=True, null=True, help_text="URL for the event on Gig-O-Matic")
    location = models.CharField(blank=True, null=True, max_length=255, help_text="e.g. 'Mueller Lake Park, Austin, TX'")
    location_url = models.URLField(blank=True, null=True, help_text="URL for a map of the location")
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
    """
    first_name = models.CharField(max_length=255)
    last_name = models.CharField(max_length=255)
    # instruments = models.ManyToManyField("blowcomotion.Instrument", blank=True)
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

    search_fields = [
        index.SearchField("first_name"),
        index.SearchField("last_name"),
        index.SearchField("bio"),
    ]

    def __str__(self):
        return f"{self.first_name} {self.last_name}"
    

class BasePage(Page):
    class Meta:
        abstract = True

class BlankCanvasPage(BasePage):
    template = 'pages/blank_canvas_page.html'
    body = StreamField([
        ("hero", blowcomotion_blocks.HeroBlock()),
        ("rich_text", blocks.RichTextBlock()),
        ("events", blowcomotion_blocks.EventsBlock()),
    ], block_counts={
        "hero": {"max_num": 1},
    }, blank=True, null=True)

    content_panels = Page.content_panels + [
        "body",
    ]

    def get_context(self, request):
        context = super().get_context(request)
        if self.body:
            context["hero_header"] = self.body[0].block_type == "hero"
        else:
            context["hero_header"] = False
        return context

