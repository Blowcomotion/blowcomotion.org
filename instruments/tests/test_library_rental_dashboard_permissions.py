"""
Unit tests for library/rental dashboard view permission gates.
"""
from django.contrib.auth.models import ContentType, Permission, User
from django.test import Client, TestCase
from django.urls import reverse

from blowcomotion.models import LibraryInstrument

DASHBOARD_URL_NAMES = [
    'instrument_library_rented',
    'instrument_library_available',
    'instrument_library_needs_repair',
    'instrument_library_gallery',
    'rental_requests_dashboard',
]


class LibraryRentalDashboardPermissionTests(TestCase):
    def setUp(self):
        self.client = Client()
        ct = ContentType.objects.get_for_model(LibraryInstrument)
        self.change_perm = Permission.objects.get(content_type=ct, codename='change_libraryinstrument')
        # Wagtail's admin-login wall (register_admin_urls) requires
        # wagtailadmin.access_admin in addition to is_staff before any
        # admin view — including ours — is reached at all. Both test users
        # need this so the requests actually exercise our
        # change_libraryinstrument gate rather than being turned away
        # earlier by Wagtail's own wall.
        self.access_admin_perm = Permission.objects.get(
            content_type__app_label='wagtailadmin', codename='access_admin'
        )

    def test_staff_without_permission_denied(self):
        user = User.objects.create_user(username='staff', password='pw', is_staff=True)
        user.user_permissions.add(self.access_admin_perm)
        self.client.login(username='staff', password='pw')
        for url_name in DASHBOARD_URL_NAMES:
            # These views are registered via Wagtail's register_admin_urls
            # hook, which wraps every admin view in
            # wagtail.admin.auth.require_admin_access. That wrapper catches
            # the PermissionDenied our permission_required(raise_exception=True)
            # decorator raises and, for a normal (non-XHR) browser request,
            # converts it into a 302 redirect to the admin home with a flash
            # message rather than letting a raw 403 through. A genuine 403
            # only surfaces for XMLHttpRequest requests, which these
            # dashboards never receive from real users, so we assert the
            # actual denied behavior (redirect to admin home) instead.
            response = self.client.get(reverse(url_name))
            self.assertRedirects(
                response, reverse('wagtailadmin_home'), fetch_redirect_response=False
            )
            ajax_response = self.client.get(
                reverse(url_name), HTTP_X_REQUESTED_WITH='XMLHttpRequest'
            )
            self.assertEqual(ajax_response.status_code, 403, url_name)

    def test_library_manager_allowed(self):
        user = User.objects.create_user(username='librarian', password='pw', is_staff=True)
        user.user_permissions.add(self.change_perm, self.access_admin_perm)
        self.client.login(username='librarian', password='pw')
        for url_name in DASHBOARD_URL_NAMES:
            response = self.client.get(reverse(url_name))
            self.assertEqual(response.status_code, 200, url_name)
