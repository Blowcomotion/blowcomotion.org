from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core import mail
from django.test import TestCase, override_settings
from django.urls import reverse

from blowcomotion.models import Member
from members import auth as members_auth
from members.auth import create_member_user, make_login_link_token

User = get_user_model()


def make_member(**kwargs):
    defaults = dict(first_name="Sam", last_name="Player", email="sam@example.com")
    defaults.update(kwargs)
    return Member.objects.create(**defaults)


# Patch reCAPTCHA to always pass in tests
recaptcha_pass = patch(
    "members.views._validate_recaptcha", return_value=(True, None)
)


@override_settings(
    EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
    FROM_EMAIL="noreply@blowcomotion.org",
    RATELIMIT_ENABLE=False,
)
class LoginLinkRequestTests(TestCase):
    def setUp(self):
        self.member = make_member()
        self.user = create_member_user(self.member)
        self.user.set_password("Str0ngP@ss!")
        self.user.save()

    def test_get_redirects_to_login(self):
        response = self.client.get(reverse("member-login-link-request"))
        self.assertRedirects(response, reverse("member-login"), fetch_redirect_response=False)

    @recaptcha_pass
    def test_existing_member_receives_login_link(self, mock_recaptcha):
        response = self.client.post(
            reverse("member-login-link-request"), {"email": "SAM@example.com"}
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "a login link has been sent")
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn("/member/login/link/", mail.outbox[0].body)
        self.assertEqual(mail.outbox[0].to, ["sam@example.com"])

    @recaptcha_pass
    def test_unknown_email_same_neutral_response_no_email(self, mock_recaptcha):
        response = self.client.post(
            reverse("member-login-link-request"), {"email": "nobody@example.com"}
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "a login link has been sent")
        self.assertEqual(len(mail.outbox), 0)

    @recaptcha_pass
    def test_inactive_member_no_email(self, mock_recaptcha):
        make_member(email="gone@example.com", is_active=False)
        response = self.client.post(
            reverse("member-login-link-request"), {"email": "gone@example.com"}
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "a login link has been sent")
        self.assertEqual(len(mail.outbox), 0)

    @recaptcha_pass
    def test_member_without_password_gets_set_password_email(self, mock_recaptcha):
        make_member(email="nopass@example.com")
        response = self.client.post(
            reverse("member-login-link-request"), {"email": "nopass@example.com"}
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "a login link has been sent")
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn("/member/set-password/", mail.outbox[0].body)

    def test_recaptcha_failure_sends_no_email(self):
        with patch(
            "members.views._validate_recaptcha",
            return_value=(False, "reCAPTCHA failed"),
        ):
            response = self.client.post(
                reverse("member-login-link-request"), {"email": "sam@example.com"}
            )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(mail.outbox), 0)
        self.assertNotContains(response, "a login link has been sent")


class LoginLinkRedeemTests(TestCase):
    def setUp(self):
        self.member = make_member()
        self.user = create_member_user(self.member)
        self.user.set_password("Str0ngP@ss!")
        self.user.save()

    def _get(self, token):
        return self.client.get(reverse("member-login-link", kwargs={"token": token}))

    def _post(self, token):
        return self.client.post(reverse("member-login-link", kwargs={"token": token}))

    def test_get_renders_interstitial_without_logging_in(self):
        """GET (as issued by email scanners) must not consume the token or log in."""
        token = make_login_link_token(self.user)
        response = self._get(token)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Continue to log in")
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_get_interstitial_has_post_form_with_csrf(self):
        token = make_login_link_token(self.user)
        response = self._get(token)
        self.assertContains(response, 'id="login-continue-form"')
        self.assertContains(response, 'method="post"')
        self.assertContains(response, "csrfmiddlewaretoken")

    def test_post_valid_token_logs_in_and_redirects(self):
        token = make_login_link_token(self.user)
        response = self._post(token)
        self.assertRedirects(response, "/member/profile/", fetch_redirect_response=False)
        self.assertEqual(int(self.client.session["_auth_user_id"]), self.user.pk)

    def test_scanner_get_then_human_get_post_still_works(self):
        """A scanner GET (or several) must not stop the human's GET + POST."""
        token = make_login_link_token(self.user)
        self._get(token)  # scanner prefetch
        self._get(token)  # another scanner / human page load
        response = self._post(token)
        self.assertRedirects(response, "/member/profile/", fetch_redirect_response=False)
        self.assertEqual(int(self.client.session["_auth_user_id"]), self.user.pk)

    def test_garbage_token_rejected(self):
        for response in (self._get("not-a-real-token"), self._post("not-a-real-token")):
            self.assertEqual(response.status_code, 200)
            self.assertContains(response, "invalid or expired")
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_tampered_token_rejected(self):
        token = make_login_link_token(self.user)
        for response in (self._get(token[:-3] + "abc"), self._post(token[:-3] + "abc")):
            self.assertContains(response, "invalid or expired")
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_expired_token_rejected(self):
        token = make_login_link_token(self.user)
        with patch.object(members_auth, "LOGIN_LINK_MAX_AGE", -1):
            for response in (self._get(token), self._post(token)):
                self.assertContains(response, "invalid or expired")
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_token_single_use_after_post(self):
        """Logging in updates last_login, invalidating the outstanding token."""
        token = make_login_link_token(self.user)
        first = self._post(token)
        self.assertRedirects(first, "/member/profile/", fetch_redirect_response=False)
        self.client.logout()
        for response in (self._get(token), self._post(token)):
            self.assertContains(response, "invalid or expired")
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_token_invalid_after_password_login(self):
        """Any subsequent login (e.g. with a password) invalidates the token."""
        token = make_login_link_token(self.user)
        self.client.login(username="sam@example.com", password="Str0ngP@ss!")
        self.client.logout()
        response = self._post(token)
        self.assertContains(response, "invalid or expired")

    def test_inactive_user_rejected(self):
        token = make_login_link_token(self.user)
        self.user.is_active = False
        self.user.save(update_fields=["is_active"])
        for response in (self._get(token), self._post(token)):
            self.assertContains(response, "invalid or expired")
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_user_without_member_rejected(self):
        orphan = User.objects.create_user(
            username="orphan@example.com", email="orphan@example.com", password="x"
        )
        token = make_login_link_token(orphan)
        for response in (self._get(token), self._post(token)):
            self.assertContains(response, "invalid or expired")
        self.assertNotIn("_auth_user_id", self.client.session)
