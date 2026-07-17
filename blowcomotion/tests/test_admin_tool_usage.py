"""
Tests for the admin tool usage tracking endpoint (issue #311) and the
usage dashboard built on top of it (issue #333).
"""

import json
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.middleware.csrf import get_token
from django.test import Client, RequestFactory, TestCase
from django.utils import timezone

from blowcomotion.models import AdminToolUsage

User = get_user_model()


class AdminToolUsageViewTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.url = '/admin-tool-usage/'

        # Real Wagtail admin users are typically is_staff=False with the
        # wagtailadmin.access_admin permission (Wagtail never sets is_staff);
        # the view must accept them — see the prod bug this shape caught.
        self.admin_user = User.objects.create_user(
            username='wagtailadmin',
            password='testpass',
        )
        self.admin_user.user_permissions.add(
            Permission.objects.get(
                codename='access_admin',
                content_type__app_label='wagtailadmin',
            )
        )
        self.regular_user = User.objects.create_user(
            username='regular',
            password='testpass',
            is_staff=False,
        )

    def test_admin_user_post_creates_record(self):
        self.client.login(username='wagtailadmin', password='testpass')
        response = self.client.post(
            self.url,
            data=json.dumps({'tool': '/admin/images/', 'action': 'upload-button'}),
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 204)
        self.assertEqual(AdminToolUsage.objects.count(), 1)
        record = AdminToolUsage.objects.first()
        self.assertEqual(record.user, self.admin_user)
        self.assertEqual(record.tool, '/admin/images/')
        self.assertEqual(record.action, 'upload-button')

    def test_admin_user_post_without_action_creates_page_view_record(self):
        self.client.login(username='wagtailadmin', password='testpass')
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
        self.client.login(username='wagtailadmin', password='testpass')
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

    def test_user_without_admin_access_is_rejected(self):
        self.client.login(username='regular', password='testpass')
        response = self.client.post(
            self.url,
            data=json.dumps({'tool': '/admin/images/'}),
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 403)
        self.assertEqual(AdminToolUsage.objects.count(), 0)

    def test_is_staff_alone_is_not_enough(self):
        # is_staff is a Django-admin concept and does not grant Wagtail admin
        # access; the view keys off wagtailadmin.access_admin instead.
        User.objects.create_user(
            username='djangostaff', password='testpass', is_staff=True,
        )
        self.client.login(username='djangostaff', password='testpass')
        response = self.client.post(
            self.url,
            data=json.dumps({'tool': '/admin/images/'}),
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 403)
        self.assertEqual(AdminToolUsage.objects.count(), 0)

    def test_get_is_rejected(self):
        self.client.login(username='wagtailadmin', password='testpass')
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
        csrf_client.force_login(self.admin_user)

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


class AdminToolUsageDashboardTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.url = '/admin/tool-usage/'

        self.superuser = User.objects.create_superuser(
            username='super',
            password='testpass',
            first_name='Sue',
            last_name='Per',
        )
        self.staff_user = User.objects.create_user(
            username='staff',
            password='testpass',
            is_staff=True,
        )

    def test_requires_permission(self):
        self.client.login(username='staff', password='testpass')
        response = self.client.get(self.url)
        self.assertNotEqual(response.status_code, 200)

    def test_anonymous_is_redirected_to_login(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 302)

    def test_dashboard_aggregates_usage(self):
        AdminToolUsage.objects.create(user=self.superuser, tool='/admin/pages/')
        AdminToolUsage.objects.create(user=self.superuser, tool='/admin/pages/')
        AdminToolUsage.objects.create(user=self.superuser, tool='/admin/images/', action='upload-button')
        AdminToolUsage.objects.create(user=self.staff_user, tool='/admin/images/')
        # Backdate one record outside the default 30-day window; it must
        # not be counted (auto_now_add means we update after create).
        old = AdminToolUsage.objects.create(user=self.staff_user, tool='/admin/old-tool/')
        AdminToolUsage.objects.filter(pk=old.pk).update(
            timestamp=timezone.now() - timedelta(days=45)
        )

        self.client.login(username='super', password='testpass')
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)

        self.assertEqual(response.context['days'], 30)
        self.assertEqual(response.context['total_events'], 4)

        top_tools = response.context['top_tools']
        self.assertEqual(top_tools[0]['tool'], '/admin/pages/')
        self.assertEqual(top_tools[0]['count'], 2)
        self.assertEqual(top_tools[0]['pct'], 100)
        self.assertNotIn('/admin/old-tool/', [t['tool'] for t in top_tools])

        per_user = response.context['per_user']
        self.assertEqual(per_user[0]['user'], 'Sue Per')
        self.assertEqual(per_user[0]['count'], 3)
        self.assertEqual(per_user[1]['user'], 'staff')
        self.assertEqual(per_user[1]['count'], 1)

        top_actions = response.context['top_actions']
        self.assertEqual(len(top_actions), 1)
        self.assertEqual(top_actions[0]['action'], 'upload-button')

        usage_by_day = response.context['usage_by_day']
        self.assertEqual(len(usage_by_day), 30)
        self.assertEqual(usage_by_day[-1]['day'], timezone.localdate())
        self.assertEqual(usage_by_day[-1]['count'], 4)

    def test_invalid_days_falls_back_to_30(self):
        self.client.login(username='super', password='testpass')
        for bad in ('999', 'abc', '-7'):
            response = self.client.get(self.url, {'days': bad})
            self.assertEqual(response.context['days'], 30)

    def test_valid_period_is_honoured(self):
        self.client.login(username='super', password='testpass')
        response = self.client.get(self.url, {'days': '7'})
        self.assertEqual(response.context['days'], 7)
        self.assertEqual(len(response.context['usage_by_day']), 7)
