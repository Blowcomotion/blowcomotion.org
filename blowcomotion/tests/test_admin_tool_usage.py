"""
Tests for the admin tool usage tracking endpoint (issue #311).
"""

import json

from django.contrib.auth import get_user_model
from django.middleware.csrf import get_token
from django.test import Client, RequestFactory, TestCase

from blowcomotion.models import AdminToolUsage

User = get_user_model()


class AdminToolUsageViewTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.url = '/admin-tool-usage/'

        self.staff_user = User.objects.create_user(
            username='staff',
            password='testpass',
            is_staff=True,
        )
        self.regular_user = User.objects.create_user(
            username='regular',
            password='testpass',
            is_staff=False,
        )

    def test_staff_post_creates_record(self):
        self.client.login(username='staff', password='testpass')
        response = self.client.post(
            self.url,
            data=json.dumps({'tool': '/admin/images/', 'action': 'upload-button'}),
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 204)
        self.assertEqual(AdminToolUsage.objects.count(), 1)
        record = AdminToolUsage.objects.first()
        self.assertEqual(record.user, self.staff_user)
        self.assertEqual(record.tool, '/admin/images/')
        self.assertEqual(record.action, 'upload-button')

    def test_staff_post_without_action_creates_page_view_record(self):
        self.client.login(username='staff', password='testpass')
        response = self.client.post(
            self.url,
            data=json.dumps({'tool': '/admin/pages/'}),
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 204)
        record = AdminToolUsage.objects.get()
        self.assertEqual(record.tool, '/admin/pages/')
        self.assertEqual(record.action, '')

    def test_missing_tool_returns_400(self):
        self.client.login(username='staff', password='testpass')
        response = self.client.post(
            self.url,
            data=json.dumps({'action': 'click'}),
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(AdminToolUsage.objects.count(), 0)

    def test_anonymous_post_is_rejected(self):
        response = self.client.post(
            self.url,
            data=json.dumps({'tool': '/admin/images/'}),
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 403)
        self.assertEqual(AdminToolUsage.objects.count(), 0)

    def test_non_staff_post_is_rejected(self):
        self.client.login(username='regular', password='testpass')
        response = self.client.post(
            self.url,
            data=json.dumps({'tool': '/admin/images/'}),
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 403)
        self.assertEqual(AdminToolUsage.objects.count(), 0)

    def test_get_is_rejected(self):
        self.client.login(username='staff', password='testpass')
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 405)

    def test_json_post_succeeds_with_csrf_enforced(self):
        """
        The JS client sends a JSON body with the CSRF token in the
        X-CSRFToken header (the shape actually shipped — see
        admin-tool-usage.js). Exercise it with CSRF checks turned on,
        since the default test client disables them and would hide a
        regression here (e.g. reading request.POST before request.body).
        """
        csrf_client = Client(enforce_csrf_checks=True)
        csrf_client.force_login(self.staff_user)

        # Populate the csrftoken cookie the same way a real browser session
        # would: any admin page rendering {% csrf_token %} calls get_token()
        # under the hood, which sets the cookie. Force that directly rather
        # than depending on a specific admin template having a POST form.
        request = RequestFactory().get('/admin/')
        request.session = csrf_client.session
        token = get_token(request)
        csrf_client.cookies['csrftoken'] = token

        response = csrf_client.post(
            self.url,
            data=json.dumps({'tool': '/admin/images/', 'action': 'upload-button'}),
            content_type='application/json',
            HTTP_X_CSRFTOKEN=token,
        )
        self.assertEqual(response.status_code, 204)
        self.assertEqual(AdminToolUsage.objects.count(), 1)
