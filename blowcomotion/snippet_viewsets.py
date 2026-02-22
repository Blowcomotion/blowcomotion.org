from wagtail.admin.panels import (
    FieldPanel,
    FieldRowPanel,
    InlinePanel,
    MultiFieldPanel,
    MultipleChooserPanel,
)
from wagtail.admin.ui.tables import DateColumn, UpdatedAtColumn
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
    menu_icon = 'music'
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
    icon = 'french-horn'
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
    list_display = ["first_name", "last_name", "last_seen", UpdatedAtColumn()]
    list_filter = ["primary_instrument", "instructor", "board_member", "is_active", "renting"]
    # search_fields = ("first_name", "last_name", "preferred_name", "gigomatic_username", "bio")
    panels = [
        "first_name",
        "last_name",
        "preferred_name",
        "gigomatic_username",
        "gigomatic_id",
        "primary_instrument",
        MultipleChooserPanel("additional_instruments", chooser_field_name="instrument", 
                           help_text="Select any additional instruments this member plays"),
        "birth_month",
        "birth_day",
        "birth_year",
        "join_date",
        "is_active",
        "bio",
        "inspired_by",
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


class AttendanceRecordViewSet(SnippetViewSet):
    model = None
    menu_label = 'Attendance Records'
    menu_name = 'attendance_records'
    menu_icon = 'check'
    list_display = ['member', 'played_instrument', 'guest_name', DateColumn('date', label='Date'), 'notes', UpdatedAtColumn()]
    list_filter = ['date', 'member', 'played_instrument']
    search_fields = ('member__first_name', 'member__last_name', 'guest_name', 'notes', 'played_instrument__name')
    panels = [
        FieldRowPanel([
            'date',
            'member',
            'played_instrument',
        ], heading="Attendance Details"),
        'guest_name',
        'notes',
    ]
    ordering = ['-date', 'member__first_name']

    def __init__(self, *args, **kwargs):
        from .models import AttendanceRecord
        self.model = AttendanceRecord
        super().__init__(*args, **kwargs)


class LibraryInstrumentViewSet(SnippetViewSet):
    model = None
    menu_label = 'Library Instruments'
    menu_name = 'library_instruments'
    menu_icon = 'french-horn'
    list_display = ['instrument', 'serial_number', 'status', 'member', 'rental_date', 'review_date_6_month', 'review_date_12_month', UpdatedAtColumn()]
    list_filter = ['status', 'instrument', 'patreon_active', 'live']
    search_fields = ('instrument__name', 'serial_number', 'member__first_name', 'member__last_name', 'comments')
    panels = [
        MultiFieldPanel([
            'instrument',
            'status',
            'serial_number',
            'member',
        ], heading="Basic Information"),
        MultiFieldPanel([
            FieldRowPanel([
                'rental_date',
                'agreement_signed_date',
            ]),
            FieldRowPanel([
                'review_date_6_month',
                'review_date_12_month',
            ], heading="Review Cycle"),
        ], heading="Rental Dates"),
        MultiFieldPanel([
            'patreon_active',
            'patreon_amount',
        ], heading="Patreon Support"),
        FieldPanel('comments'),
        InlinePanel('photos', label="Photos"),
        InlinePanel('rental_documents', label="Rental Documents"),
        InlinePanel('history_logs', label="History Log", help_text="Event history for this instrument"),
    ]
    ordering = ['instrument__name', 'serial_number']

    def __init__(self, *args, **kwargs):
        from .models import LibraryInstrument
        self.model = LibraryInstrument
        super().__init__(*args, **kwargs)


class InstrumentHistoryLogViewSet(SnippetViewSet):
    model = None
    menu_label = 'Instrument History Logs'
    menu_name = 'instrument_history_logs'
    menu_icon = 'list-ul'
    list_display = ['library_instrument', DateColumn('event_date', label='Event Date'), 'event_category', 'notes', 'user']
    list_filter = ['event_category', 'event_date']
    search_fields = ('library_instrument__instrument__name', 'library_instrument__serial_number', 'notes')
    panels = [
        'library_instrument',
        FieldRowPanel([
            'event_date',
            'event_category',
        ]),
        'notes',
        'user',
    ]
    ordering = ['-event_date', '-created_at']

    def __init__(self, *args, **kwargs):
        from .models import InstrumentHistoryLog
        self.model = InstrumentHistoryLog
        super().__init__(*args, **kwargs)


class BandViewSetGroup(SnippetViewSetGroup):
    items = (EventViewSet, SectionViewSet, InstrumentViewSet, MemberViewSet, SongViewSet, ChartViewSet, AttendanceRecordViewSet, LibraryInstrumentViewSet, InstrumentHistoryLogViewSet)
    menu_icon = 'drum'
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