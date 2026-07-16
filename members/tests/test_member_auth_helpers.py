from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings

from blowcomotion.models import EmailChangeToken, Member, PasswordSetToken
from members.auth import create_member_user

User = get_user_model()


def make_member(**kwargs):
    defaults = dict(first_name="Jane", last_name="Player", email="jane@example.com")
    defaults.update(kwargs)
    return Member.objects.create(**defaults)


class MemberUserFieldTests(TestCase):
    def test_member_gets_user_on_save(self):
        """Saving a member materializes the buffered name/email into a linked User."""
        m = make_member()
        self.assertIsNotNone(m.user)
        self.assertEqual(m.user.first_name, "Jane")
        self.assertEqual(m.user.last_name, "Player")
        self.assertEqual(m.user.email, "jane@example.com")
        self.assertEqual(m.user.username, "jane@example.com")
        self.assertFalse(m.user.has_usable_password())

    def test_does_not_adopt_preexisting_unlinked_user_with_matching_username(self):
        """Security: a brand-new member must never adopt a pre-existing auth
        User just because its username matches the member's email — that
        account (e.g. staff with no Member row) could belong to someone else.
        A separate User is created instead, and the existing one is left
        untouched."""
        u = User.objects.create_user(
            username="jane@example.com", email="jane@example.com",
            first_name="Existing", last_name="Staffer", is_staff=True,
        )
        m = make_member()
        m.refresh_from_db()
        self.assertNotEqual(m.user_id, u.pk)
        u.refresh_from_db()
        self.assertEqual(u.first_name, "Existing")
        self.assertEqual(u.last_name, "Staffer")
        self.assertEqual(u.username, "jane@example.com")
        # The new member gets its own account, suffixed to avoid the collision.
        self.assertNotEqual(m.user.username, "jane@example.com")
        self.assertEqual(m.user.first_name, "Jane")

    def test_member_delegates_name_and_email_to_user(self):
        m = make_member()
        m.user.first_name = "Janet"
        self.assertEqual(m.first_name, "Janet")
        self.assertEqual(m.email, "jane@example.com")

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
        user = member.user

        member.email = "new@example.com"
        member.save(sync_go3=False)

        user.refresh_from_db()
        self.assertEqual(user.email, "new@example.com")
        self.assertEqual(user.username, "new@example.com")

    def test_no_user_linked_creates_user_on_save(self):
        """If the member has no linked User, an email assignment plus save
        materializes a fresh User."""
        member = make_member(email="solo@example.com")
        # Member.user is on_delete=PROTECT, so the User must be unlinked
        # before it can be deleted.
        orphan_user = member.user
        member.user = None
        member.save(sync_go3=False)
        orphan_user.delete()
        member = Member.objects.get(pk=member.pk)
        member.email = "changed@example.com"
        member.save(sync_go3=False)
        self.assertIsNotNone(member.user)
        self.assertEqual(member.user.email, "changed@example.com")

    def test_username_not_stolen_from_other_account(self):
        """Changing a member's email to one whose username belongs to another
        account updates the email but leaves both usernames untouched."""
        other = User.objects.create_user(username="taken@example.com", email="taken@example.com")
        member = make_member(email="mine@example.com")
        member.email = "taken@example.com"
        member.save(sync_go3=False)
        member.user.refresh_from_db()
        other.refresh_from_db()
        self.assertEqual(member.user.email, "taken@example.com")
        self.assertEqual(member.user.username, "mine@example.com")
        self.assertEqual(other.username, "taken@example.com")

    @override_settings(GIGO_API_URL="http://fake-go3.example.com", GIGO_API_KEY="testkey")
    def test_email_drift_guard_fires_with_go3_configured(self):
        """Regression: verify email drift guard fires when sync_go3=True (default)
        and GO3 is configured. Without this, the guard only runs in the sync_go3=False
        path. The guard is placed before the GO3 verification block so it runs
        correctly even though the GO3 block later clobbers the update_fields local."""
        member = make_member(email="old@example.com")
        user = member.user

        # GO3 returns a valid member_id — this is what triggers the clobber:
        # update_fields = [] inside the if-branch, then gigo fields appended.
        go3_response = {"member_id": 12345, "username": "oldplayer"}
        with patch("gigs.gigo.make_gigo_api_request", return_value=go3_response):
            member.email = "new@example.com"
            member.save()  # sync_go3=True (default)

        user.refresh_from_db()
        self.assertEqual(user.email, "new@example.com")
        self.assertEqual(user.username, "new@example.com")

    def test_full_save_syncs_user_email(self):
        """Email writes through to the User on a full save (update_fields=None)."""
        member = make_member(email="full@example.com")
        user = member.user

        member.email = "fullnew@example.com"
        member.save(sync_go3=False)  # full save, no update_fields

        user.refresh_from_db()
        self.assertEqual(user.email, "fullnew@example.com")
        self.assertEqual(user.username, "fullnew@example.com")


from members.auth import (
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

    def test_member_with_no_email_gets_name_derived_user(self):
        """A member saved without an email gets a User with a name-derived
        username, so create_member_user returns it rather than raising."""
        member = Member.objects.create(first_name="No", last_name="Email")
        self.assertIsNotNone(member.user)
        self.assertEqual(member.user.username, "no-email")
        self.assertEqual(member.user.email, "")
        result = create_member_user(member)
        self.assertEqual(result.pk, member.user.pk)

    def test_links_existing_user_when_email_already_taken(self):
        existing = User.objects.create_user(username="taken@example.com", email="taken@example.com")
        # A member with no linked User yet and a buffered (unsaved) email —
        # Member.save() always mints its own fresh User once an email is
        # assigned normally, so to exercise create_member_user's own
        # "link a pre-existing matching account" logic in isolation we have
        # to construct that not-yet-materialized state directly.
        member = Member.objects.create(is_active=True)
        member._pending_user_fields["email"] = "taken@example.com"
        result = create_member_user(member)
        self.assertEqual(result, existing)
        member.refresh_from_db()
        self.assertEqual(member.user_id, existing.pk)
        self.assertEqual(User.objects.filter(username="taken@example.com").count(), 1)

    def test_syncs_email_field_when_linking_existing_user_with_stale_email(self):
        existing = User.objects.create_user(username="stale@example.com", email="")
        member = Member.objects.create(is_active=True)
        member._pending_user_fields["email"] = "stale@example.com"
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

    def test_sends_email_to_member(self):
        from django.core import mail
        send_set_password_email(self.member, "http://testserver")
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn("invite@example.com", mail.outbox[0].to)

    def test_email_contains_set_password_link(self):
        from django.core import mail
        send_set_password_email(self.member, "http://testserver")
        self.assertIn("/member/set-password/", mail.outbox[0].body)

    def test_creates_password_set_token(self):
        send_set_password_email(self.member, "http://testserver")
        self.assertEqual(
            PasswordSetToken.objects.filter(member=self.member, used=False, superseded=False).count(), 1
        )

    def test_supersedes_prior_tokens(self):
        token_old = PasswordSetToken.objects.create(member=self.member)
        send_set_password_email(self.member, "http://testserver")
        token_old.refresh_from_db()
        self.assertTrue(token_old.superseded)

    def test_set_password_email_url_not_qp_wrapped(self):
        from django.core import mail
        send_set_password_email(self.member, "https://www.blowcomotion.org")
        raw = mail.outbox[0].message().as_string()
        self.assertNotIn("=\n", raw)


@override_settings(
    EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
    FROM_EMAIL="noreply@blowcomotion.org",
)
class SendEmailChangeConfirmationTests(TestCase):
    def setUp(self):
        self.member = make_member(email="original@example.com")

    def test_sends_email_to_new_address(self):
        from django.core import mail
        send_email_change_confirmation(self.member, "newemail@example.com", "http://testserver")
        self.assertIn("newemail@example.com", mail.outbox[0].to)

    def test_email_contains_confirm_link(self):
        from django.core import mail
        send_email_change_confirmation(self.member, "newemail@example.com", "http://testserver")
        self.assertIn("/member/confirm-email/", mail.outbox[0].body)

    def test_email_change_confirmation_url_not_qp_wrapped(self):
        from django.core import mail
        send_email_change_confirmation(self.member, "newemail@example.com", "https://www.blowcomotion.org")
        raw = mail.outbox[0].message().as_string()
        self.assertNotIn("=\n", raw)

    def test_sets_pending_email_on_member(self):
        send_email_change_confirmation(self.member, "newemail@example.com", "http://testserver")
        self.member.refresh_from_db()
        self.assertEqual(self.member.pending_email, "newemail@example.com")


