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

from django import forms
from django.db import models
from django.utils.html import format_html


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

    def get_section(self, instance):
        return instance.instrument.section.name if instance.instrument and instance.instrument.section else '-'
    get_section.short_description = 'Section'
    get_section.admin_order_field = 'instrument__section__name'

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
    list_filter = ['active', 'style', 'key_signature', 'time_signature', 'tonality']
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

    def get_key_display(self, instance):
        if instance.key_signature and instance.tonality:
            return f"{instance.key_signature} {instance.tonality.capitalize()}"
        elif instance.key_signature:
            return instance.key_signature
        return '-'
    get_key_display.short_description = 'Key'
    
    def get_active_badge(self, instance):
        if instance.active:
            return format_html('<span class="w-status w-status--primary">Active</span>')
        return format_html('<span class="w-status">Inactive</span>')
    get_active_badge.short_description = 'Active'
    get_active_badge.admin_order_field = 'active'

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
    date = forms.DateField(
        required=False,
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

    def has_setlist(self, instance):
        count = instance.setlist.count()
        if count > 0:
            return format_html('<span class="w-status w-status--primary">{} songs</span>', count)
        return format_html('<span class="w-status">No setlist</span>')
    has_setlist.short_description = 'Setlist'

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


class MemberFilterSet(WagtailFilterSet):
    last_seen = forms.DateField(
        required=False,
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
        '__str__',
        'primary_instrument',
        DateColumn('last_seen', label='Last Seen'),
        'renting',
        DateColumn('join_date', label='Joined'),
        'is_active',
        UpdatedAtColumn()
    ]
    filterset_class = None  # Set in __init__
    list_filter = ["is_active", "primary_instrument", "instructor", "board_member", "renting"]
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
    ]

    def get_name_display(self, instance):
        if instance.preferred_name:
            return format_html('"{}" {} {}', instance.preferred_name, instance.first_name, instance.last_name)
        return f"{instance.first_name} {instance.last_name}"
    get_name_display.short_description = 'Name'
    get_name_display.admin_order_field = 'first_name'
    
    def get_section(self, instance):
        if instance.primary_instrument and instance.primary_instrument.section:
            return instance.primary_instrument.section.name
        return '-'
    get_section.short_description = 'Section'
    get_section.admin_order_field = 'primary_instrument__section__name'
    
    def get_status_badges(self, instance):
        badges = []
        if instance.is_active:
            badges.append('<span class="w-status w-status--primary">Active</span>')
        else:
            badges.append('<span class="w-status">Inactive</span>')
        if instance.instructor:
            badges.append('<span class="w-status w-status--label">Instructor</span>')
        if instance.board_member:
            badges.append('<span class="w-status w-status--label">Board</span>')
        if instance.renting:
            badges.append('<span class="w-status w-status--label">Renting</span>')
        return format_html(' '.join(badges))
    get_status_badges.short_description = 'Status'

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
    date = forms.DateField(
        required=False,
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
    list_filter = ['member', 'played_instrument']
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

    def get_attendee(self, instance):
        if instance.member:
            name = str(instance.member)
            if instance.guest_name:
                return format_html('{} <span class="w-help-text">(Guest: {})</span>', name, instance.guest_name)
            return name
        elif instance.guest_name:
            return format_html('<span class="w-status w-status--label">Guest:</span> {}', instance.guest_name)
        return '-'
    get_attendee.short_description = 'Attendee'
    get_attendee.admin_order_field = 'member__last_name'
    
    def get_section(self, instance):
        if instance.played_instrument and instance.played_instrument.section:
            return instance.played_instrument.section.name
        return '-'
    get_section.short_description = 'Section'
    get_section.admin_order_field = 'played_instrument__section__name'

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
    rental_date = forms.DateField(
        required=False,
        widget=DateRangePickerWidget,
        label='Rental Date Range',
    )
    review_date_6_month = forms.DateField(
        required=False,
        widget=DateRangePickerWidget,
        label='6-Month Review Date Range',
    )
    review_date_12_month = forms.DateField(
        required=False,
        widget=DateRangePickerWidget,
        label='12-Month Review Date Range',
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
        UpdatedAtColumn()
    ]
    filterset_class = None  # Set in __init__
    list_filter = ['status', 'instrument', 'storage_location', 'patreon_active']
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

    def get_serial_short(self, instance):
        if len(instance.serial_number) > 20:
            return instance.serial_number[:20] + '...'
        return instance.serial_number
    get_serial_short.short_description = 'Serial #'
    get_serial_short.admin_order_field = 'serial_number'
    
    def get_status_badge(self, instance):
        status_map = {
            'available': ('Available', 'w-status--primary'),
            'rented': ('Rented', 'w-status--label'),
            'needs_repair': ('Needs Repair', 'w-status--critical'),
            'out_for_repair': ('Out for Repair', 'w-status--warning'),
            'disposed': ('Disposed', ''),
        }
        label, css_class = status_map.get(instance.status, (instance.get_status_display(), ''))
        return format_html('<span class="w-status {}">{}</span>', css_class, label)
    get_status_badge.short_description = 'Status'
    get_status_badge.admin_order_field = 'status'
    
    def get_location(self, instance):
        if instance.member:
            return format_html('<strong>{}</strong>', str(instance.member))
        elif instance.storage_location:
            return format_html('<span class="w-help-text">{}</span>', instance.storage_location.name)
        return '-'
    get_location.short_description = 'Location/Renter'
    
    def get_review_status(self, instance):
        if not instance.review_date_6_month and not instance.review_date_12_month:
            return '-'
        
        from datetime import date
        today = date.today()
        statuses = []
        
        if instance.review_date_6_month:
            if instance.review_date_6_month < today:
                statuses.append('<span class="w-status w-status--critical">6mo overdue</span>')
            else:
                days_until = (instance.review_date_6_month - today).days
                if days_until <= 14:
                    statuses.append(f'<span class="w-status w-status--warning">6mo in {days_until}d</span>')
        
        if instance.review_date_12_month:
            if instance.review_date_12_month < today:
                statuses.append('<span class="w-status w-status--critical">12mo overdue</span>')
            else:
                days_until = (instance.review_date_12_month - today).days
                if days_until <= 30:
                    statuses.append(f'<span class="w-status w-status--warning">12mo in {days_until}d</span>')
        
        return format_html(' '.join(statuses)) if statuses else format_html('<span class="w-status w-status--primary">✓</span>')
    get_review_status.short_description = 'Review Status'
    
    def get_patreon_badge(self, instance):
        if instance.patreon_active and instance.patreon_amount:
            return format_html('<span class="w-status w-status--primary">${}/mo</span>', instance.patreon_amount)
        elif instance.patreon_active:
            return format_html('<span class="w-status w-status--primary">Active</span>')
        return '-'
    get_patreon_badge.short_description = 'Patreon'

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


class BandViewSetGroup(SnippetViewSetGroup):
    items = (EventViewSet, SectionViewSet, InstrumentViewSet, MemberViewSet, SongViewSet, ChartViewSet, AttendanceRecordViewSet, LibraryInstrumentViewSet, InstrumentHistoryLogViewSet, InstrumentStorageLocationViewSet)
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