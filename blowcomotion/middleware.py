import logging

from django.conf import settings
from django.shortcuts import redirect
from django.utils import timezone

logger = logging.getLogger(__name__)


class MemberIdleLogoutMiddleware:
    """Logs out non-staff members after MEMBER_IDLE_TIMEOUT seconds of inactivity."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        result = self.process_request(request)
        if result is not None:
            return result
        return self.get_response(request)

    def process_request(self, request):
        if not request.user.is_authenticated or request.user.is_staff:
            return None

        timeout = getattr(settings, "MEMBER_IDLE_TIMEOUT", 3600)
        now = timezone.now().timestamp()
        last_activity = request.session.get("last_activity")

        if last_activity is not None and (now - last_activity) > timeout:
            if hasattr(request.session, 'flush'):
                request.session.flush()
            else:
                request.session.clear()
            login_url = getattr(settings, "LOGIN_URL", "/member/login/")
            logger.info(f"Member session expired for user {request.user.pk}")
            return redirect(f"{login_url}?next={request.path}")

        request.session["last_activity"] = now
        return None
