"""
Unit tests for CSV export view permission gates.
"""
from unittest.mock import patch

from django.contrib.auth.models import Permission, User
from django.test import Client, TestCase
from django.urls import reverse

EXPORT_URL_NAMES = [
    'export_members',
    'export_attendance',
    'export_charts',
    'export_library_instruments',
]


class ExportViewsPermissionTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.analyst_perm = Permission.objects.get(codename='access_real_data_exports')
        # Get or create the Wagtail admin access permission
        try:
            self.admin_perm = Permission.objects.get(
                content_type__app_label='wagtailadmin',
                codename='access_admin'
            )
        except Permission.DoesNotExist:
            self.admin_perm = None

    def test_anonymous_denied(self):
        for url_name in EXPORT_URL_NAMES:
            response = self.client.get(reverse(url_name))
            self.assertIn(response.status_code, [302, 403], url_name)

    def test_staff_without_permission_denied(self):
        user = User.objects.create_user(username='staff', password='pw', is_staff=True)
        if self.admin_perm:
            user.user_permissions.add(self.admin_perm)
        self.client.login(username='staff', password='pw')
        for url_name in EXPORT_URL_NAMES:
            response = self.client.get(reverse(url_name))
            self.assertEqual(response.status_code, 403, url_name)

    @patch('blowcomotion.views.call_command')
    def test_data_analyst_allowed(self, mock_call_command):
        mock_call_command.return_value = None
        user = User.objects.create_user(username='analyst', password='pw', is_staff=True)
        user.user_permissions.add(self.analyst_perm)
        if self.admin_perm:
            user.user_permissions.add(self.admin_perm)
        self.client.login(username='analyst', password='pw')
        for url_name in EXPORT_URL_NAMES:
            with patch('builtins.open', create=True) as mock_open:
                mock_open.return_value.__enter__.return_value.read.return_value = b'csv,data'
                response = self.client.get(reverse(url_name))
            self.assertEqual(response.status_code, 200, url_name)

    def test_superuser_allowed(self):
        User.objects.create_superuser(username='admin', email='admin@example.com', password='pw')
        self.client.login(username='admin', password='pw')
        for url_name in EXPORT_URL_NAMES:
            with patch('blowcomotion.views.call_command'), \
                 patch('builtins.open', create=True) as mock_open:
                mock_open.return_value.__enter__.return_value.read.return_value = b'csv,data'
                response = self.client.get(reverse(url_name))
            self.assertEqual(response.status_code, 200, url_name)
