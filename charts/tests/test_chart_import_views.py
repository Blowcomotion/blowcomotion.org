"""
Unit tests for chart import view permission gates and import POST logic.
"""
from unittest.mock import patch

from django.conf import settings
from django.contrib.auth.models import ContentType, Permission, User
from django.test import Client, TestCase
from django.urls import reverse

from blowcomotion.models import Chart, Instrument, Song


class ChartImportPermissionTests(TestCase):
    def setUp(self):
        self.client = Client()
        ct = ContentType.objects.get_for_model(Chart)
        self.change_perm = Permission.objects.get(content_type=ct, codename='change_chart')

    def test_logged_in_without_permission_denied(self):
        # The tool now lives on the public site rather than under
        # register_admin_urls, so there is no Wagtail require_admin_access
        # wrapper to convert PermissionDenied into a redirect — the 403 from
        # permission_required(raise_exception=True) surfaces directly.
        User.objects.create_user(username='member', password='pw')
        self.client.login(username='member', password='pw')
        response = self.client.get(reverse('chart_import_picker'))
        self.assertEqual(response.status_code, 403)

    def test_arranger_allowed(self):
        user = User.objects.create_user(username='arranger', password='pw')
        user.user_permissions.add(self.change_perm)
        self.client.login(username='arranger', password='pw')
        response = self.client.get(reverse('chart_import_picker'))
        self.assertEqual(response.status_code, 200)

    def test_anonymous_redirected_to_login(self):
        response = self.client.get(reverse('chart_import_picker'))
        self.assertEqual(response.status_code, 302)
        self.assertIn(settings.LOGIN_URL, response.url)


class ChartImportConductorPostTests(TestCase):
    def setUp(self):
        self.client = Client()
        ct = ContentType.objects.get_for_model(Chart)
        change_perm = Permission.objects.get(content_type=ct, codename='change_chart')
        self.user = User.objects.create_user(username='importer', password='pw')
        self.user.user_permissions.add(change_perm)
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

    @patch('charts.import_views.list_pdfs_in_folder', return_value=[])
    def test_post_conductor_on_instrument_chart_clears_instrument(self, _mock):
        inst = Instrument.objects.create(name='Trumpet')
        chart = Chart.objects.create(
            song=self.song, instrument=inst, part='1st Trumpet',
            drive_pdf_url='https://drive.google.com/file/d/old/view',
        )
        post_data = {
            'song_id': str(self.song.id),
            'folder_name': 'Test Song',
            'folder_id': 'fake_folder',
            'rows': ['0'],
            'row_0_file_id': 'file_xyz',
            'row_0_filename': 'TestSong_Trumpet.pdf',
            'row_0_modified': '2024-01-01T00:00:00.000Z',
            'row_0_is_conductor': '1',
            'row_0_chart_id': str(chart.id),
            'row_0_instrument_id': str(inst.id),
            'row_0_part': '1st Trumpet',
        }
        self.client.post(reverse('chart_import_review'), post_data)
        chart.refresh_from_db()
        self.assertTrue(chart.is_conductor_chart)
        self.assertIsNone(chart.instrument)
        self.assertEqual(chart.part, '')
        chart.full_clean()
