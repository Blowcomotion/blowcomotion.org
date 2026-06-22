import uuid
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from blowcomotion.models import EmailChangeToken, Member, PasswordSetToken, Section

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
