import datetime
import re

import requests
from django.views.generic.base import View
from queryish.rest import APIModel, APIQuerySet
from wagtail.admin.ui.tables import Column, TitleColumn
from wagtail.admin.views.generic.chooser import (BaseChooseView,
                                                 ChooseResultsViewMixin,
                                                 ChooseViewMixin,
                                                 ChosenResponseMixin,
                                                 ChosenViewMixin,
                                                 CreationFormMixin)
from wagtail.admin.viewsets.chooser import ChooserViewSet
from wagtail.admin.widgets import BaseChooser
from django.conf import settings

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
        "location",
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


class MemberChooseView(ChooseViewMixin, CreationFormMixin, BaseMemberChooseView):
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


class GigoAPIQuerySet(APIQuerySet):
    base_url = f"{settings.GIGO_API_URL}/gigs"
    pagination_style = "page"
    page_size = 10
    http_headers = {"X-API-KEY": settings.GIGO_API_KEY}

    def get_results_from_response(self, response):
        return response["gigs"]


class GigoGig(APIModel):
    base_query_class = GigoAPIQuerySet

    class Meta:
        detail_url = f"{settings.GIGO_API_URL}/gigs/%s"
        fields = ["id", "title", "date", "address", "gig_status"]
        verbose_name_plural = "GigoGigs"

    def __str__(self):
        return self.title


class BaseGigoGigChooseView(BaseChooseView):
    @property
    def columns(self):
        return [
            TitleColumn(
                "title",
                label="Title",
                url_name=self.chosen_url_name,
                id_accessor="id",
                link_attrs={"data-chooser-modal-choice": True},
            ),
            Column("date", label="Date"),
            Column("address", label="Address"),
        ]

    def get_object_list(self):
        r = requests.get(
            f"{settings.GIGO_API_URL}/gigs",
            headers={"X-API-KEY": settings.GIGO_API_KEY},
        )
        r.raise_for_status()
        results = r.json()
        if results["gigs"] is None:
            return []
        # remove gigs before today
        results = [
            gig
            for gig in results["gigs"]
            if gig["date"] >= datetime.date.today().isoformat() and gig["gig_status"].lower() == "confirmed" and gig["band"].lower() == "blowcomotion"
        ]

        results.sort(key=lambda gig: gig["date"])
        return results

    def apply_object_list_ordering(self, objects):
        return objects


class GigoGigChooseView(ChooseViewMixin, CreationFormMixin, BaseGigoGigChooseView):
    pass


class GigoGigChooseResultsView(
    ChooseResultsViewMixin, CreationFormMixin, BaseGigoGigChooseView
):
    pass


class GigoGigChosenViewMixin(ChosenViewMixin):
    def get_object(self, pk):
        r = requests.get(
            f"{settings.GIGO_API_URL}/gigs/{int(pk)}",
            headers={"X-API-KEY": settings.GIGO_API_KEY},
        )
        r.raise_for_status()
        return r.json()


class GigoGigChosenResponseMixin(ChosenResponseMixin):
    def get_chosen_response_data(self, item):
        return {
            "id": item["id"],
            "title": item["title"],
        }


class GigoGigChosenView(GigoGigChosenViewMixin, GigoGigChosenResponseMixin, View):
    pass


class BaseGigoGigChooserWidget(BaseChooser):
    def get_instance(self, value):
        if value is None:
            return None
        elif isinstance(value, dict):
            return value
        else:
            r = requests.get(
                f"{settings.GIGO_API_URL}/gigs/{value.id}",
                headers={"X-API-KEY": settings.GIGO_API_KEY},
            )
            r.raise_for_status()
            return r.json()

    def get_value_data_from_instance(self, instance):
        return {
            "id": instance["id"],
            "title": instance["title"],
        }


class GigoGigChooserViewSet(ChooserViewSet):
    model = GigoGig

    choose_one_text = "Choose a GigoGig"
    choose_another_text = "Choose another GigoGig"
    choose_view_class = GigoGigChooseView
    choose_results_view_class = GigoGigChooseResultsView
    chosen_view_class = GigoGigChosenView
    base_widget_class = BaseGigoGigChooserWidget


gigo_gig_chooser_viewset = GigoGigChooserViewSet("gigo_gig_chooser")
member_chooser_viewset = MemberChooserViewset("member_chooser")
instrument_chooser_viewset = InstrumentChooserViewset("instrument_chooser")
section_chooser_viewset = SectionChooserViewset("section_chooser")
event_chooser_viewset = EventChooserViewset("event_chooser")
song_chooser_viewset = SongChooserViewset("song_chooser")
chart_chooser_viewset = ChartChooserViewset("chart_chooser")
