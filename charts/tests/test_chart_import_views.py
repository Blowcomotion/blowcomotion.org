"""
Unit tests for chart import view permission gates and import POST logic.
"""
from unittest.mock import patch

from django.contrib.auth.models import ContentType, Permission, User
from django.test import Client, TestCase
from django.urls import reverse

from blowcomotion.models import Chart, Song


class ChartImportPermissionTests(TestCase):
    def setUp(self):
        self.client = Client()
        ct = ContentType.objects.get_for_model(Chart)
        self.change_perm = Permission.objects.get(content_type=ct, codename='change_chart')
        # Wagtail's admin-login wall (register_admin_urls) requires
        # wagtailadmin.access_admin in addition to is_staff before any
        # admin view — including ours — is reached at all. Both test users
        # need this so the requests actually exercise our change_chart gate
        # rather than being turned away earlier by Wagtail's own wall.
        self.access_admin_perm = Permission.objects.get(
            content_type__app_label='wagtailadmin', codename='access_admin'
        )

    def test_staff_without_permission_denied(self):
        user = User.objects.create_user(username='staff', password='pw', is_staff=True)
        user.user_permissions.add(self.access_admin_perm)
        self.client.login(username='staff', password='pw')
        # chart_import_picker is registered via Wagtail's register_admin_urls
        # hook, which wraps every admin view in
        # wagtail.admin.auth.require_admin_access. That wrapper catches the
        # PermissionDenied our permission_required(raise_exception=True)
        # decorator raises and, for a normal (non-XHR) browser request,
        # converts it into a 302 redirect to the admin home with a flash
        # message rather than letting a raw 403 through. A genuine 403 only
        # surfaces for XMLHttpRequest requests, so we assert the actual
        # denied behavior (redirect to admin home) as well as the 403 for
        # an XHR request.
        response = self.client.get(reverse('chart_import_picker'))
        self.assertRedirects(
            response, reverse('wagtailadmin_home'), fetch_redirect_response=False
        )
        ajax_response = self.client.get(
            reverse('chart_import_picker'), HTTP_X_REQUESTED_WITH='XMLHttpRequest'
        )
        self.assertEqual(ajax_response.status_code, 403)

    def test_arranger_allowed(self):
        user = User.objects.create_user(username='arranger', password='pw', is_staff=True)
        user.user_permissions.add(self.change_perm, self.access_admin_perm)
        self.client.login(username='arranger', password='pw')
        response = self.client.get(reverse('chart_import_picker'))
        self.assertEqual(response.status_code, 200)

    def test_anonymous_redirected(self):
        response = self.client.get(reverse('chart_import_picker'))
        self.assertEqual(response.status_code, 302)


class ChartImportConductorPostTests(TestCase):
    def setUp(self):
        self.client = Client()
        ct = ContentType.objects.get_for_model(Chart)
        change_perm = Permission.objects.get(content_type=ct, codename='change_chart')
        access_admin_perm = Permission.objects.get(
            content_type__app_label='wagtailadmin', codename='access_admin'
        )
        self.user = User.objects.create_user(username='importer', password='pw', is_staff=True)
        self.user.user_permissions.add(change_perm, access_admin_perm)
        self.client.login(username='importer', password='pw')
        self.song = Song.objects.create(title="Test Song")

    @patch('charts.import_views.list_pdfs_in_folder', return_value=[])
    def test_post_conductor_row_creates_conductor_chart(self, _mock):
        post_data = {
            'song_id': str(self.song.id),
            'folder_name': 'Test Song',
            'folder_id': 'fake_folder',
            'rows': ['0'],
            'row_0_file_id': 'file_abc',
            'row_0_filename': 'TestSong_Score.pdf',
            'row_0_modified': '2024-01-01T00:00:00.000Z',
            'row_0_is_conductor': '1',
            'row_0_chart_id': '',
            'row_0_part': '',
        }
        response = self.client.post(reverse('chart_import_review'), post_data)
        self.assertRedirects(response, reverse('chart_import_picker'), fetch_redirect_response=False)
        chart = Chart.objects.get(song=self.song)
        self.assertTrue(chart.is_conductor_chart)
        self.assertIsNone(chart.instrument)
        self.assertEqual(chart.drive_file_id, 'file_abc')
