import datetime
from io import StringIO

from wagtail.models import Site

from django.core.management import call_command
from django.test import TestCase, override_settings

from blowcomotion.models import (
    AttendanceRecord,
    Instrument,
    Member,
    Section,
    SiteSettings,
)

# Get today's weekday for tests
TODAY_WEEKDAY = datetime.date.today().weekday()


class CleanupAttendanceRosterCommandTest(TestCase):
    """Tests for the cleanup_attendance_roster management command."""

    def setUp(self):
        """Set up test data."""
        # Create a site and settings
        self.site = Site.objects.get(is_default_site=True)
        self.settings = SiteSettings.for_site(self.site)
        self.settings.attendance_cleanup_days = 90
        self.settings.save()

        # Create a section and instrument
        self.section = Section.objects.create(name="Test Section")
        self.instrument = Instrument.objects.create(name="Test Instrument", section=self.section)

        # Create test members
        self.old_member = Member.objects.create(
            first_name="Old",
            last_name="Member",
            primary_instrument=self.instrument,
            is_active=True,
            last_seen=datetime.date.today() - datetime.timedelta(days=100),
        )

        self.recent_member = Member.objects.create(
            first_name="Recent",
            last_name="Member",
            primary_instrument=self.instrument,
            is_active=True,
            last_seen=datetime.date.today() - datetime.timedelta(days=30),
        )

    def test_cleanup_marks_inactive(self):
        """Test that inactive members are correctly identified and marked."""
        out = StringIO()
        call_command("cleanup_attendance_roster", f"--day-to-run={TODAY_WEEKDAY}", stdout=out)
        
        # Refresh member from database
        self.old_member.refresh_from_db()
        self.recent_member.refresh_from_db()

        # Old member should be marked inactive
        self.assertFalse(self.old_member.is_active)
        # Recent member should remain active
        self.assertTrue(self.recent_member.is_active)

    def test_cleanup_dry_run(self):
        """Test that --dry-run doesn't actually mark members inactive."""
        out = StringIO()
        call_command("cleanup_attendance_roster", "--dry-run", f"--day-to-run={TODAY_WEEKDAY}", stdout=out)

        # Refresh member from database
        self.old_member.refresh_from_db()
        # Member should still be active (dry run)
        self.assertTrue(self.old_member.is_active)

    def test_cleanup_respects_day_to_run(self):
        """Test that command skips execution if not on the correct day."""
        out = StringIO()
        # Command should skip if not on specified day (use a different day)
        different_day = (TODAY_WEEKDAY + 1) % 7
        call_command("cleanup_attendance_roster", f"--day-to-run={different_day}", stdout=out)
        
        # Command should have exited early
        output = out.getvalue()
        self.assertIn("only", output)  # Should mention day restriction


class SendAttendanceReportCommandTest(TestCase):
    """Tests for the send_attendance_report management command."""

    def setUp(self):
        """Set up test data."""
        # Create a site and settings
        self.site = Site.objects.get(is_default_site=True)
        self.settings = SiteSettings.for_site(self.site)
        self.settings.attendance_report_notification_recipients = "test@example.com"
        self.settings.save()

        # Create sections and instruments
        self.section1 = Section.objects.create(name="Woodwinds")
        self.section2 = Section.objects.create(name="Brass")

        self.instrument1 = Instrument.objects.create(name="Clarinet", section=self.section1)
        self.instrument2 = Instrument.objects.create(name="Trumpet", section=self.section2)

        # Create test members
        self.member1 = Member.objects.create(
            first_name="John",
            last_name="Doe",
            primary_instrument=self.instrument1,
            is_active=True,
        )

        self.member2 = Member.objects.create(
            first_name="Jane",
            last_name="Smith",
            primary_instrument=self.instrument2,
            is_active=True,
        )

        # Create a new member (joined this week)
        self.new_member = Member.objects.create(
            first_name="New",
            last_name="Member",
            primary_instrument=self.instrument1,
            is_active=True,
            join_date=datetime.date.today(),
        )

        # Create a reactivated member
        self.reactivated_member = Member.objects.create(
            first_name="Reactivated",
            last_name="Member",
            primary_instrument=self.instrument2,
            is_active=True,
            reactivated_date=datetime.date.today(),
        )

        # Create attendance records for past week
        today = datetime.date.today()
        for i in range(3):
            AttendanceRecord.objects.create(
                date=today - datetime.timedelta(days=i),
                member=self.member1,
                played_instrument=self.instrument1,
            )

        for i in range(2):
            AttendanceRecord.objects.create(
                date=today - datetime.timedelta(days=i),
                member=self.member2,
                played_instrument=self.instrument2,
            )

        # Create a guest attendance record
        AttendanceRecord.objects.create(
            date=today,
            guest_name="Guest",
        )

    def test_generates_attendance_report(self):
        """Test that the report is generated with attendance metrics."""
        out = StringIO()
        call_command("send_attendance_report", "--dry-run", f"--day-to-run={TODAY_WEEKDAY}", stdout=out)

        output = out.getvalue()

        # Check that key elements are in the report
        self.assertIn("Attendance Report", output)
        self.assertIn("TOTAL ATTENDANCE", output)
        self.assertIn("ATTENDANCE BY SECTION", output)
        self.assertIn("Woodwinds", output)
        self.assertIn("Brass", output)

    def test_new_members_in_report(self):
        """Test that new members are listed in the report."""
        out = StringIO()
        call_command("send_attendance_report", "--dry-run", f"--day-to-run={TODAY_WEEKDAY}", stdout=out)

        output = out.getvalue()
        self.assertIn("NEW MEMBERS", output)
        self.assertIn("New", output)

    def test_reactivated_members_in_report(self):
        """Test that reactivated members are listed in the report."""
        out = StringIO()
        call_command("send_attendance_report", "--dry-run", f"--day-to-run={TODAY_WEEKDAY}", stdout=out)

        output = out.getvalue()
        self.assertIn("REACTIVATED MEMBERS", output)
        self.assertIn("Reactivated", output)

    def test_guest_attendance_in_report(self):
        """Test that guest attendance is counted in the report."""
        out = StringIO()
        call_command("send_attendance_report", "--dry-run", f"--day-to-run={TODAY_WEEKDAY}", stdout=out)

        output = out.getvalue()
        self.assertIn("GUEST ATTENDANCE", output)

    def test_turnout_percentage_in_report(self):
        """Test that turnout percentages are calculated."""
        out = StringIO()
        call_command("send_attendance_report", "--dry-run", f"--day-to-run={TODAY_WEEKDAY}", stdout=out)

        output = out.getvalue()
        self.assertIn("TURNOUT PERCENTAGE", output)
        self.assertIn("%", output)

    def test_report_respects_day_to_run(self):
        """Test that command skips execution if not on the correct day."""
        out = StringIO()
        different_day = (TODAY_WEEKDAY + 1) % 7
        call_command("send_attendance_report", f"--day-to-run={different_day}", stdout=out)

        output = out.getvalue()
        self.assertIn("only", output)  # Should mention day restriction

    def test_report_dry_run_format(self):
        """Test the dry-run email format."""
        out = StringIO()
        call_command("send_attendance_report", "--dry-run", f"--day-to-run={TODAY_WEEKDAY}", stdout=out)

        output = out.getvalue()
        self.assertIn("[Dry Run]", output)
        self.assertIn("Would send email", output)

    @override_settings(FROM_EMAIL="noreply@example.com")
    def test_report_sends_email_without_dry_run(self):
        """Test that the report actually sends an email when not in dry-run mode."""
        from django.core import mail

        out = StringIO()
        call_command("send_attendance_report", f"--day-to-run={TODAY_WEEKDAY}", stdout=out)

        # Verify email was sent
        self.assertEqual(len(mail.outbox), 1)
        email = mail.outbox[0]
        self.assertIn("Weekly Attendance Report", email.subject)
        self.assertEqual(email.to, ["test@example.com"])
        self.assertIn("Attendance Report", email.body)
        self.assertIn("TOTAL ATTENDANCE", email.body)
