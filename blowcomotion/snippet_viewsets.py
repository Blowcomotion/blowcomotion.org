import django_filters
from wagtail.admin.filters import DateRangePickerWidget, WagtailFilterSet
from wagtail.admin.panels import (
    FieldPanel,
    FieldRowPanel,
    InlinePanel,
    MultiFieldPanel,
    MultipleChooserPanel,
)
from wagtail.admin.ui.tables import Column, DateColumn, UpdatedAtColumn
from wagtail.snippets.views.snippets import SnippetViewSet, SnippetViewSetGroup
from wagtailmedia.edit_handlers import MediaChooserPanel


# Custom FilterSets
class ChartFilterSet(WagtailFilterSet):
    class Meta:
        model = None
        fields = ['instrument', 'song']


class ChartViewSet(SnippetViewSet):
    model = None
    menu_label = 'Charts'
    menu_name = 'charts'
    menu_icon = 'doc-full-inverse'
    search_fields = ['song__title', 'instrument__name', 'part']
    list_display = [
        'song',
        'pdf',
        'instrument',
        Column('part', label='Part'),
        UpdatedAtColumn()
    ]
    filterset_class = None  # Set in __init__
    ordering = ['song__title', 'instrument__name']
    panels = [
        'song',
        'pdf',
        'part',
        'instrument',
    ]

    def __init__(self, *args, **kwargs):
        from .models import Chart

        # Create a dynamic FilterSet class with the model set
        class ChartFilterSetWithModel(ChartFilterSet):
            class Meta(ChartFilterSet.Meta):
                model = Chart
        
        self.model = Chart
        self.filterset_class = ChartFilterSetWithModel
        super().__init__(*args, **kwargs)


class SongFilterSet(WagtailFilterSet):
    class Meta:
        model = None
        fields = {
            'active': ['exact'],
            'style': ['exact'],
            'key_signature': ['exact'],
            'time_signature': ['exact'],
            'tonality': ['exact'],
        }


class SongViewSet(SnippetViewSet):
    model = None
    menu_label = 'Songs'
    menu_name = 'songs'
    menu_icon = 'music'
    search_fields = ['title', 'composer', 'arranger', 'style', 'source_band']
    list_display = [
        'title',
        'key_signature',
        'time_signature',
        Column('tempo', label='Tempo (BPM)'),
        'style',
        'composer',
        'active',
        UpdatedAtColumn()
    ]
    filterset_class = None  # Set in __init__
    ordering = ['title']
    panels = [
        'title',
        MediaChooserPanel('recording', help_text="Select the audio recording for this song.", media_type='audio'),
        InlinePanel('videos', label="Source Videos", help_text="Add YouTube or other video links for reference performances."),
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

        # Create a dynamic FilterSet class with the model set
        class SongFilterSetWithModel(SongFilterSet):
            class Meta(SongFilterSet.Meta):
                model = Song
        
        self.model = Song
        self.filterset_class = SongFilterSetWithModel
        super().__init__(*args, **kwargs)


class EventFilterSet(WagtailFilterSet):
    date = django_filters.DateFromToRangeFilter(
        widget=DateRangePickerWidget,
        label='Date Range',
    )
    
    class Meta:
        model = None
        fields = ['date', 'location']


class EventViewSet(SnippetViewSet):
    model = None
    menu_label = 'Events'
    menu_name = 'events'
    menu_icon = 'date'
    search_fields = ['title', 'location', 'description']
    list_display = [
        'title',
        DateColumn('date', label='Date'),
        'time',
        'location',
        UpdatedAtColumn(),
    ]
    filterset_class = None  # Set in __init__
    ordering = ['-date', 'time']
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

        # Create a dynamic FilterSet class with the model set
        class EventFilterSetWithModel(EventFilterSet):
            class Meta(EventFilterSet.Meta):
                model = Event
        
        self.model = Event
        self.filterset_class = EventFilterSetWithModel
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
    list_display = ["name", "section", "hide_from_rental", "hide_from_member_forms", UpdatedAtColumn()]
    list_filter = ["section"]
    search_fields = ("name", "description")
    panels = [
        "name",
        "section",
        "description",
        "image",
        "hide_from_rental",
        "hide_from_member_forms",
    ]

    def __init__(self, *args, **kwargs):
        from .models import Instrument
        self.model = Instrument
        super().__init__(*args, **kwargs)


class MemberFilterSet(WagtailFilterSet):
    last_seen = django_filters.DateFromToRangeFilter(
        widget=DateRangePickerWidget,
        label='Last Seen Date Range',
    )
    
    class Meta:
        model = None
        fields = {
            'is_active': ['exact'],
            'primary_instrument': ['exact'],
            'instructor': ['exact'],
            'board_member': ['exact'],
            'renting': ['exact'],
        }


class MemberViewSet(SnippetViewSet):
    model = None
    menu_label = 'Members'
    menu_name = 'members'
    menu_icon = 'group'
    search_fields = ("first_name", "last_name", "preferred_name", "gigomatic_username", "email")
    list_display = [
        'display_name',
        Column('primary_instrument', label='Instrument', sort_key='primary_instrument__name'),
        DateColumn('last_seen', label='Last Seen'),
        'renting',
        DateColumn('join_date', label='Joined'),
        'is_active',
        UpdatedAtColumn()
    ]
    filterset_class = None  # Set in __init__
    ordering = ['last_name', 'first_name']
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
        "shirt_size",
        "dietary_preferences",
        "dietary_other",
        "has_allergies",
        "allergens",
        "allergens_other",
        "has_epipen",
        "allergy_details",
        "medical_notes",
    ]

    def __init__(self, *args, **kwargs):
        from .models import Member

        # Create a dynamic FilterSet class with the model set
        class MemberFilterSetWithModel(MemberFilterSet):
            class Meta(MemberFilterSet.Meta):
                model = Member
        
        self.model = Member
        self.filterset_class = MemberFilterSetWithModel
        super().__init__(*args, **kwargs)


class AttendanceRecordFilterSet(WagtailFilterSet):
    date = django_filters.DateFromToRangeFilter(
        widget=DateRangePickerWidget,
        label='Date Range',
    )
    
    class Meta:
        model = None
        fields = {
            'member': ['exact'],
            'played_instrument': ['exact'],
        }


class AttendanceRecordViewSet(SnippetViewSet):
    model = None
    menu_label = 'Attendance Records'
    menu_name = 'attendance_records'
    menu_icon = 'check'
    search_fields = ('member__first_name', 'member__last_name', 'guest_name', 'notes', 'played_instrument__name')
    list_display = [
        '__str__',
        DateColumn('date', label='Date'),
        'member',
        'played_instrument',
        'guest_name',
        'notes',
        UpdatedAtColumn()
    ]
    filterset_class = None  # Set in __init__
    ordering = ['-date', 'member__last_name']
    panels = [
        FieldRowPanel([
            'date',
            'member',
            'played_instrument',
        ], heading="Attendance Details"),
        'guest_name',
        'notes',
    ]

    def __init__(self, *args, **kwargs):
        from .models import AttendanceRecord

        # Create a dynamic FilterSet class with the model set
        class AttendanceRecordFilterSetWithModel(AttendanceRecordFilterSet):
            class Meta(AttendanceRecordFilterSet.Meta):
                model = AttendanceRecord
        
        self.model = AttendanceRecord
        self.filterset_class = AttendanceRecordFilterSetWithModel
        super().__init__(*args, **kwargs)


class LibraryInstrumentFilterSet(WagtailFilterSet):
    rental_date = django_filters.DateFromToRangeFilter(
        widget=DateRangePickerWidget,
        label='Rental Date Range',
    )
    
    class Meta:
        model = None
        fields = {
            'status': ['exact'],
            'instrument': ['exact'],
            'member': ['exact'],
            'storage_location': ['exact'],
            'patreon_active': ['exact'],
        }


class LibraryInstrumentViewSet(SnippetViewSet):
    model = None
    menu_label = 'Library Instruments'
    menu_name = 'library_instruments'
    menu_icon = 'french-horn'
    search_fields = ('instrument__name', 'serial_number', 'member__first_name', 'member__last_name', 'comments')
    list_display = [
        'instrument',
        'serial_number',
        'status',
        'member',
        'storage_location',
        DateColumn('rental_date', label='Rental Date'),
        'patreon_active',
        'hide_from_rental',
        'hide_from_member_forms',
        UpdatedAtColumn()
    ]
    filterset_class = None  # Set in __init__
    ordering = ['instrument__name', 'serial_number']
    panels = [
        MultiFieldPanel([
            'instrument',
            'status',
            'serial_number',
            'member',
            'storage_location',
        ], heading="Basic Information"),
        MultiFieldPanel([
            'rental_date',
        ], heading="Rental Date"),
        MultiFieldPanel([
            FieldRowPanel([
                'acquisition_cost',
                'current_value',
            ]),
            'replacement_cost',
        ], heading="Cost Information"),
        MultiFieldPanel([
            'patreon_active',
            'patreon_amount',
        ], heading="Patreon Support"),
        MultiFieldPanel([
            'hide_from_rental',
            'hide_from_member_forms',
        ], heading="Visibility"),
        FieldPanel('comments'),
        InlinePanel('photos', label="Photos"),
        InlinePanel('history_logs', label="History Log", help_text="Event history for this instrument"),
    ]

    def __init__(self, *args, **kwargs):
        from .models import LibraryInstrument

        # Create a dynamic FilterSet class with the model set
        class LibraryInstrumentFilterSetWithModel(LibraryInstrumentFilterSet):
            class Meta(LibraryInstrumentFilterSet.Meta):
                model = LibraryInstrument
        
        self.model = LibraryInstrument
        self.filterset_class = LibraryInstrumentFilterSetWithModel
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


class InstrumentStorageLocationViewSet(SnippetViewSet):
    model = None
    menu_label = 'Storage Locations'
    menu_name = 'storage_locations'
    menu_icon = 'home'
    list_display = ['name', 'city', 'state', 'phone_number', UpdatedAtColumn()]
    list_filter = ['city', 'state']
    search_fields = ('name', 'description', 'street_address', 'city', 'state', 'notes')
    panels = [
        'name',
        'description',
        MultiFieldPanel([
            'street_address',
            FieldRowPanel([
                'city',
                'state',
                'zip_code',
            ]),
            'country',
        ], heading="Address"),
        MultiFieldPanel([
            'phone_number',
            'email',
        ], heading="Contact Information"),
        'notes',
    ]
    ordering = ['name']

    def __init__(self, *args, **kwargs):
        from .models import InstrumentStorageLocation
        self.model = InstrumentStorageLocation
        super().__init__(*args, **kwargs)


class CachedGigFilterSet(WagtailFilterSet):
    date = django_filters.DateFromToRangeFilter(
        widget=DateRangePickerWidget,
        label='Date Range',
    )
    
    class Meta:
        model = None
        fields = {
            'gig_status': ['exact'],
            'band': ['exact'],
        }


class CachedGigViewSet(SnippetViewSet):
    model = None
    menu_label = 'Cached Gigs'
    menu_name = 'cached_gigs'
    menu_icon = 'date'
    search_fields = ('title', 'address', 'band')
    list_display = [
        'title',
        'date',
        'time',
        'gig_status',
        'band',
        'address',
        DateColumn('last_synced', label='Last Synced'),
    ]
    filterset_class = None  # Set in __init__
    ordering = ['-date', 'time']
    list_filter = ['gig_status', 'band']
    panels = [
        FieldRowPanel([
            FieldPanel('gig_id', read_only=True),
            FieldPanel('title'),
        ], heading="Gig Info"),
        FieldRowPanel([
            FieldPanel('date'),
            FieldPanel('time'),
        ], heading="Date and Time"),
        FieldPanel('address'),
        FieldRowPanel([
            FieldPanel('gig_status'),
            FieldPanel('band'),
        ], heading="Status"),
        FieldPanel('last_synced', read_only=True),
    ]

    def __init__(self, *args, **kwargs):
        from .models import CachedGig

        # Create a dynamic FilterSet class with the model set
        class CachedGigFilterSetWithModel(CachedGigFilterSet):
            class Meta(CachedGigFilterSet.Meta):
                model = CachedGig
        
        self.model = CachedGig
        self.filterset_class = CachedGigFilterSetWithModel
        super().__init__(*args, **kwargs)


class EquipmentFilterSet(WagtailFilterSet):
    class Meta:
        model = None
        fields = {
            'status': ['exact'],
            'storage_location': ['exact'],
        }


class EquipmentViewSet(SnippetViewSet):
    model = None
    menu_label = 'Equipment'
    menu_name = 'equipment'
    menu_icon = 'folder-open-inverse'
    search_fields = ('name', 'serial_number', 'notes')
    list_display = ['name', 'quantity', 'status', 'storage_location', UpdatedAtColumn()]
    filterset_class = None
    ordering = ['name']
    panels = [
        'name',
        'serial_number',
        FieldRowPanel(['quantity', 'status']),
        'storage_location',
        FieldRowPanel(['acquisition_cost', 'current_value', 'replacement_cost']),
        'notes',
        InlinePanel('photos', label="Photos"),
    ]

    def __init__(self, *args, **kwargs):
        from .models import Equipment

        class EquipmentFilterSetWithModel(EquipmentFilterSet):
            class Meta(EquipmentFilterSet.Meta):
                model = Equipment

        self.model = Equipment
        self.filterset_class = EquipmentFilterSetWithModel
        super().__init__(*args, **kwargs)


class BandViewSetGroup(SnippetViewSetGroup):
    items = (EventViewSet, SectionViewSet, InstrumentViewSet, MemberViewSet, SongViewSet, ChartViewSet, AttendanceRecordViewSet, LibraryInstrumentViewSet, InstrumentHistoryLogViewSet, InstrumentStorageLocationViewSet, EquipmentViewSet)
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
    list_display = ["name", "email", "event_date", "event_location", "date_submitted"]
    search_fields = ("name", "email", "event_location", "event_details", "message")
    panels = [
        "name",
        "email",
        "event_date",
        "event_time",
        "event_location",
        "duration",
        "expected_guests",
        "budget",
        "event_details",
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


class InstrumentRentalRequestSubmissionViewset(SnippetViewSet):
    model = None
    menu_label = "Instrument Rental Requests"
    menu_name = "instrument_rental_requests"
    menu_icon = "bi-music-note-beamed"
    list_display = ["name", "email", "instrument", "status", "is_waitlist", "date_submitted"]
    search_fields = ("name", "email")
    panels = [
        "member",
        "name",
        "email",
        "phone",
        "address",
        "instrument",
        "second_choice",
        "third_choice",
        "is_waitlist",
        "status",
        "admin_message",
        "assigned_unit",
        "message",
        "policy_acknowledged",
    ]

    def __init__(self, *args, **kwargs):
        from .models import InstrumentRentalRequestSubmission
        self.model = InstrumentRentalRequestSubmission
        super().__init__(*args, **kwargs)


class FormsViewSetGroup(SnippetViewSetGroup):
    items = (ContactFormSubmissionViewset, FeedbackFormSubmissionViewset, JoinBandFormSubmissionViewset, BookingFormSubmissionViewset, DonateFormSubmissionViewset, InstrumentRentalRequestSubmissionViewset, )
    menu_icon = 'clipboard-list'
    menu_label = 'Form Submissions'
    menu_name = 'forms'


class SyncViewSetGroup(SnippetViewSetGroup):
    items = (CachedGigViewSet,)
    menu_icon = 'music'
    menu_label = 'Gigo Gigs'
    menu_name = 'sync'
