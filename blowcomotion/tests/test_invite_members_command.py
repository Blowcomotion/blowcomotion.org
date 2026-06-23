from io import StringIO
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import TestCase

from blowcomotion.member_auth import create_member_user
from blowcomotion.models import Member

User = get_user_model()


def make_member(email, active=True, **kwargs):
    return Member.objects.create(
        first_name="Test", last_name="Member", email=email, is_active=active, **kwargs
    )


patch_email = patch("blowcomotion.management.commands.invite_members.send_set_password_email")


class InviteMembersCommandTests(TestCase):
    @patch_email
    def test_invites_active_members_without_user(self, mock_email):
        m = make_member("invite1@example.com")
        out = StringIO()
        call_command("invite_members", stdout=out)
        mock_email.assert_called_once()
        m.refresh_from_db()
        self.assertIsNotNone(m.user_id)

    @patch_email
    def test_skips_members_with_existing_user(self, mock_email):
        m = make_member("existing@example.com")
        create_member_user(m)
        out = StringIO()
        call_command("invite_members", stdout=out)
        mock_email.assert_not_called()

    @patch_email
    def test_skips_inactive_members(self, mock_email):
        make_member("inactive@example.com", active=False)
        call_command("invite_members", stdout=StringIO())
        mock_email.assert_not_called()

    @patch_email
    def test_dry_run_sends_no_emails_creates_no_users(self, mock_email):
        m = make_member("dryrun@example.com")
        out = StringIO()
        call_command("invite_members", "--dry-run", stdout=out)
        mock_email.assert_not_called()
        m.refresh_from_db()
        self.assertIsNone(m.user_id)
        self.assertIn("dryrun@example.com", out.getvalue())

    @patch_email
    def test_member_id_flag_processes_single_member(self, mock_email):
        m1 = make_member("single1@example.com")
        m2 = make_member("single2@example.com")
        call_command("invite_members", f"--member-id={m1.pk}", stdout=StringIO())
        mock_email.assert_called_once()
        m2.refresh_from_db()
        self.assertIsNone(m2.user_id)

    @patch_email
    def test_error_on_one_member_does_not_abort_rest(self, mock_email):
        m1 = make_member("fail@example.com")
        m2 = make_member("ok@example.com")

        call_count = [0]
        def email_side_effect(member, base_url):
            call_count[0] += 1
            if member.email == "fail@example.com":
                raise Exception("SMTP error")
        mock_email.side_effect = email_side_effect

        out = StringIO()
        call_command("invite_members", stdout=out)
        self.assertEqual(call_count[0], 2)

    @patch_email
    def test_logs_summary(self, mock_email):
        make_member("a@example.com")
        make_member("b@example.com")
        out = StringIO()
        call_command("invite_members", stdout=out)
        output = out.getvalue()
        self.assertIn("invited", output.lower())
