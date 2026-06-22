from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import RequestFactory, TestCase, override_settings

from blowcomotion.member_auth import create_member_user
from blowcomotion.models import EmailChangeToken, Member, PasswordSetToken

User = get_user_model()


def make_member(**kwargs):
    defaults = dict(first_name="Jane", last_name="Player", email="jane@example.com")
    defaults.update(kwargs)
    return Member.objects.create(**defaults)


class MemberUserFieldTests(TestCase):
    def test_member_has_no_user_by_default(self):
        m = make_member()
        self.assertIsNone(m.user)

    def test_member_can_link_user(self):
        m = make_member()
        u = User.objects.create_user(username="jane@example.com", email="jane@example.com")
        m.user = u
        m.save(update_fields=["user"], sync_go3=False)
        m.refresh_from_db()
        self.assertEqual(m.user_id, u.pk)

    def test_notify_fields_default_true(self):
        m = make_member()
        self.assertTrue(m.notify_rental_updates)
        self.assertTrue(m.notify_reminders)
        self.assertTrue(m.notify_announcements)

    def test_pending_email_default_null(self):
        m = make_member()
        self.assertIsNone(m.pending_email)


class PasswordSetTokenTests(TestCase):
    def setUp(self):
        self.member = make_member()

    def test_token_created_with_defaults(self):
        token = PasswordSetToken.objects.create(member=self.member)
        self.assertFalse(token.used)
        self.assertFalse(token.superseded)
        self.assertIsNotNone(token.uuid)

    def test_token_uuid_is_unique(self):
        t1 = PasswordSetToken.objects.create(member=self.member)
        t2 = PasswordSetToken.objects.create(member=self.member)
        self.assertNotEqual(t1.uuid, t2.uuid)

    def test_used_token_can_be_marked(self):
        token = PasswordSetToken.objects.create(member=self.member)
        token.used = True
        token.save()
        token.refresh_from_db()
        self.assertTrue(token.used)

    def test_superseded_token_can_be_marked(self):
        token = PasswordSetToken.objects.create(member=self.member)
        token.superseded = True
        token.save()
        token.refresh_from_db()
        self.assertTrue(token.superseded)


class EmailChangeTokenTests(TestCase):
    def setUp(self):
        self.member = make_member()

    def test_token_stores_new_email(self):
        token = EmailChangeToken.objects.create(
            member=self.member, new_email="new@example.com"
        )
        self.assertEqual(token.new_email, "new@example.com")
        self.assertFalse(token.used)

    def test_token_uuid_is_unique(self):
        t1 = EmailChangeToken.objects.create(member=self.member, new_email="a@example.com")
        t2 = EmailChangeToken.objects.create(member=self.member, new_email="b@example.com")
        self.assertNotEqual(t1.uuid, t2.uuid)


class MemberSaveEmailDriftTests(TestCase):
    def test_admin_email_change_syncs_user(self):
        member = make_member(email="old@example.com")
        user = User.objects.create_user(
            username="old@example.com", email="old@example.com"
        )
        member.user = user
        member.save(update_fields=["user"], sync_go3=False)

        member.email = "new@example.com"
        member.save(update_fields=["email"], sync_go3=False)

        user.refresh_from_db()
        self.assertEqual(user.email, "new@example.com")
        self.assertEqual(user.username, "new@example.com")

    def test_no_user_linked_no_error(self):
        member = make_member(email="solo@example.com")
        member.email = "changed@example.com"
        member.save(update_fields=["email"], sync_go3=False)  # should not raise

    @override_settings(GIGO_API_URL="http://fake-go3.example.com", GIGO_API_KEY="testkey")
    def test_email_drift_guard_fires_with_go3_configured(self):
        """Regression: verify email drift guard fires when sync_go3=True (default)
        and GO3 is configured. Without this, the guard only runs in the sync_go3=False
        path. The guard is placed before the GO3 verification block so it runs
        correctly even though the GO3 block later clobbers the update_fields local."""
        member = make_member(email="old@example.com")
        user = User.objects.create_user(
            username="old@example.com", email="old@example.com"
        )
        member.user = user
        member.save(update_fields=["user"], sync_go3=False)

        # GO3 returns a valid member_id — this is what triggers the clobber:
        # update_fields = [] inside the if-branch, then gigo fields appended.
        go3_response = {"member_id": 12345, "username": "oldplayer"}
        with patch("blowcomotion.utils.make_gigo_api_request", return_value=go3_response):
            member.email = "new@example.com"
            member.save(update_fields=["email"])  # sync_go3=True (default)

        user.refresh_from_db()
        self.assertEqual(user.email, "new@example.com")
        self.assertEqual(user.username, "new@example.com")

    def test_full_save_syncs_user_email(self):
        """Email drift guard fires on a full save (update_fields=None)."""
        member = make_member(email="full@example.com")
        user = User.objects.create_user(
            username="full@example.com", email="full@example.com"
        )
        member.user = user
        member.save(update_fields=["user"], sync_go3=False)

        member.email = "fullnew@example.com"
        member.save(sync_go3=False)  # full save, no update_fields

        user.refresh_from_db()
        self.assertEqual(user.email, "fullnew@example.com")
        self.assertEqual(user.username, "fullnew@example.com")


from blowcomotion.member_auth import (
    create_member_user,
    send_email_change_confirmation,
    send_set_password_email,
)


class CreateMemberUserTests(TestCase):
    def setUp(self):
        self.member = make_member(email="test@example.com")

    def test_creates_user_with_unusable_password(self):
        user = create_member_user(self.member)
        self.assertFalse(user.has_usable_password())

    def test_sets_username_and_email_from_member_email(self):
        user = create_member_user(self.member)
        self.assertEqual(user.username, "test@example.com")
        self.assertEqual(user.email, "test@example.com")

    def test_links_user_to_member(self):
        user = create_member_user(self.member)
        self.member.refresh_from_db()
        self.assertEqual(self.member.user_id, user.pk)

    def test_returns_existing_user_if_already_linked(self):
        user1 = create_member_user(self.member)
        user2 = create_member_user(self.member)
        self.assertEqual(user1.pk, user2.pk)
        self.assertEqual(User.objects.filter(email="test@example.com").count(), 1)

    def test_raises_for_member_with_no_email(self):
        member = Member.objects.create(first_name="No", last_name="Email")
        with self.assertRaises(ValueError):
            create_member_user(member)

    def test_links_existing_user_when_email_already_taken(self):
        existing = User.objects.create_user(username="taken@example.com", email="taken@example.com")
        member = Member.objects.create(first_name="Ex", last_name="Isting", email="taken@example.com")
        result = create_member_user(member)
        self.assertEqual(result, existing)
        member.refresh_from_db()
        self.assertEqual(member.user_id, existing.pk)
        self.assertEqual(User.objects.filter(username="taken@example.com").count(), 1)

    def test_syncs_email_field_when_linking_existing_user_with_stale_email(self):
        existing = User.objects.create_user(username="stale@example.com", email="")
        member = Member.objects.create(first_name="St", last_name="Ale", email="stale@example.com")
        create_member_user(member)
        existing.refresh_from_db()
        self.assertEqual(existing.email, "stale@example.com")


@override_settings(
    EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
    FROM_EMAIL="noreply@blowcomotion.org",
)
class SendSetPasswordEmailTests(TestCase):
    def setUp(self):
        self.member = make_member(email="invite@example.com")
        create_member_user(self.member)
        self.factory = RequestFactory()

    def test_sends_email_to_member(self):
        from django.core import mail
        request = self.factory.get("/")
        request.META["SERVER_NAME"] = "testserver"
        request.META["SERVER_PORT"] = "80"
        send_set_password_email(self.member, request)
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn("invite@example.com", mail.outbox[0].to)

    def test_email_contains_set_password_link(self):
        from django.core import mail
        request = self.factory.get("/")
        request.META["SERVER_NAME"] = "testserver"
        request.META["SERVER_PORT"] = "80"
        send_set_password_email(self.member, request)
        self.assertIn("/member/set-password/", mail.outbox[0].body)

    def test_creates_password_set_token(self):
        request = self.factory.get("/")
        request.META["SERVER_NAME"] = "testserver"
        request.META["SERVER_PORT"] = "80"
        send_set_password_email(self.member, request)
        self.assertEqual(
            PasswordSetToken.objects.filter(member=self.member, used=False, superseded=False).count(), 1
        )

    def test_supersedes_prior_tokens(self):
        token_old = PasswordSetToken.objects.create(member=self.member)
        request = self.factory.get("/")
        request.META["SERVER_NAME"] = "testserver"
        request.META["SERVER_PORT"] = "80"
        send_set_password_email(self.member, request)
        token_old.refresh_from_db()
        self.assertTrue(token_old.superseded)


@override_settings(
    EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
    FROM_EMAIL="noreply@blowcomotion.org",
)
class SendEmailChangeConfirmationTests(TestCase):
    def setUp(self):
        self.member = make_member(email="original@example.com")
        self.factory = RequestFactory()

    def test_sends_email_to_new_address(self):
        from django.core import mail
        request = self.factory.get("/")
        request.META["SERVER_NAME"] = "testserver"
        request.META["SERVER_PORT"] = "80"
        send_email_change_confirmation(self.member, "newemail@example.com", request)
        self.assertIn("newemail@example.com", mail.outbox[0].to)

    def test_email_contains_confirm_link(self):
        from django.core import mail
        request = self.factory.get("/")
        request.META["SERVER_NAME"] = "testserver"
        request.META["SERVER_PORT"] = "80"
        send_email_change_confirmation(self.member, "newemail@example.com", request)
        self.assertIn("/member/confirm-email/", mail.outbox[0].body)

    def test_sets_pending_email_on_member(self):
        request = self.factory.get("/")
        request.META["SERVER_NAME"] = "testserver"
        request.META["SERVER_PORT"] = "80"
        send_email_change_confirmation(self.member, "newemail@example.com", request)
        self.member.refresh_from_db()
        self.assertEqual(self.member.pending_email, "newemail@example.com")


