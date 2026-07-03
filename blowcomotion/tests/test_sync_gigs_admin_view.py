"""
Unit tests for the sync_gigs_admin view permission gate.
"""
from unittest.mock import patch

from django.contrib.auth.models import ContentType, Permission, User
from django.test import Client, TestCase
from django.urls import reverse

from blowcomotion.models import CachedGig


class SyncGigsAdminPermissionTests(TestCase):
    def setUp(self):
        self.client = Client()
        ct = ContentType.objects.get_for_model(CachedGig)
        self.change_cachedgig = Permission.objects.get(content_type=ct, codename='change_cachedgig')
        # Get or create the Wagtail admin access permission
        try:
            self.admin_perm = Permission.objects.get(
                content_type__app_label='wagtailadmin',
                codename='access_admin'
            )
        except Permission.DoesNotExist:
            self.admin_perm = None

    def test_anonymous_denied(self):
        response = self.client.get(reverse('sync_gigs'))
        self.assertIn(response.status_code, [302, 403])

    def test_staff_without_permission_denied(self):
        user = User.objects.create_user(username='staff', password='pw', is_staff=True)
        if self.admin_perm:
            user.user_permissions.add(self.admin_perm)
        self.client.login(username='staff', password='pw')
        response = self.client.get(reverse('sync_gigs'))
        self.assertEqual(response.status_code, 403)

    def test_user_with_change_cachedgig_allowed(self):
        user = User.objects.create_user(username='booker', password='pw', is_staff=True)
        user.user_permissions.add(self.change_cachedgig)
        if self.admin_perm:
            user.user_permissions.add(self.admin_perm)
        self.client.login(username='booker', password='pw')
        response = self.client.get(reverse('sync_gigs'))
        self.assertEqual(response.status_code, 200)

    def test_superuser_allowed(self):
        User.objects.create_superuser(username='admin', email='admin@example.com', password='pw')
        self.client.login(username='admin', password='pw')
        response = self.client.get(reverse('sync_gigs'))
        self.assertEqual(response.status_code, 200)
