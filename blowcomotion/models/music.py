from modelcluster.fields import ParentalKey
from modelcluster.models import ClusterableModel
from wagtail.admin.panels import FieldPanel
from wagtail.documents import get_document_model
from wagtail.models import Orderable
from wagtail.search import index

from django.core.exceptions import ValidationError
from django.db import models


class Chart(models.Model):
    song = ParentalKey("blowcomotion.Song", related_name="charts")
    pdf = models.ForeignKey(
        get_document_model(),
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
    )
    drive_pdf_url = models.URLField(null=True, blank=True)
    part = models.CharField(
        max_length=255,
        blank=True,
        null=True,
        help_text=" e.g. '2nd Trombone' If left blank, instrument name will be used.",
    )
    instrument = models.ForeignKey("blowcomotion.Instrument", on_delete=models.CASCADE)
    drive_file_id = models.CharField(max_length=255, null=True, blank=True, db_index=True)
    drive_modified_time = models.DateTimeField(null=True, blank=True)
    drive_imported_at = models.DateTimeField(null=True, blank=True)

    # Index song and instrument fields for searchability in the chart library
    search_fields = [
        index.SearchField("song__title", partial_match=True, boost=2),
        index.SearchField("instrument__name", partial_match=True),
    ]

    def clean(self):
        if not self.pdf and not self.drive_pdf_url:
            raise ValidationError("A chart must have either a PDF document or a Drive PDF URL.")

    def __str__(self):
        return f"{self.song.title} - {self.instrument.name} - {self.part}" if self.part else f"{self.song.title} - {self.instrument.name}"


class SongConductor(Orderable):
    song = ParentalKey("blowcomotion.Song", related_name="conductors")
    member = models.ForeignKey("blowcomotion.Member", on_delete=models.CASCADE)


class SongSoloist(Orderable):
    song = ParentalKey("blowcomotion.Song", related_name="soloists")
    member = models.ForeignKey("blowcomotion.Member", on_delete=models.CASCADE)


class SongVideo(Orderable):
    """Video URLs for a song (e.g., YouTube links to source performances)."""
    song = ParentalKey("blowcomotion.Song", related_name="videos")
    url = models.URLField(help_text="URL to video (YouTube, Vimeo, etc.)")
    title = models.CharField(
        max_length=255,
        blank=True,
        null=True,
        help_text="Optional title/description for this video (e.g., 'Original by Rebirth Brass Band')"
    )

    panels = [
        FieldPanel("url"),
        FieldPanel("title"),
    ]

    def __str__(self):
        return f"{self.song.title} - {self.title or self.url}"


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
    recording = models.ForeignKey(
        "wagtailmedia.Media",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
    )
    source_band = models.CharField(
        max_length=255,
        blank=True,
        null=True,
        help_text="e.g. 'Rebirth Brass Band', 'The Beatles', 'The Rolling Stones', etc.",
    )
    active = models.BooleanField(default=True)

    search_fields = [
        index.SearchField("title"),
        index.AutocompleteField("title"),
        index.SearchField("time_signature"),
        index.SearchField("key_signature"),
        index.SearchField("tonality"),
        index.SearchField("arranger"),
        index.SearchField("composer"),
        index.SearchField("description"),
        index.SearchField("style"),
        index.SearchField("recording"),
        index.SearchField("form"),
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
