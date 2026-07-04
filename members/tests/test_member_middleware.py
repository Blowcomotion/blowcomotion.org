import time

from django.contrib.auth import get_user_model
from django.test import RequestFactory, TestCase, override_settings
from django.utils import timezone

User = get_user_model()


def _make_user(staff=False):
    username = f"user_{User.objects.count()}@example.com"
    u = User.objects.create_user(username=username, email=username, password="pass")
    u.is_staff = staff
    u.save()
    return u


def _make_request(user, session_data=None):
    factory = RequestFactory()
    request = factory.get("/member/profile/")
    request.user = user
    request.session = {}
    if session_data:
        request.session.update(session_data)
    return request


class MemberIdleLogoutMiddlewareTests(TestCase):
    def get_middleware(self):
        from members.middleware import MemberIdleLogoutMiddleware
        return MemberIdleLogoutMiddleware(get_response=lambda r: None)

    @override_settings(MEMBER_IDLE_TIMEOUT=3600)
    def test_sets_last_activity_on_first_request(self):
        mw = self.get_middleware()
        user = _make_user()
        request = _make_request(user)
        mw.process_request(request)
        self.assertIn("last_activity", request.session)

    @override_settings(MEMBER_IDLE_TIMEOUT=3600)
    def test_active_session_allowed(self):
        from django.utils import timezone
        mw = self.get_middleware()
        user = _make_user()
        recent = timezone.now().timestamp() - 100
        request = _make_request(user, {"last_activity": recent})
        result = mw.process_request(request)
        self.assertIsNone(result)  # no redirect

    @override_settings(MEMBER_IDLE_TIMEOUT=60)
    def test_idle_session_redirects_to_login(self):
        from django.utils import timezone
        mw = self.get_middleware()
        user = _make_user()
        expired = timezone.now().timestamp() - 120
        request = _make_request(user, {"last_activity": expired})
        result = mw.process_request(request)
        self.assertIsNotNone(result)
        self.assertEqual(result.status_code, 302)
        self.assertIn("/member/login/", result["Location"])

    @override_settings(MEMBER_IDLE_TIMEOUT=60)
    def test_staff_user_not_affected(self):
        from django.utils import timezone
        mw = self.get_middleware()
        staff_user = _make_user(staff=True)
        expired = timezone.now().timestamp() - 120
        request = _make_request(staff_user, {"last_activity": expired})
        result = mw.process_request(request)
        self.assertIsNone(result)  # staff not logged out

    @override_settings(MEMBER_IDLE_TIMEOUT=3600)
    def test_anonymous_user_not_affected(self):
        from django.contrib.auth.models import AnonymousUser
        mw = self.get_middleware()
        request = _make_request(AnonymousUser())
        result = mw.process_request(request)
        self.assertIsNone(result)
