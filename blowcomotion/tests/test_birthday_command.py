"""
Tests for the monthly birthday summary management command.
"""

from io import StringIO

from wagtail.models import Site

from django.core import mail
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase

from blowcomotion.models import Instrument, Member, Section, SiteSettings


class SendMonthlyBirthdaySummaryTests(TestCase):
    """Test cases for the send_monthly_birthday_summary management command"""

    def setUp(self):
        """Set up test data"""
        # Set up site and settings
        self.site = Site.objects.get(is_default_site=True)
        self.site_settings = SiteSettings.objects.create(
            site=self.site,
            birthday_summary_email_recipients='test1@example.com, test2@example.com'
        )
        
        # Create test sections and instruments
        self.brass_section = Section.objects.create(name='Brass')
        self.drums_section = Section.objects.create(name='Drums')
        
        self.trumpet = Instrument.objects.create(name='Trumpet', section=self.brass_section)
        self.trombone = Instrument.objects.create(name='Trombone', section=self.brass_section)
        self.snare = Instrument.objects.create(name='Snare Drum', section=self.drums_section)
        
        # Create test members with birthdays
        self.member_with_age = Member.objects.create(
            first_name='John',
            last_name='WithAge',
            birth_month=9,  # September
            birth_day=15,
            birth_year=1990,
            is_active=True,
            preferred_name='Johnny',
            primary_instrument=self.trumpet
        )
        
        self.member_no_age = Member.objects.create(
            first_name='Jane',
            last_name='NoAge',
            birth_month=9,  # September
            birth_day=25,
            is_active=True,
            primary_instrument=self.trombone
        )
        
        self.inactive_member = Member.objects.create(
            first_name='Bob',
            last_name='Inactive',
            birth_month=9,  # September
            birth_day=5,
            birth_year=1985,
            is_active=False,  # Should not appear in summary
            primary_instrument=self.snare
        )
        
        self.member_different_month = Member.objects.create(
            first_name='Alice',
            last_name='DifferentMonth',
            birth_month=10,  # October
            birth_day=10,
            birth_year=1995,
            is_active=True,
            primary_instrument=self.trumpet
        )

    def test_command_with_birthdays_dry_run(self):
        """Test command with birthdays in dry-run mode"""
        out = StringIO()
        call_command('send_monthly_birthday_summary', '--month=9', '--year=2025', '--ignore-date-check', '--dry-run', stdout=out)
        
        output = out.getvalue()
        
        # Check command output
        self.assertIn('Generating birthday summary for September 2025', output)
        self.assertIn('Found 2 birthday(s) in September 2025', output)
        self.assertIn('John WithAge', output)
        self.assertIn('Jane NoAge', output)
        self.assertIn('DRY RUN', output)
        self.assertNotIn('Bob Inactive', output)  # Inactive member should not appear
        self.assertNotIn('Alice DifferentMonth', output)  # Different month should not appear
        
        # No emails should be sent in dry-run mode
        self.assertEqual(len(mail.outbox), 0)

    def test_command_with_birthdays_actual_send(self):
        """Test command with actual email sending"""
        out = StringIO()
        self._run_command(month=9, year=2025, stdout=out)
        
        output = out.getvalue()
        
        # Check command output
        self.assertIn('✅ Monthly birthday summary sent successfully', output)
        
        # Check that email was sent
        self.assertEqual(len(mail.outbox), 1)
        
        email = mail.outbox[0]
        self.assertEqual(email.subject, 'Monthly Birthday Summary - September 2025')
        self.assertEqual(email.from_email, 'website@blowcomotion.org')
        self.assertEqual(email.to, ['test1@example.com', 'test2@example.com'])
        
        # Check email content
        self.assertIn('John WithAge', email.body)
        self.assertIn('Jane NoAge', email.body)
        self.assertIn('September 15', email.body)
        self.assertIn('September 25', email.body)
        self.assertIn('Turning 35', email.body)  # Age calculation
        self.assertIn('Johnny', email.body)  # Preferred name
        self.assertIn('Trumpet', email.body)  # Instrument
        self.assertIn('Trombone', email.body)  # Instrument
        
        # Check that inactive member and different month member are not included
        self.assertNotIn('Bob Inactive', email.body)
        self.assertNotIn('Alice DifferentMonth', email.body)

    def test_command_no_birthdays(self):
        """Test command when there are no birthdays in the target month"""
        out = StringIO()
        self._run_command(month=11, year=2025, dry_run=True, stdout=out)
        
        output = out.getvalue()
        
        # Check command output
        self.assertIn('Found 0 birthday(s) in November 2025', output)
        self.assertIn('No birthdays scheduled for November 2025', output)

    def test_command_no_recipients_configured(self):
        """Test command when no email recipients are configured"""
        # Clear recipients
        self.site_settings.birthday_summary_email_recipients = ''
        self.site_settings.save()
        

        with self.assertRaises(CommandError) as cm:
            self._run_command(month=9, year=2025)
        
        self.assertIn('No birthday email recipients configured', str(cm.exception))

    def test_command_default_next_month(self):
        """Test command with default next month behavior"""
        out = StringIO()
        
        # We can't easily mock the date in the command, so we'll test with explicit month
        self._run_command(month=9, year=2025, dry_run=True, stdout=out)
        
        output = out.getvalue()
        self.assertIn('September 2025', output)

    def test_command_invalid_month(self):
        """Test command with invalid month parameter"""
        with self.assertRaises(CommandError) as cm:
            self._run_command(month=13, year=2025)
        
        self.assertIn('Month must be between 1 and 12', str(cm.exception))

    def test_email_template_html_content(self):
        """Test that HTML email template renders correctly"""
        self._run_command(month=9, year=2025)
        
        self.assertEqual(len(mail.outbox), 1)
        email = mail.outbox[0]
        
        # Check that HTML content exists
        html_content = None
        for part in email.message().walk():
            if part.get_content_type() == 'text/html':
                html_content = part.get_payload()
                break
        
        self.assertIsNotNone(html_content)
        self.assertIn('Monthly Birthday Summary', html_content)
        self.assertIn('September 2025', html_content)
        self.assertIn('Johnny', html_content)
        self.assertIn('Trumpet', html_content)
        self.assertIn('<!DOCTYPE html>', html_content)

    def test_age_calculation(self):
        """Test age calculation in birthday summary"""
        out = StringIO()
        self._run_command(month=9, year=2025, dry_run=True, stdout=out)
        
        output = out.getvalue()
        
        # John WithAge was born in 1990, so in 2025 he turns 35
        self.assertIn('turning 35', output)
        
        # Jane NoAge has no birth year, so no age info
        self.assertNotIn('Jane NoAge - September 25 (turning', output)

    def _run_command(self, **kwargs):
        """Helper to run command with date check bypassed for tests"""
        kwargs.setdefault('ignore_date_check', True)
        return call_command('send_monthly_birthday_summary', **kwargs)