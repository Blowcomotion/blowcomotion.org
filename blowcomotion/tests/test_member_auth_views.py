from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse

from blowcomotion.member_auth import create_member_user
from blowcomotion.models import Member, PasswordSetToken

User = get_user_model()


def make_member(**kwargs):
    defaults = dict(first_name="Sam", last_name="Player", email="sam@example.com")
    defaults.update(kwargs)
    return Member.objects.create(**defaults)


# Patch reCAPTCHA to always pass in tests
recaptcha_pass = patch(
    "blowcomotion.member_views._validate_recaptcha", return_value=(True, None)
)


class LoginViewTests(TestCase):
    def setUp(self):
        self.member = make_member()
        self.user = create_member_user(self.member)
        self.user.set_password("Str0ngP@ss!")
        self.user.save()

    def test_login_page_renders(self):
        response = self.client.get(reverse("member-login"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "form")

    @recaptcha_pass
    def test_valid_login_redirects_to_profile(self, mock_recaptcha):
        response = self.client.post(
            reverse("member-login"),
            {"username": "sam@example.com", "password": "Str0ngP@ss!", "best_color": "purple"},
        )
        self.assertRedirects(response, "/member/profile/", fetch_redirect_response=False)

    def test_honeypot_filled_redirects_silently(self):
        response = self.client.post(
            reverse("member-login"),
            {"username": "sam@example.com", "password": "x", "best_color": "red"},
        )
        self.assertEqual(response.status_code, 302)

    def test_recaptcha_fail_stays_on_login(self):
        with patch(
            "blowcomotion.member_views._validate_recaptcha",
            return_value=(False, "reCAPTCHA failed"),
        ):
            response = self.client.post(
                reverse("member-login"),
                {"username": "sam@example.com", "password": "Str0ngP@ss!", "best_color": "purple"},
            )
        self.assertEqual(response.status_code, 200)


class SetPasswordViewTests(TestCase):
    def setUp(self):
        self.member = make_member()
        self.user = create_member_user(self.member)

    def _make_token(self):
        return PasswordSetToken.objects.create(member=self.member)

    def test_valid_token_renders_form(self):
        token = self._make_token()
        response = self.client.get(
            reverse("member-set-password", kwargs={"token_uuid": token.uuid})
        )
        self.assertEqual(response.status_code, 200)

    def test_used_token_returns_404(self):
        token = self._make_token()
        token.used = True
        token.save()
        response = self.client.get(
            reverse("member-set-password", kwargs={"token_uuid": token.uuid})
        )
        self.assertEqual(response.status_code, 404)

    def test_superseded_token_returns_404(self):
        token = self._make_token()
        token.superseded = True
        token.save()
        response = self.client.get(
            reverse("member-set-password", kwargs={"token_uuid": token.uuid})
        )
        self.assertEqual(response.status_code, 404)

    def test_expired_token_shows_expired_message(self):
        from datetime import timedelta

        from django.utils import timezone
        token = self._make_token()
        PasswordSetToken.objects.filter(pk=token.pk).update(
            created_at=timezone.now() - timedelta(hours=25)
        )
        response = self.client.get(
            reverse("member-set-password", kwargs={"token_uuid": token.uuid})
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "expired")

    @recaptcha_pass
    def test_valid_submission_logs_in_user(self, mock_recaptcha):
        token = self._make_token()
        response = self.client.post(
            reverse("member-set-password", kwargs={"token_uuid": token.uuid}),
            {"new_password1": "NewStr0ng@Pass!", "new_password2": "NewStr0ng@Pass!", "best_color": "purple"},
        )
        self.assertRedirects(response, "/member/profile/", fetch_redirect_response=False)
        token.refresh_from_db()
        self.assertTrue(token.used)


@override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
                   FROM_EMAIL="noreply@blowcomotion.org")
class GetAccessViewTests(TestCase):
    def test_get_renders_form(self):
        response = self.client.get(reverse("member-get-access"))
        self.assertEqual(response.status_code, 200)

    @recaptcha_pass
    def test_unknown_email_shows_generic_response(self, mock_recaptcha):
        response = self.client.post(
            reverse("member-get-access"), {"email": "nobody@example.com", "best_color": "purple"}
        )
        self.assertEqual(response.status_code, 200)
        from django.core import mail
        self.assertEqual(len(mail.outbox), 0)

    @recaptcha_pass
    def test_member_without_user_creates_account_and_sends_email(self, mock_recaptcha):
        make_member(email="newbie@example.com")
        response = self.client.post(
            reverse("member-get-access"), {"email": "newbie@example.com", "best_color": "purple"}
        )
        self.assertEqual(response.status_code, 200)
        from django.core import mail
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn("/member/set-password/", mail.outbox[0].body)

    @recaptcha_pass
    def test_member_with_user_sends_reset_email(self, mock_recaptcha):
        from django.core import mail
        member = make_member(email="existing@example.com")
        user = create_member_user(member)
        user.set_password("SomePass123!")
        user.save()
        response = self.client.post(
            reverse("member-get-access"), {"email": "existing@example.com", "best_color": "purple"}
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(mail.outbox), 1)
