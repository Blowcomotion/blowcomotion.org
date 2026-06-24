from unittest.mock import patch

from wagtail.models import Revision

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from blowcomotion.member_auth import create_member_user
from blowcomotion.models import EmailChangeToken, Member

User = get_user_model()


def make_member(**kwargs):
    defaults = dict(first_name="Robin", last_name="Player", email="robin@example.com")
    defaults.update(kwargs)
    return Member.objects.create(**defaults)


class PortalAuthGateTests(TestCase):
    def test_staff_user_without_member_profile_redirects(self):
        staff = User.objects.create_user(username="staff@example.com", password="StaffP@ss!")
        self.client.login(username="staff@example.com", password="StaffP@ss!")
        response = self.client.get(reverse("member-profile"))
        self.assertEqual(response.status_code, 302)

    def test_staff_user_without_member_requests_redirects(self):
        staff = User.objects.create_user(username="staff2@example.com", password="StaffP@ss!")
        self.client.login(username="staff2@example.com", password="StaffP@ss!")
        response = self.client.get(reverse("member-requests"))
        self.assertEqual(response.status_code, 302)

    def test_profile_redirects_anonymous_to_login(self):
        response = self.client.get(reverse("member-profile"))
        self.assertRedirects(
            response,
            "/member/login/?next=/member/profile/",
            fetch_redirect_response=False,
        )

    def test_requests_redirects_anonymous_to_login(self):
        response = self.client.get(reverse("member-requests"))
        self.assertRedirects(
            response,
            "/member/login/?next=/member/requests/",
            fetch_redirect_response=False,
        )


class ProfileViewTests(TestCase):
    def setUp(self):
        self.member = make_member()
        self.user = create_member_user(self.member)
        self.user.set_password("Pass123!")
        self.user.save()
        self.client.login(username="robin@example.com", password="Pass123!")
        self._recaptcha = patch(
            "blowcomotion.member_views._validate_recaptcha", return_value=(True, None)
        )
        self._recaptcha.start()

    def tearDown(self):
        self._recaptcha.stop()

    def test_profile_page_renders(self):
        response = self.client.get(reverse("member-profile"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Robin")

    def test_profile_saves_name_change(self):
        response = self.client.post(
            reverse("member-profile"),
            {
                "first_name": "Robin",
                "last_name": "Player",
                "preferred_name": "Robbie",
                "email": "robin@example.com",
                "notify_rental_updates": True,
                "notify_reminders": True,
                "notify_announcements": True,
            },
            follow=True,
        )
        self.assertEqual(response.status_code, 200)
        self.member.refresh_from_db()
        self.assertEqual(self.member.preferred_name, "Robbie")

    def test_email_change_sets_pending_email(self):
        from django.test import override_settings
        with override_settings(
            EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
            FROM_EMAIL="noreply@blowcomotion.org",
        ):
            self.client.post(
                reverse("member-profile"),
                {
                    "first_name": "Robin",
                    "last_name": "Player",
                    "email": "newemail@example.com",
                    "notify_rental_updates": True,
                    "notify_reminders": True,
                    "notify_announcements": True,
                },
            )
        self.member.refresh_from_db()
        self.assertEqual(self.member.pending_email, "newemail@example.com")
        self.assertEqual(self.member.email, "robin@example.com")  # unchanged until confirmed

    def test_profile_post_with_recaptcha_failure_returns_error(self):
        self._recaptcha.stop()
        with patch(
            "blowcomotion.member_views._validate_recaptcha",
            return_value=(False, "reCAPTCHA failed"),
        ):
            response = self.client.post(
                reverse("member-profile"),
                {"first_name": "Robin", "last_name": "Player", "email": "robin@example.com"},
            )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["recaptcha_error"], "reCAPTCHA failed")
        self.assertContains(response, "reCAPTCHA failed")

    def test_profile_recaptcha_failure_preserves_submitted_input(self):
        self._recaptcha.stop()
        with patch(
            "blowcomotion.member_views._validate_recaptcha",
            return_value=(False, "reCAPTCHA failed"),
        ):
            response = self.client.post(
                reverse("member-profile"),
                {"first_name": "Changed", "last_name": "Player", "email": "robin@example.com"},
            )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["form"]["first_name"].value(), "Changed")

    def test_email_unchanged_does_not_send_confirmation(self):
        from django.core import mail
        with self.settings(
            EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
            FROM_EMAIL="noreply@blowcomotion.org",
        ):
            self.client.post(
                reverse("member-profile"),
                {
                    "first_name": "Robin",
                    "last_name": "Player",
                    "email": "robin@example.com",  # same email
                    "notify_rental_updates": True,
                    "notify_reminders": True,
                    "notify_announcements": True,
                },
            )
        self.assertEqual(len(mail.outbox), 0)

    def test_profile_save_creates_revision(self):
        self.client.post(
            reverse("member-profile"),
            {
                "first_name": "Robin",
                "last_name": "Player",
                "preferred_name": "Robbie",
                "email": "robin@example.com",
                "notify_rental_updates": True,
                "notify_reminders": True,
                "notify_announcements": True,
            },
        )
        self.assertEqual(Revision.objects.for_instance(self.member).count(), 1)
        revision = Revision.objects.for_instance(self.member).first()
        self.assertEqual(revision.user, self.user)
        self.assertIn("Robbie", revision.content.get("preferred_name", ""))


class ConfirmEmailViewTests(TestCase):
    def setUp(self):
        self.member = make_member()
        self.user = create_member_user(self.member)
        self.user.set_password("Pass123!")
        self.user.save()

    def test_valid_token_updates_email(self):
        from datetime import timedelta

        from django.utils import timezone
        token = EmailChangeToken.objects.create(
            member=self.member, new_email="confirmed@example.com"
        )
        response = self.client.get(
            reverse("member-confirm-email", kwargs={"token_uuid": token.uuid})
        )
        self.assertEqual(response.status_code, 200)
        self.member.refresh_from_db()
        self.assertEqual(self.member.email, "confirmed@example.com")
        self.assertIsNone(self.member.pending_email)
        token.refresh_from_db()
        self.assertTrue(token.used)
        self.user.refresh_from_db()
        self.assertEqual(self.user.email, "confirmed@example.com")
        self.assertEqual(self.user.username, "confirmed@example.com")

    def test_used_token_shows_error(self):
        token = EmailChangeToken.objects.create(
            member=self.member, new_email="x@example.com", used=True
        )
        response = self.client.get(
            reverse("member-confirm-email", kwargs={"token_uuid": token.uuid})
        )
        self.assertContains(response, "invalid")

    def test_expired_token_shows_error(self):
        from datetime import timedelta

        from django.utils import timezone
        token = EmailChangeToken.objects.create(
            member=self.member, new_email="x@example.com"
        )
        EmailChangeToken.objects.filter(pk=token.pk).update(
            created_at=timezone.now() - timedelta(hours=25)
        )
        response = self.client.get(
            reverse("member-confirm-email", kwargs={"token_uuid": token.uuid})
        )
        self.assertContains(response, "expired")


class RequestsStubTests(TestCase):
    def setUp(self):
        member = make_member()
        user = create_member_user(member)
        user.set_password("Pass123!")
        user.save()
        self.client.login(username="robin@example.com", password="Pass123!")

    def test_requests_page_renders(self):
        response = self.client.get(reverse("member-requests"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Coming soon")
