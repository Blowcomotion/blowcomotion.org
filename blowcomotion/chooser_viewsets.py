from wagtail.admin.ui.tables import TitleColumn
from wagtail.admin.views.generic.chooser import (BaseChooseView,
                                                 ChooseResultsViewMixin,
                                                 ChooseViewMixin,
                                                 CreationFormMixin)
from wagtail.admin.viewsets.chooser import ChooserViewSet


class ChartChooserViewset(ChooserViewSet):
    model = "blowcomotion.Chart"
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


class SongChooserViewset(ChooserViewSet):
    model = "blowcomotion.Song"
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


class EventChooserViewset(ChooserViewSet):
    model = "blowcomotion.Event"
    choose_one_text = "Choose an event"
    choose_another_text = "Choose another event"
    edit_item_text = "Edit event"
    form_fields = [
        "title",
        "date",
        "time",
        "location",
        "location_url",
        "description",
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
instrument_chooser_viewset = InstrumentChooserViewset("instrument_chooser")
section_chooser_viewset = SectionChooserViewset("section_chooser")
event_chooser_viewset = EventChooserViewset("event_chooser")
song_chooser_viewset = SongChooserViewset("song_chooser")
chart_chooser_viewset = ChartChooserViewset("chart_chooser")
