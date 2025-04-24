from wagtail.admin.panels import MultipleChooserPanel
from wagtail.admin.ui.tables import UpdatedAtColumn
from wagtail.snippets.views.snippets import SnippetViewSet, SnippetViewSetGroup


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
        'time_signature',
        'key_signature',
        'style',
        'composer',
        'arranger',
        'description',
        MultipleChooserPanel("conductors", chooser_field_name="member"),
        'music_video_url',
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
    search_fields = ("first_name", "last_name", "bio")
    panels = [
        "first_name",
        "last_name",
        MultipleChooserPanel("instruments", chooser_field_name="instrument"),
        "birthday",
        "join_date",
        "is_active",
        "bio",
        "instructor",
        "board_member",
        "image",
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


class FormsViewSetGroup(SnippetViewSetGroup):
    items = (ContactFormSubmissionViewset, FeedbackFormSubmissionViewset, )
    menu_icon = 'clipboard-list'
    menu_label = 'Form Submissions'
    menu_name = 'forms'