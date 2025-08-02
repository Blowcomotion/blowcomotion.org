from wagtail.admin.panels import FieldRowPanel, MultipleChooserPanel
from wagtail.admin.ui.tables import UpdatedAtColumn
from wagtail.snippets.views.snippets import SnippetViewSet, SnippetViewSetGroup

from wagtailmedia.edit_handlers import MediaChooserPanel


class ChartViewSet(SnippetViewSet):
    model = None
    menu_label = 'Charts'
    menu_name = 'charts'
    menu_icon = 'doc-full-inverse'
    list_display = ['instrument', 'song', UpdatedAtColumn()]
    panels = [
        'song',
        'pdf',
        'part',
        'instrument',
    ]

    def __init__(self, *args, **kwargs):
        from .models import Chart  # Lazy import inside the method
        self.model = Chart
        super().__init__(*args, **kwargs)


class SongViewSet(SnippetViewSet):
    model = None
    menu_label = 'Songs'
    menu_name = 'songs'
    menu_icon = 'pick'
    list_display = ['title', 'composer', 'style', UpdatedAtColumn()]
    panels = [
        'title',
        FieldRowPanel(
            [
                'music_video_url',
                MediaChooserPanel('recording', help_text="Select the media file for this song.", media_type='audio'),
            ],
            heading="Media",
            help_text="Select the music video and recording for this song.",
        ),
        'time_signature',
        FieldRowPanel(
            [
                'key_signature',
                'tonality',
            ],
            heading="Key Signature and Tonality",
            help_text="Select the key signature and tonality of the song.",
        ),
        'tempo',
        'style',
        'composer',
        'arranger',
        'form',
        'description',
        MultipleChooserPanel("conductors", chooser_field_name="member", help_text="Select the members that usually conduct this song."),
        MultipleChooserPanel("soloists", chooser_field_name="member", help_text="If this song has soloists, select the members that usually solo on this song."),
        'source_band',
        'active',
    ]

    def __init__(self, *args, **kwargs):
        from .models import Song
        self.model = Song
        super().__init__(*args, **kwargs)


class EventViewSet(SnippetViewSet):
    model = None
    menu_label = 'Events'
    menu_name = 'events'
    menu_icon = 'date'
    list_display = [
        'title',
        'date',
        'time',
        'location',
        UpdatedAtColumn(),
    ]
    panels = [
        'title',
        'date',
        'time',
        'description',
        'location',
        'location_url',
        'setlist',
        'event_scroller_image',
    ]

    def __init__(self, *args, **kwargs):
        from .models import Event
        self.model = Event
        super().__init__(*args, **kwargs)


class SectionViewSet(SnippetViewSet):
    model = None
    menu_label = 'Sections'
    menu_name = 'sections'
    icon = 'folder-inverse'
    list_display = ["name", UpdatedAtColumn()]
    search_fields = ("name",)
    panels = [
        "name",
        MultipleChooserPanel("instructors", chooser_field_name="instructor"),
        MultipleChooserPanel("members", chooser_field_name="member"),
    ]

    def __init__(self, *args, **kwargs):
        from .models import Section
        self.model = Section
        super().__init__(*args, **kwargs)


class InstrumentViewSet(SnippetViewSet):
    model = None
    menu_label = 'Instruments'
    menu_name = 'instruments'
    icon = 'pick'
    list_display = ["name", "section", UpdatedAtColumn()]
    list_filter = ["section"]
    search_fields = ("name", "description")
    panels = [
        "name",
        "section",
        "description",
        "image",
    ]

    def __init__(self, *args, **kwargs):
        from .models import Instrument
        self.model = Instrument
        super().__init__(*args, **kwargs)


class MemberViewSet(SnippetViewSet):
    model = None
    menu_label = 'Members'
    menu_name = 'members'
    menu_icon = 'group'
    list_display = ["first_name", "last_name", "instructor", "board_member", UpdatedAtColumn()]
    list_filter = ["instruments", "instructor", "board_member"]
    search_fields = ("first_name", "last_name", "preferred_name", "bio")
    panels = [
        "first_name",
        "last_name",
        "preferred_name",
        MultipleChooserPanel("instruments", chooser_field_name="instrument"),
        "birth_month",
        "birth_day",
        "birth_year",
        "join_date",
        "is_active",
        "bio",
        "instructor",
        "board_member",
        "image",
        "renting",
        "last_seen",
        "separation_date",
        "email",
        "phone",
        "address",
        "city",
        "state",
        "zip_code",
        "country",
        "notes",
        "emergency_contact",
    ]

    def __init__(self, *args, **kwargs):
        from .models import Member
        self.model = Member
        super().__init__(*args, **kwargs)


class BandViewSetGroup(SnippetViewSetGroup):
    items = (EventViewSet, SectionViewSet, InstrumentViewSet, MemberViewSet, SongViewSet, ChartViewSet)
    menu_icon = 'folder-inverse'
    menu_label = 'Band Stuff'
    menu_name = 'band'


class ContactFormSubmissionViewset(SnippetViewSet):
    model = None
    menu_label = 'Contact Form'
    menu_name = 'contact_form'
    menu_icon = 'clipboard-list'
    list_display = ["name", "email", "message", "date_submitted"]
    search_fields = ("name", "email", "message")
    panels = [
        "name",
        "email",
        "message",
        "newsletter_opt_in",
    ]

    def __init__(self, *args, **kwargs):
        from .models import ContactFormSubmission
        self.model = ContactFormSubmission
        super().__init__(*args, **kwargs)


class FeedbackFormSubmissionViewset(SnippetViewSet):
    model = None
    menu_label = 'Feedback Form'
    menu_name = 'feedback_form'
    menu_icon = 'clipboard-list'
    list_display = ["name", "email", "message", "submitted_from_page", "date_submitted"]
    search_fields = ("name", "email", "message", "submitted_from_page")
    panels = [
        "name",
        "email",
        "message",
        "submitted_from_page",
    ]

    def __init__(self, *args, **kwargs):
        from .models import FeedbackFormSubmission
        self.model = FeedbackFormSubmission
        super().__init__(*args, **kwargs)


class JoinBandFormSubmissionViewset(SnippetViewSet):
    model = None
    menu_label = 'Join Band Form'
    menu_name = 'join_band_form'
    menu_icon = 'group'
    list_display = ["name", "email", "instrument", "instrument_rental", "date_submitted"]
    search_fields = ("name", "email", "instrument", "message")
    panels = [
        "name",
        "email",
        "instrument",
        "instrument_rental",
        "message",
        "newsletter_opt_in",
    ]

    def __init__(self, *args, **kwargs):
        from .models import JoinBandFormSubmission
        self.model = JoinBandFormSubmission
        super().__init__(*args, **kwargs)


class BookingFormSubmissionViewset(SnippetViewSet):
    model = None
    menu_label = 'Booking Form'
    menu_name = 'booking_form'
    menu_icon = 'calendar-alt'
    list_display = ["name", "email", "message", "date_submitted"]
    search_fields = ("name", "email", "message")
    panels = [
        "name",
        "email",
        "message",
        "newsletter_opt_in",
    ]

    def __init__(self, *args, **kwargs):
        from .models import BookingFormSubmission
        self.model = BookingFormSubmission
        super().__init__(*args, **kwargs)


class DonateFormSubmissionViewset(SnippetViewSet):
    model = None
    menu_label = 'Donate Form'
    menu_name = 'donate_form'
    menu_icon = 'bi-currency-dollar'
    list_display = ["name", "email", "message", "date_submitted"]
    search_fields = ("name", "email", "message")
    panels = [
        "name",
        "email",
        "message",
        "newsletter_opt_in",
    ]

    def __init__(self, *args, **kwargs):
        from .models import DonateFormSubmission
        self.model = DonateFormSubmission
        super().__init__(*args, **kwargs)


class FormsViewSetGroup(SnippetViewSetGroup):
    items = (ContactFormSubmissionViewset, FeedbackFormSubmissionViewset, JoinBandFormSubmissionViewset, BookingFormSubmissionViewset, DonateFormSubmissionViewset, )
    menu_icon = 'clipboard-list'
    menu_label = 'Form Submissions'
    menu_name = 'forms'