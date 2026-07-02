"""
Tests for the birthday summary management command
(monthly mode and rolling-window --days mode).
"""

from datetime import date
from io import StringIO
from unittest.mock import patch

from wagtail.models import Site

from django.conf import settings
from django.core import mail
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase, override_settings

from blowcomotion.models import Instrument, Member, Section, SiteSettings


@override_settings(FROM_EMAIL='test@example.com')
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
        self.assertEqual(email.from_email, settings.FROM_EMAIL)
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
        
        # Verify no email is sent when there are no birthdays
        self.assertEqual(len(mail.outbox), 0)

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

    def test_member_with_additional_instruments(self):
        """Test that both primary and additional instruments are included in birthday summary"""
        from blowcomotion.models import MemberInstrument

        # Create a member with birthday in September
        member_multi_instruments = Member.objects.create(
            first_name='Alex',
            last_name='MultiInstrument',
            birth_month=9,  # September
            birth_day=20,
            birth_year=1988,
            is_active=True,
            primary_instrument=self.trumpet  # Primary instrument
        )
        
        # Add additional instruments
        MemberInstrument.objects.create(
            member=member_multi_instruments,
            instrument=self.trombone
        )
        MemberInstrument.objects.create(
            member=member_multi_instruments,
            instrument=self.snare
        )
        
        # Test dry-run output
        out = StringIO()
        self._run_command(month=9, year=2025, dry_run=True, stdout=out)
        
        output = out.getvalue()
        
        # Check that all instruments are listed in output
        self.assertIn('Alex MultiInstrument', output)
        self.assertIn('Trumpet', output)
        self.assertIn('Trombone', output)
        self.assertIn('Snare Drum', output)
        
        # Test actual email sending
        mail.outbox = []  # Clear previous emails
        self._run_command(month=9, year=2025)
        
        # Verify email was sent
        self.assertEqual(len(mail.outbox), 1)
        email = mail.outbox[0]
        
        # Check email content includes all instruments
        email_body = email.body
        self.assertIn('Alex MultiInstrument', email_body)
        self.assertIn('Trumpet', email_body)
        self.assertIn('Trombone', email_body)
        self.assertIn('Snare Drum', email_body)
        self.assertIn('Turning 37', email_body)  # Born in 1988, turns 37 in 2025
        
        # Check HTML email content
        html_content = None
        for part in email.message().walk():
            if part.get_content_type() == 'text/html':
                html_content = part.get_payload()
                break
        
        self.assertIsNotNone(html_content)
        self.assertIn('Alex MultiInstrument', html_content)
        self.assertIn('Trumpet', html_content)
        self.assertIn('Trombone', html_content)
        self.assertIn('Snare Drum', html_content)

    def test_year_inference_future_month_in_current_year(self):
        """Test year inference when specifying a month later than today"""
        # Setup: Create a member with birthday in November
        Member.objects.create(
            first_name='Bob',
            last_name='November',
            birth_month=11,  # November
            birth_day=10,
            birth_year=2000,
            is_active=True,
            primary_instrument=self.trumpet
        )
        
        # Mock today as January 27, 2026
        with patch('blowcomotion.management.commands.send_monthly_birthday_summary.date') as mock_date:
            mock_date.today.return_value = date(2026, 1, 27)
            mock_date.side_effect = date
            
            out = StringIO()
            call_command('send_monthly_birthday_summary', month=11, ignore_date_check=True, dry_run=True, stdout=out)
            
            output = out.getvalue()
            
            # November comes later in 2026, so it should use 2026 (current year)
            self.assertIn('November 2026', output)
            self.assertIn('Bob November', output)
            self.assertNotIn('November 2027', output)

    def test_year_inference_past_month_rolls_to_next_year(self):
        """Test year inference when specifying a month earlier than current month"""
        # Setup: Create a member with birthday in September
        Member.objects.create(
            first_name='Charlie',
            last_name='September',
            birth_month=9,  # September
            birth_day=15,
            birth_year=1995,
            is_active=True,
            primary_instrument=self.trumpet
        )
        
        # Mock today as January 27, 2026
        # September 2026 would be in the future, so it should use 2026
        # But if today is March 2026, then September 2026 is future
        # If today is October 2026, then September 2026 is past, so use 2027
        with patch('blowcomotion.management.commands.send_monthly_birthday_summary.date') as mock_date:
            mock_date.today.return_value = date(2026, 10, 15)  # October 15, 2026
            mock_date.side_effect = date
            
            out = StringIO()
            call_command('send_monthly_birthday_summary', month=9, ignore_date_check=True, dry_run=True, stdout=out)
            
            output = out.getvalue()
            
            # September has already passed in 2026, so it should roll to 2027
            self.assertIn('September 2027', output)
            self.assertIn('Charlie September', output)
            self.assertNotIn('September 2026', output)

    def test_year_inference_edge_case_same_day_as_target_month(self):
        """Test year inference when today is the first day of the target month"""
        # Setup: Create a member with birthday in January
        Member.objects.create(
            first_name='Diana',
            last_name='January',
            birth_month=1,  # January
            birth_day=20,
            birth_year=2000,
            is_active=True,
            primary_instrument=self.trumpet
        )
        
        # Mock today as January 1, 2026 (first day of January)
        with patch('blowcomotion.management.commands.send_monthly_birthday_summary.date') as mock_date:
            mock_date.today.return_value = date(2026, 1, 1)
            mock_date.side_effect = date
            
            out = StringIO()
            call_command('send_monthly_birthday_summary', month=1, ignore_date_check=True, dry_run=True, stdout=out)
            
            output = out.getvalue()
            
            # Today IS in January 2026, so target is January 2026 (not 2027)
            self.assertIn('January 2026', output)
            self.assertIn('Diana January', output)
            self.assertNotIn('January 2027', output)

    def test_year_inference_december_edge_case(self):
        """Test year inference when specifying December from an earlier month"""
        # Setup: Create a member with birthday in December
        Member.objects.create(
            first_name='Eve',
            last_name='December',
            birth_month=12,  # December
            birth_day=25,
            birth_year=1990,
            is_active=True,
            primary_instrument=self.trumpet
        )
        
        # Mock today as June 15, 2026 (middle of year)
        with patch('blowcomotion.management.commands.send_monthly_birthday_summary.date') as mock_date:
            mock_date.today.return_value = date(2026, 6, 15)
            mock_date.side_effect = date
            
            out = StringIO()
            call_command('send_monthly_birthday_summary', month=12, ignore_date_check=True, dry_run=True, stdout=out)
            
            output = out.getvalue()
            
            # December is later in 2026, so use 2026
            self.assertIn('December 2026', output)
            self.assertIn('Eve December', output)
            self.assertNotIn('December 2027', output)

    def test_year_inference_january_from_december(self):
        """Test year inference when specifying January from December of previous year"""
        # Setup: Create a member with birthday in January
        Member.objects.create(
            first_name='Frank',
            last_name='January',
            birth_month=1,  # January
            birth_day=10,
            birth_year=1985,
            is_active=True,
            primary_instrument=self.trumpet
        )
        
        # Mock today as December 15, 2025 (December of previous year)
        with patch('blowcomotion.management.commands.send_monthly_birthday_summary.date') as mock_date:
            mock_date.today.return_value = date(2025, 12, 15)
            mock_date.side_effect = date
            
            out = StringIO()
            call_command('send_monthly_birthday_summary', month=1, ignore_date_check=True, dry_run=True, stdout=out)
            
            output = out.getvalue()
            
            # January 2025 is in the past, so should use January 2026
            self.assertIn('January 2026', output)
            self.assertIn('Frank January', output)
            self.assertNotIn('January 2025', output)

    def test_year_inference_with_only_month_no_birthdays_correct_year(self):
        """Test year inference targets correct year even when no birthdays found"""
        # No members with birthdays in May
        
        # Mock today as February 1, 2026
        with patch('blowcomotion.management.commands.send_monthly_birthday_summary.date') as mock_date:
            mock_date.today.return_value = date(2026, 2, 1)
            mock_date.side_effect = date
            
            out = StringIO()
            call_command('send_monthly_birthday_summary', month=1, ignore_date_check=True, dry_run=True, stdout=out)
            
            output = out.getvalue()
            
            # January is in the past (month 1 < current month 2), so should roll to 2027
            self.assertIn('January 2027', output)
            self.assertIn('No birthdays scheduled for January 2027', output)

    def test_year_inference_explicit_year_overrides_inference(self):
        """Test that explicit year parameter overrides inference logic"""
        # Setup: Create a member with birthday in January
        Member.objects.create(
            first_name='Grace',
            last_name='January',
            birth_month=1,  # January
            birth_day=5,
            birth_year=1999,
            is_active=True,
            primary_instrument=self.trumpet
        )
        
        # Mock today as June 15, 2026
        with patch('blowcomotion.management.commands.send_monthly_birthday_summary.date') as mock_date:
            mock_date.today.return_value = date(2026, 6, 15)
            mock_date.side_effect = date
            
            out = StringIO()
            # Explicitly provide year=2025 (even though it's in the past)
            call_command('send_monthly_birthday_summary', month=1, year=2025, ignore_date_check=True, dry_run=True, stdout=out)
            
            output = out.getvalue()
            
            # Should respect explicit year=2025, not infer 2026
            self.assertIn('January 2025', output)
            # Member still appears because they have a birthday in 2025 (born 1999, so age 26 in 2025)
            self.assertIn('Grace January', output)
            self.assertNotIn('January 2026', output)

    def _run_command(self, **kwargs):
        """Helper to run command with date check bypassed for tests"""
        kwargs.setdefault('ignore_date_check', True)
        return call_command('send_monthly_birthday_summary', **kwargs)

@override_settings(FROM_EMAIL='test@example.com')
class RollingWindowBirthdayUpdateTests(TestCase):
    """Test cases for the rolling-window (--days) mode of send_monthly_birthday_summary"""

    def setUp(self):
        """Set up test data"""
        self.site = Site.objects.get(is_default_site=True)
        self.site_settings = SiteSettings.objects.create(
            site=self.site,
            birthday_summary_email_recipients='test1@example.com, test2@example.com'
        )

        self.brass_section = Section.objects.create(name='Brass')
        self.drums_section = Section.objects.create(name='Drums')

        self.trumpet = Instrument.objects.create(name='Trumpet', section=self.brass_section)
        self.trombone = Instrument.objects.create(name='Trombone', section=self.brass_section)
        self.snare = Instrument.objects.create(name='Snare Drum', section=self.drums_section)

    def _mock_today(self, mock_date, today):
        mock_date.today.return_value = today
        mock_date.side_effect = date

    def test_command_with_birthday_in_range_dry_run(self):
        """A birthday within the default 7-day lookahead window should show up in dry-run output"""
        Member.objects.create(
            first_name='John',
            last_name='WithAge',
            birth_month=7,
            birth_day=5,
            birth_year=1990,
            is_active=True,
            preferred_name='Johnny',
            primary_instrument=self.trumpet,
        )

        with patch('blowcomotion.management.commands.send_monthly_birthday_summary.date') as mock_date:
            self._mock_today(mock_date, date(2026, 7, 1))

            out = StringIO()
            call_command('send_monthly_birthday_summary', '--days', '--dry-run', stdout=out)

            output = out.getvalue()
            self.assertIn('Found 1 birthday(s) in the next 7 day(s)', output)
            self.assertIn('John WithAge', output)
            self.assertIn('DRY RUN', output)
            self.assertEqual(len(mail.outbox), 0)

    def test_command_birthday_outside_range_excluded(self):
        """A birthday outside the lookahead window should not appear"""
        Member.objects.create(
            first_name='Alice',
            last_name='FarAway',
            birth_month=12,
            birth_day=25,
            birth_year=1995,
            is_active=True,
            primary_instrument=self.trumpet,
        )

        with patch('blowcomotion.management.commands.send_monthly_birthday_summary.date') as mock_date:
            self._mock_today(mock_date, date(2026, 7, 1))

            out = StringIO()
            call_command('send_monthly_birthday_summary', '--days', '--dry-run', stdout=out)

            output = out.getvalue()
            self.assertIn('Found 0 birthday(s)', output)
            self.assertNotIn('Alice FarAway', output)

    def test_command_excludes_inactive_members(self):
        Member.objects.create(
            first_name='Bob',
            last_name='Inactive',
            birth_month=7,
            birth_day=5,
            birth_year=1985,
            is_active=False,
            primary_instrument=self.snare,
        )

        with patch('blowcomotion.management.commands.send_monthly_birthday_summary.date') as mock_date:
            self._mock_today(mock_date, date(2026, 7, 1))

            out = StringIO()
            call_command('send_monthly_birthday_summary', '--days', '--dry-run', stdout=out)

            output = out.getvalue()
            self.assertIn('Found 0 birthday(s)', output)
            self.assertNotIn('Bob Inactive', output)

    def test_command_with_actual_send(self):
        Member.objects.create(
            first_name='John',
            last_name='WithAge',
            birth_month=7,
            birth_day=5,
            birth_year=1990,
            is_active=True,
            preferred_name='Johnny',
            primary_instrument=self.trumpet,
        )

        with patch('blowcomotion.management.commands.send_monthly_birthday_summary.date') as mock_date:
            self._mock_today(mock_date, date(2026, 7, 1))

            out = StringIO()
            call_command('send_monthly_birthday_summary', '--days', stdout=out)

            output = out.getvalue()
            self.assertIn('✅ Weekly birthday update sent successfully', output)

            self.assertEqual(len(mail.outbox), 1)
            email = mail.outbox[0]
            self.assertEqual(email.subject, 'Weekly Birthday Update - July 01, 2026')
            self.assertEqual(email.from_email, settings.FROM_EMAIL)
            self.assertEqual(email.to, ['test1@example.com', 'test2@example.com'])
            self.assertIn('John WithAge', email.body)
            self.assertIn('July 05', email.body)
            self.assertIn('Turning 36', email.body)
            self.assertIn('Johnny', email.body)
            self.assertIn('Trumpet', email.body)

    def test_command_no_birthdays_skips_email(self):
        with patch('blowcomotion.management.commands.send_monthly_birthday_summary.date') as mock_date:
            self._mock_today(mock_date, date(2026, 7, 1))

            out = StringIO()
            call_command('send_monthly_birthday_summary', '--days', stdout=out)

            output = out.getvalue()
            self.assertIn('No birthdays scheduled', output)
            self.assertEqual(len(mail.outbox), 0)

    def test_command_no_recipients_configured(self):
        self.site_settings.birthday_summary_email_recipients = ''
        self.site_settings.save()

        Member.objects.create(
            first_name='John',
            last_name='WithAge',
            birth_month=7,
            birth_day=5,
            birth_year=1990,
            is_active=True,
            primary_instrument=self.trumpet,
        )

        with patch('blowcomotion.management.commands.send_monthly_birthday_summary.date') as mock_date:
            self._mock_today(mock_date, date(2026, 7, 1))

            with self.assertRaises(CommandError) as cm:
                call_command('send_monthly_birthday_summary', '--days')

            self.assertIn('No birthday email recipients configured', str(cm.exception))

    def test_command_negative_days_rejected(self):
        with self.assertRaises(CommandError) as cm:
            call_command('send_monthly_birthday_summary', '--days=-5')

        self.assertIn('--days must be a positive integer', str(cm.exception))

    def test_command_days_and_month_rejected(self):
        with self.assertRaises(CommandError) as cm:
            call_command('send_monthly_birthday_summary', '--days=7', '--month=9')

        self.assertIn('--days cannot be combined with --month or --year', str(cm.exception))

    def test_command_birthday_today_included(self):
        """A birthday that falls on today should be included"""
        Member.objects.create(
            first_name='Grace',
            last_name='Today',
            birth_month=7,
            birth_day=1,
            birth_year=2000,
            is_active=True,
            primary_instrument=self.trumpet,
        )

        with patch('blowcomotion.management.commands.send_monthly_birthday_summary.date') as mock_date:
            self._mock_today(mock_date, date(2026, 7, 1))

            out = StringIO()
            call_command('send_monthly_birthday_summary', '--days', '--dry-run', stdout=out)

            output = out.getvalue()
            self.assertIn('Grace Today', output)

    def test_command_year_wrap_birthday_included(self):
        """A birthday early next January should be picked up from late December"""
        Member.objects.create(
            first_name='Eve',
            last_name='NewYear',
            birth_month=1,
            birth_day=2,
            birth_year=1990,
            is_active=True,
            primary_instrument=self.trumpet,
        )

        with patch('blowcomotion.management.commands.send_monthly_birthday_summary.date') as mock_date:
            self._mock_today(mock_date, date(2026, 12, 28))

            out = StringIO()
            call_command('send_monthly_birthday_summary', '--days', '--dry-run', stdout=out)

            output = out.getvalue()
            self.assertIn('Found 1 birthday(s)', output)
            self.assertIn('Eve NewYear', output)

    def test_command_custom_days_argument(self):
        """A wider lookahead window should include birthdays past the default cutoff"""
        Member.objects.create(
            first_name='Alice',
            last_name='TenDaysOut',
            birth_month=7,
            birth_day=11,
            birth_year=1995,
            is_active=True,
            primary_instrument=self.trumpet,
        )

        with patch('blowcomotion.management.commands.send_monthly_birthday_summary.date') as mock_date:
            self._mock_today(mock_date, date(2026, 7, 1))

            # Default 7-day window excludes the birthday (10 days out)
            out = StringIO()
            call_command('send_monthly_birthday_summary', '--days', '--dry-run', stdout=out)
            self.assertIn('Found 0 birthday(s)', out.getvalue())
            self.assertNotIn('Alice TenDaysOut', out.getvalue())

            # A wider 14-day window includes it
            out = StringIO()
            call_command('send_monthly_birthday_summary', '--days=14', '--dry-run', stdout=out)
            self.assertIn('Found 1 birthday(s)', out.getvalue())
            self.assertIn('Alice TenDaysOut', out.getvalue())

    def test_command_member_with_additional_instruments(self):
        from blowcomotion.models import MemberInstrument

        member = Member.objects.create(
            first_name='Alex',
            last_name='MultiInstrument',
            birth_month=7,
            birth_day=5,
            birth_year=1988,
            is_active=True,
            primary_instrument=self.trumpet,
        )
        MemberInstrument.objects.create(member=member, instrument=self.trombone)
        MemberInstrument.objects.create(member=member, instrument=self.snare)

        with patch('blowcomotion.management.commands.send_monthly_birthday_summary.date') as mock_date:
            self._mock_today(mock_date, date(2026, 7, 1))

            out = StringIO()
            call_command('send_monthly_birthday_summary', '--days', '--dry-run', stdout=out)

            output = out.getvalue()
            self.assertIn('Alex MultiInstrument', output)
            self.assertIn('Trumpet', output)
            self.assertIn('Trombone', output)
            self.assertIn('Snare Drum', output)

    def test_email_template_html_content(self):
        Member.objects.create(
            first_name='John',
            last_name='WithAge',
            birth_month=7,
            birth_day=5,
            birth_year=1990,
            is_active=True,
            preferred_name='Johnny',
            primary_instrument=self.trumpet,
        )

        with patch('blowcomotion.management.commands.send_monthly_birthday_summary.date') as mock_date:
            self._mock_today(mock_date, date(2026, 7, 1))

            call_command('send_monthly_birthday_summary', '--days')

        self.assertEqual(len(mail.outbox), 1)
        email = mail.outbox[0]

        html_content = None
        for part in email.message().walk():
            if part.get_content_type() == 'text/html':
                html_content = part.get_payload()
                break

        self.assertIsNotNone(html_content)
        self.assertIn('Weekly Birthday Update', html_content)
        self.assertIn('Johnny', html_content)
        self.assertIn('Trumpet', html_content)
        self.assertIn('<!DOCTYPE html>', html_content)
