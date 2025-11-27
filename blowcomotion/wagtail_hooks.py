from wagtail import hooks
from wagtail.admin.menu import Menu, MenuItem, SubmenuMenuItem
from wagtail.admin.ui.components import Component
from wagtail.snippets.models import register_snippet

from django.urls import path, reverse
from django.utils.html import format_html

from blowcomotion.views import dump_data, export_attendance_csv, export_members_csv

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
        path("export_members/", export_members_csv, name="export_members"),
        path("export_attendance/", export_attendance_csv, name="export_attendance"),
    ]


@hooks.register("register_admin_menu_item")
def register_admin_menu_item():
    """
    Register the admin menu item for the app.
    """
    submenu = Menu(items=[
        MenuItem('Dump Data', reverse('dump_data'), icon_name='download'),
        MenuItem('Export Members CSV', reverse('export_members'), icon_name='table'),
        MenuItem('Export Attendance CSV', reverse('export_attendance'), icon_name='calendar'),
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


class NotificationBannerPanel(Component):
    """Panel for quick access to notification banner editing."""
    order = 100

    def render_html(self, parent_context):
        # Get the notification banner settings URL
        edit_url = reverse('wagtailsettings:edit', args=['blowcomotion', 'NotificationBanner'])
        
        return format_html(
            """
            <section class="panel summary nice-padding" style="margin-bottom: 20px;">
                <h3>Notification Banner</h3>
                <p>Quickly edit the site-wide notification banner message. Usually to notify of rehearsal location changes or other important announcements.</p>
                <a href="{}" class="button">Edit Notification Banner</a>
            </section>
            """,
            edit_url
        )


@hooks.register('construct_homepage_panels')
def add_notification_banner_panel(request, panels):
    """Add notification banner shortcut to the admin homepage."""
    panels.append(NotificationBannerPanel())
