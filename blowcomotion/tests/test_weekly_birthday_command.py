"""
Tests for the weekly birthday update management command.
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
class SendWeeklyBirthdaySummaryTests(TestCase):
    """Test cases for the send_weekly_birthday_summary management command"""

    def setUp(self):
        """Set up test data"""
        self.site = Site.objects.get(is_default_site=True)
        self.site_settings = SiteSettings.objects.create(
            site=self.site,
            weekly_birthday_summary_email_recipients='matt@example.com, test2@example.com'
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
        """A birthday within the lookahead window should show up in dry-run output"""
        Member.objects.create(
            first_name='John',
            last_name='WithAge',
            birth_month=7,
            birth_day=10,
            birth_year=1990,
            is_active=True,
            preferred_name='Johnny',
            primary_instrument=self.trumpet,
        )

        with patch('blowcomotion.management.commands.send_weekly_birthday_summary.date') as mock_date:
            self._mock_today(mock_date, date(2026, 7, 1))

            out = StringIO()
            call_command('send_weekly_birthday_summary', '--dry-run', stdout=out)

            output = out.getvalue()
            self.assertIn('Found 1 birthday(s)', output)
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

        with patch('blowcomotion.management.commands.send_weekly_birthday_summary.date') as mock_date:
            self._mock_today(mock_date, date(2026, 7, 1))

            out = StringIO()
            call_command('send_weekly_birthday_summary', '--dry-run', stdout=out)

            output = out.getvalue()
            self.assertIn('Found 0 birthday(s)', output)
            self.assertNotIn('Alice FarAway', output)

    def test_command_excludes_inactive_members(self):
        Member.objects.create(
            first_name='Bob',
            last_name='Inactive',
            birth_month=7,
            birth_day=10,
            birth_year=1985,
            is_active=False,
            primary_instrument=self.snare,
        )

        with patch('blowcomotion.management.commands.send_weekly_birthday_summary.date') as mock_date:
            self._mock_today(mock_date, date(2026, 7, 1))

            out = StringIO()
            call_command('send_weekly_birthday_summary', '--dry-run', stdout=out)

            output = out.getvalue()
            self.assertIn('Found 0 birthday(s)', output)
            self.assertNotIn('Bob Inactive', output)

    def test_command_with_actual_send(self):
        Member.objects.create(
            first_name='John',
            last_name='WithAge',
            birth_month=7,
            birth_day=10,
            birth_year=1990,
            is_active=True,
            preferred_name='Johnny',
            primary_instrument=self.trumpet,
        )

        with patch('blowcomotion.management.commands.send_weekly_birthday_summary.date') as mock_date:
            self._mock_today(mock_date, date(2026, 7, 1))

            out = StringIO()
            call_command('send_weekly_birthday_summary', stdout=out)

            output = out.getvalue()
            self.assertIn('✅ Weekly birthday update sent successfully', output)

            self.assertEqual(len(mail.outbox), 1)
            email = mail.outbox[0]
            self.assertEqual(email.subject, 'Weekly Birthday Update - July 01, 2026')
            self.assertEqual(email.from_email, settings.FROM_EMAIL)
            self.assertEqual(email.to, ['matt@example.com', 'test2@example.com'])
            self.assertIn('John WithAge', email.body)
            self.assertIn('July 10', email.body)
            self.assertIn('Turning 36', email.body)
            self.assertIn('Johnny', email.body)
            self.assertIn('Trumpet', email.body)

    def test_command_no_birthdays_skips_email(self):
        with patch('blowcomotion.management.commands.send_weekly_birthday_summary.date') as mock_date:
            self._mock_today(mock_date, date(2026, 7, 1))

            out = StringIO()
            call_command('send_weekly_birthday_summary', stdout=out)

            output = out.getvalue()
            self.assertIn('No birthdays scheduled', output)
            self.assertEqual(len(mail.outbox), 0)

    def test_command_no_recipients_configured(self):
        self.site_settings.weekly_birthday_summary_email_recipients = ''
        self.site_settings.save()

        Member.objects.create(
            first_name='John',
            last_name='WithAge',
            birth_month=7,
            birth_day=10,
            birth_year=1990,
            is_active=True,
            primary_instrument=self.trumpet,
        )

        with patch('blowcomotion.management.commands.send_weekly_birthday_summary.date') as mock_date:
            self._mock_today(mock_date, date(2026, 7, 1))

            with self.assertRaises(CommandError) as cm:
                call_command('send_weekly_birthday_summary')

            self.assertIn('No weekly birthday email recipients configured', str(cm.exception))

    def test_command_negative_days_rejected(self):
        with self.assertRaises(CommandError) as cm:
            call_command('send_weekly_birthday_summary', '--days=-5')

        self.assertIn('--days must be a positive integer', str(cm.exception))

    def test_command_birthday_today_included(self):
        """A birthday that falls on today should be included with 'Today!'"""
        Member.objects.create(
            first_name='Grace',
            last_name='Today',
            birth_month=7,
            birth_day=1,
            birth_year=2000,
            is_active=True,
            primary_instrument=self.trumpet,
        )

        with patch('blowcomotion.management.commands.send_weekly_birthday_summary.date') as mock_date:
            self._mock_today(mock_date, date(2026, 7, 1))

            out = StringIO()
            call_command('send_weekly_birthday_summary', '--dry-run', stdout=out)

            output = out.getvalue()
            self.assertIn('Grace Today', output)

    def test_command_year_wrap_birthday_included(self):
        """A birthday early next January should be picked up from late December"""
        Member.objects.create(
            first_name='Eve',
            last_name='NewYear',
            birth_month=1,
            birth_day=5,
            birth_year=1990,
            is_active=True,
            primary_instrument=self.trumpet,
        )

        with patch('blowcomotion.management.commands.send_weekly_birthday_summary.date') as mock_date:
            self._mock_today(mock_date, date(2026, 12, 28))

            out = StringIO()
            call_command('send_weekly_birthday_summary', '--dry-run', stdout=out)

            output = out.getvalue()
            self.assertIn('Found 1 birthday(s)', output)
            self.assertIn('Eve NewYear', output)

    def test_command_custom_days_argument(self):
        """A shorter lookahead window should exclude birthdays past the cutoff"""
        Member.objects.create(
            first_name='Alice',
            last_name='TenDaysOut',
            birth_month=7,
            birth_day=11,
            birth_year=1995,
            is_active=True,
            primary_instrument=self.trumpet,
        )

        with patch('blowcomotion.management.commands.send_weekly_birthday_summary.date') as mock_date:
            self._mock_today(mock_date, date(2026, 7, 1))

            # Default 30-day window includes the birthday
            out = StringIO()
            call_command('send_weekly_birthday_summary', '--dry-run', stdout=out)
            self.assertIn('Found 1 birthday(s)', out.getvalue())
            self.assertIn('Alice TenDaysOut', out.getvalue())

            # A narrower 7-day window excludes it (birthday is 10 days out)
            out = StringIO()
            call_command('send_weekly_birthday_summary', '--days=7', '--dry-run', stdout=out)
            self.assertIn('Found 0 birthday(s)', out.getvalue())
            self.assertNotIn('Alice TenDaysOut', out.getvalue())

    def test_command_member_with_additional_instruments(self):
        from blowcomotion.models import MemberInstrument

        member = Member.objects.create(
            first_name='Alex',
            last_name='MultiInstrument',
            birth_month=7,
            birth_day=15,
            birth_year=1988,
            is_active=True,
            primary_instrument=self.trumpet,
        )
        MemberInstrument.objects.create(member=member, instrument=self.trombone)
        MemberInstrument.objects.create(member=member, instrument=self.snare)

        with patch('blowcomotion.management.commands.send_weekly_birthday_summary.date') as mock_date:
            self._mock_today(mock_date, date(2026, 7, 1))

            out = StringIO()
            call_command('send_weekly_birthday_summary', '--dry-run', stdout=out)

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
            birth_day=10,
            birth_year=1990,
            is_active=True,
            preferred_name='Johnny',
            primary_instrument=self.trumpet,
        )

        with patch('blowcomotion.management.commands.send_weekly_birthday_summary.date') as mock_date:
            self._mock_today(mock_date, date(2026, 7, 1))

            call_command('send_weekly_birthday_summary')

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
