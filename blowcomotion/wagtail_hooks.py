from wagtail import hooks
from wagtail.admin.menu import Menu, MenuItem, SubmenuMenuItem
from wagtail.admin.ui.components import Component
from wagtail.snippets.models import register_snippet

from django.conf import settings as django_settings
from django.templatetags.static import static
from django.urls import path, reverse
from django.utils.html import format_html
from django.utils.safestring import mark_safe

from blowcomotion.views import (
    dump_data,
    export_attendance_csv,
    export_charts_csv,
    export_library_instruments_csv,
    export_members_csv,
    fetch_embed_data,
    instrument_library_available,
    instrument_library_needs_repair,
    instrument_library_rented,
    rental_request_return,
    rental_request_review,
    rental_requests_dashboard,
    sync_gigs_admin,
)

from .chooser_viewsets import (
    event_chooser_viewset,
    gigo_gig_chooser_viewset,
    instrument_chooser_viewset,
    library_instrument_available_chooser_viewset,
    library_instrument_chooser_viewset,
    member_chooser_viewset,
    section_chooser_viewset,
    song_chooser_viewset,
)
from .snippet_viewsets import BandViewSetGroup, FormsViewSetGroup, SyncViewSetGroup

register_snippet(BandViewSetGroup)
register_snippet(FormsViewSetGroup)
register_snippet(SyncViewSetGroup)


class PermissionMenuItem(MenuItem):
    def __init__(self, *args, permission=None, **kwargs):
        self._permission = permission
        super().__init__(*args, **kwargs)

    def is_shown(self, request):
        if self._permission is None:
            return True
        return request.user.has_perm(self._permission)


class PermissionSubmenuMenuItem(SubmenuMenuItem):
    def __init__(self, *args, permission=None, **kwargs):
        self._permission = permission
        super().__init__(*args, **kwargs)

    def is_shown(self, request):
        if self._permission is None:
            return True
        return request.user.has_perm(self._permission)


@hooks.register("register_admin_urls")
def register_admin_urls():
    """
    Register the admin URLs for the app.
    """
    return [
        path("dump_data/", dump_data, name="dump_data"),
        path("sync_gigs/", sync_gigs_admin, name="sync_gigs"),
        path("export_members/", export_members_csv, name="export_members"),
        path("export_attendance/", export_attendance_csv, name="export_attendance"),
        path("export_charts/", export_charts_csv, name="export_charts"),
        path("export_library_instruments/", export_library_instruments_csv, name="export_library_instruments"),
        path("embeds/fetch/", fetch_embed_data, name="fetch_embed_data"),
        path(
            "instrument-library/rented/",
            instrument_library_rented,
            name="instrument_library_rented",
        ),
        path(
            "instrument-library/available/",
            instrument_library_available,
            name="instrument_library_available",
        ),
        path(
            "instrument-library/needs-repair/",
            instrument_library_needs_repair,
            name="instrument_library_needs_repair",
        ),
        # TODO(#250): delete — replaced by Rental Requests dashboard
        # path(
        #     "instrument-library/manage/",
        #     instrument_library_quick_rent,
        #     name="instrument_library_quick_rent",
        # ),
        path("rental-requests/", rental_requests_dashboard, name="rental_requests_dashboard"),
        path("rental-requests/<int:pk>/", rental_request_review, name="rental_request_review"),
        path("rental-requests/<int:pk>/return/", rental_request_return, name="rental_request_return"),
    ]


@hooks.register("register_admin_urls")
def register_chart_import_urls():
    from django.urls import path

    from blowcomotion import views_chart_import
    return [
        path("chart-import/", views_chart_import.picker, name="chart_import_picker"),
        path("chart-import/review/", views_chart_import.review, name="chart_import_review"),
    ]


@hooks.register("register_admin_menu_item")
def register_management_menu_item():
    """
    Register the admin menu item for the app.
    """
    exports_submenu = Menu(items=[
        PermissionMenuItem('Dump Data', reverse('dump_data'), icon_name='download',
                            permission='blowcomotion.access_dev_tools'),
        PermissionMenuItem('Export Members CSV', reverse('export_members'), icon_name='table',
                            permission='blowcomotion.access_real_data_exports'),
        PermissionMenuItem('Export Attendance CSV', reverse('export_attendance'), icon_name='calendar',
                            permission='blowcomotion.access_real_data_exports'),
        PermissionMenuItem('Export Charts CSV', reverse('export_charts'), icon_name='doc-full-inverse',
                            permission='blowcomotion.access_real_data_exports'),
        PermissionMenuItem('Export Library Instruments CSV', reverse('export_library_instruments'), icon_name='french-horn',
                            permission='blowcomotion.access_real_data_exports'),
    ])

    library_dashboards_submenu = Menu(items=[
        PermissionMenuItem('Library: Rented', reverse('instrument_library_rented'), icon_name='french-horn',
                            permission='blowcomotion.change_libraryinstrument'),
        PermissionMenuItem('Library: Available', reverse('instrument_library_available'), icon_name='french-horn',
                            permission='blowcomotion.change_libraryinstrument'),
        PermissionMenuItem('Library: Maintenance', reverse('instrument_library_needs_repair'), icon_name='warning',
                            permission='blowcomotion.change_libraryinstrument'),
    ])

    submenu = Menu(items=[
        PermissionSubmenuMenuItem('Exports', exports_submenu, icon_name='download',
                                   permission='blowcomotion.access_dev_tools'),
        PermissionSubmenuMenuItem('Library Dashboards', library_dashboards_submenu, icon_name='french-horn',
                                   permission='blowcomotion.change_libraryinstrument'),
        PermissionMenuItem('Sync Gigs', reverse('sync_gigs'), icon_name='cog',
                            permission='blowcomotion.change_cachedgig'),
    ])
    # ponytail: Utilities menu requires access_dev_tools, so a Data-Analyst-only
    # user has no menu entry point to the exports (still reachable by URL). Revisit
    # if Data Analyst needs its own menu item.
    return PermissionSubmenuMenuItem(
        'Utilities', submenu, icon_name='cogs', order=10000,
        permission='blowcomotion.access_dev_tools',
    )


# TODO(#250): delete — replaced by Rental Requests dashboard
# @hooks.register("register_admin_menu_item")
# def register_library_quick_rent_menu_item():
#     return MenuItem(
#         'Library: Quick Rent',
#         reverse('instrument_library_quick_rent'),
#         icon_name='french-horn',
#         order=295,
#     )


@hooks.register("register_admin_menu_item")
def register_rental_requests_menu_item():
    return PermissionMenuItem(
        "Rental Requests",
        reverse("rental_requests_dashboard"),
        icon_name="french-horn",
        order=295,
        permission='blowcomotion.change_libraryinstrument',
    )


@hooks.register("register_admin_menu_item")
def register_chart_import_menu_item():
    return PermissionMenuItem(
        "Import Charts",
        reverse("chart_import_picker"),
        icon_name="google-drive",
        order=901,
        permission='blowcomotion.change_chart',
    )


@hooks.register("register_icons")
def register_icons(icons):
    return icons + [
        'icons/drum-solid-full.svg',
        'icons/music-solid-full.svg',
        'icons/french-horn.svg',
        'icons/google-drive.svg',
    ]


@hooks.register("register_admin_viewset")
def register_viewset():
    return (
        member_chooser_viewset,
        instrument_chooser_viewset,
        library_instrument_chooser_viewset,
        library_instrument_available_chooser_viewset,
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


@hooks.register('insert_global_admin_css')
def admin_env_sidebar_css():
    color = '#1a5c2e' if django_settings.DEBUG else '#5b1a76'
    return mark_safe(f'<style>.sidebar,.sidebar-loading,.sidebar__inner{{background-color:{color}!important}}</style>')


@hooks.register('insert_global_admin_js')
def video_title_resolver_js():
    """
    Load the video title resolver JavaScript for VideoFeedBlock.
    This fetches video titles from URLs and updates the minimap display.
    """
    return format_html(
        '<script src="{}"></script>',
        static('js/video-title-resolver.js')
    )
