from wagtail import hooks
from wagtail.admin.menu import Menu, MenuItem, SubmenuMenuItem
from wagtail.snippets.models import register_snippet

from django.urls import path, reverse

from blowcomotion.views import dump_data

from .chooser_viewsets import (
    event_chooser_viewset,
    gigo_gig_chooser_viewset,
    instrument_chooser_viewset,
    member_chooser_viewset,
    section_chooser_viewset,
    song_chooser_viewset,
)
from .snippet_viewsets import BandViewSetGroup, FormsViewSetGroup

register_snippet(BandViewSetGroup)
register_snippet(FormsViewSetGroup)


@hooks.register("register_admin_urls")
def register_admin_urls():
    """
    Register the admin URLs for the app.
    """
    return [
        path("dump_data/", dump_data, name="dump_data"),
    ]


@hooks.register("register_admin_menu_item")
def register_admin_menu_item():
    """
    Register the admin menu item for the app.
    """
    submenu = Menu(items=[
            MenuItem('Dump Data', reverse('dump_data'), icon_name='download'),
    ])
    return SubmenuMenuItem('Management', submenu, icon_name='cogs', order=10000)


@hooks.register("register_admin_viewset")
def register_viewset():
    return (
        member_chooser_viewset,
        instrument_chooser_viewset,
        section_chooser_viewset,
        song_chooser_viewset,
        event_chooser_viewset,
        gigo_gig_chooser_viewset,
    )
