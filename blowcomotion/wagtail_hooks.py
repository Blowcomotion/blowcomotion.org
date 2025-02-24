from django import forms
from wagtail import hooks
from wagtail.admin.panels import FieldPanel, InlinePanel, MultipleChooserPanel
from wagtail.admin.ui.tables import TitleColumn, UpdatedAtColumn
from wagtail.admin.views.generic.chooser import (BaseChooseView,
                                                 ChooseResultsViewMixin,
                                                 ChooseViewMixin,
                                                 CreationFormMixin)
from wagtail.admin.viewsets.chooser import ChooserViewSet
from wagtail.snippets.models import register_snippet
from wagtail.snippets.views.snippets import SnippetViewSet, SnippetViewSetGroup

from .models import Event, Instrument, Member, Section, Song, Chart


class ChartChooserViewset(ChooserViewSet):
    model = Chart
    choose_one_text = "Choose a chart"
    choose_another_text = "Choose another chart"
    edit_item_text = "Edit chart"
    menu_icon = "doc-full-inverse"
    form_fields = [
        "song",
        "pdf",
        "instrument",
        "is_part_uploaded",
        "part",
    ]

chart_chooser_viewset = ChartChooserViewset("chart_chooser")


class ChartViewSet(SnippetViewSet):
    model = Chart
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


class SongChooserViewset(ChooserViewSet):
    model = Song
    choose_one_text = "Choose a song"
    choose_another_text = "Choose another song"
    edit_item_text = "Edit song"
    form_fields = [
        "title",
        "time_signature",
        "key_signature",
        "style",
        "composer",
        "arranger",
        "description",
        "music_video_url",
    ]

song_chooser_viewset = SongChooserViewset("song_chooser")

class SongViewSet(SnippetViewSet):
    model = Song
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


class EventChooserViewset(ChooserViewSet):
    model = Event
    choose_one_text = "Choose an event"
    choose_another_text = "Choose another event"
    edit_item_text = "Edit event"
    form_fields = [
        "title",
        "date",
        "location",
        "location_url",
        "description",
        "setlist",
    ]

event_chooser_viewset = EventChooserViewset("event_chooser")


class EventViewSet(SnippetViewSet):
    model = Event
    menu_label = 'Events'
    menu_name = 'events'
    menu_icon = 'date'
    list_display = ['title', 'date', 'location', UpdatedAtColumn()]
    panels = [
        'title',
        'date',
        'time',
        'location',
        'location_url',
        'description',
        'setlist',
    ]


class SectionChooserViewset(ChooserViewSet):
    model = "blowcomotion.Section"
    choose_one_text = "Choose a section"
    choose_another_text = "Choose another section"
    edit_item_text = "Edit section"
    form_fields = [
        "name",
        "instructors",
        "members",
    ]


section_chooser_viewset = SectionChooserViewset("section_chooser")

class InstrumentChooserViewset(ChooserViewSet):
    model = "blowcomotion.Instrument"
    choose_one_text = "Choose an instrument"
    choose_another_text = "Choose another instrument"
    edit_item_text = "Edit instrument"
    form_fields = [
        "name",
        "description",
        "section",
    ]

instrument_chooser_viewset = InstrumentChooserViewset("instrument_chooser")

class BaseMemberChooseView(BaseChooseView):
    @property
    def columns(self):
        return [
            TitleColumn("first_name", label="First name"),
            TitleColumn("last_name", label="Last name"),
            TitleColumn("instructor", label="Instructor"),
            TitleColumn("board_member", label="Board member"),
        ]

class MemberChooseView(ChooseViewMixin, CreationFormMixin,  BaseMemberChooseView):
    pass

class MemberChooseResultsView(
    ChooseResultsViewMixin, CreationFormMixin, BaseMemberChooseView
):
    pass


class MemberChooserViewset(ChooserViewSet):
    icon = "user"
    model = "blowcomotion.Member"
    choose_view_class = MemberChooseView
    choose_results_view_class = MemberChooseResultsView
    choose_one_text = "Choose a member"
    choose_another_text = "Choose another member"
    edit_item_text = "Edit member"
    search_tab_label = "Search Members"

    form_fields = [
        "first_name",
        "last_name",
        "birthday",
        "join_date",
        "is_active",
        "bio",
        "instructor",
        "board_member",
        "image",
    ]

member_chooser_viewset = MemberChooserViewset("member_chooser")


class SectionViewSet(SnippetViewSet):
    model = Section
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


class InstrumentViewSet(SnippetViewSet):
    model = Instrument
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


class MemberViewSet(SnippetViewSet):
    model = Member
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


class BandViewSetGroup(SnippetViewSetGroup):
    items = (EventViewSet, SectionViewSet, InstrumentViewSet, MemberViewSet, SongViewSet, ChartViewSet)
    menu_icon = 'folder-inverse'
    menu_label = 'Band Stuff'
    menu_name = 'band'

register_snippet(BandViewSetGroup)

@hooks.register('register_admin_viewset')
def register_viewset():
    return member_chooser_viewset, instrument_chooser_viewset, section_chooser_viewset, song_chooser_viewset, event_chooser_viewset