"""
Unit tests for admin Utilities/Rental Requests/Import Charts menu visibility.
"""
from django.contrib.auth.models import ContentType, Permission, User
from django.test import Client, TestCase
from django.urls import reverse


class AdminMenuVisibilityTests(TestCase):
    def setUp(self):
        self.client = Client()

    def _get_admin_home_html(self, user):
        self.client.force_login(user)
        response = self.client.get(reverse('wagtailadmin_home'))
        return response.content.decode()

    def test_staff_without_any_permission_does_not_see_utilities_menu(self):
        access_admin = Permission.objects.get(content_type__app_label='wagtailadmin', codename='access_admin')
        user = User.objects.create_user(username='staff', password='pw', is_staff=True)
        user.user_permissions.add(access_admin)
        html = self._get_admin_home_html(user)
        self.assertNotIn('Utilities', html)
        self.assertNotIn('Rental Requests', html)
        self.assertNotIn('Import Charts', html)

    def test_dev_sees_utilities_menu(self):
        access_admin = Permission.objects.get(content_type__app_label='wagtailadmin', codename='access_admin')
        dev_perm = Permission.objects.get(codename='access_dev_tools')
        user = User.objects.create_user(username='dev', password='pw', is_staff=True)
        user.user_permissions.add(access_admin, dev_perm)
        html = self._get_admin_home_html(user)
        self.assertIn('Utilities', html)

    def test_library_manager_sees_rental_requests(self):
        access_admin = Permission.objects.get(content_type__app_label='wagtailadmin', codename='access_admin')
        change_li = Permission.objects.get(content_type__app_label='blowcomotion', codename='change_libraryinstrument')
        user = User.objects.create_user(username='librarian', password='pw', is_staff=True)
        user.user_permissions.add(access_admin, change_li)
        html = self._get_admin_home_html(user)
        self.assertIn('Rental Requests', html)
        self.assertNotIn('Utilities', html)

    def test_arranger_sees_import_charts(self):
        access_admin = Permission.objects.get(content_type__app_label='wagtailadmin', codename='access_admin')
        change_chart = Permission.objects.get(content_type__app_label='blowcomotion', codename='change_chart')
        user = User.objects.create_user(username='arranger', password='pw', is_staff=True)
        user.user_permissions.add(access_admin, change_chart)
        html = self._get_admin_home_html(user)
        self.assertIn('Import Charts', html)

    def test_superuser_sees_everything(self):
        user = User.objects.create_superuser(username='admin', email='admin@example.com', password='pw')
        html = self._get_admin_home_html(user)
        self.assertIn('Utilities', html)
        self.assertIn('Rental Requests', html)
        self.assertIn('Import Charts', html)

    def test_data_analyst_sees_utilities_and_exports_menu(self):
        access_admin = Permission.objects.get(content_type__app_label='wagtailadmin', codename='access_admin')
        analyst_perm = Permission.objects.get(codename='access_real_data_exports')
        user = User.objects.create_user(username='analyst', password='pw', is_staff=True)
        user.user_permissions.add(access_admin, analyst_perm)
        html = self._get_admin_home_html(user)
        self.assertIn('Utilities', html)
        self.assertIn('Exports', html)
        self.assertIn('Dump Data', html)
