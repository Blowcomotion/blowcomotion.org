"""
Tests for the cleanup_attendance_roster management command.
"""

from datetime import date, timedelta
from io import StringIO
from unittest.mock import MagicMock, patch

from wagtail.models import Site

from django.conf import settings
from django.core import mail
from django.core.management import call_command
from django.test import TestCase, override_settings

from blowcomotion.models import Instrument, Member, Section, SiteSettings


class CleanupAttendanceRosterTests(TestCase):
    """Test cases for the cleanup_attendance_roster management command"""

    def setUp(self):
        """Set up test data"""
        # Set up site and settings
        self.site = Site.objects.get(is_default_site=True)
        self.site_settings = SiteSettings.objects.create(
            site=self.site,
            attendance_cleanup_days=90,
            attendance_cleanup_notification_recipients='admin@example.com'
        )
        
        # Create test sections and instruments
        self.brass_section = Section.objects.create(name='Brass')
        self.trumpet = Instrument.objects.create(name='Trumpet', section=self.brass_section)
        
        # Create test members with various last_seen dates
        today = date.today()
        
        # Member who should be marked inactive (last seen 100 days ago)
        self.inactive_member = Member.objects.create(
            first_name='Old',
            last_name='Member',
            email='old@example.com',
            last_seen=today - timedelta(days=100),
            is_active=True,
            primary_instrument=self.trumpet,
            gigomatic_id='123'
        )
        
        # Member who is still active (last seen 30 days ago)
        self.active_member = Member.objects.create(
            first_name='Active',
            last_name='Member',
            email='active@example.com',
            last_seen=today - timedelta(days=30),
            is_active=True,
            primary_instrument=self.trumpet
        )
        
        # Member already marked inactive
        self.already_inactive = Member.objects.create(
            first_name='Already',
            last_name='Inactive',
            email='inactive@example.com',
            last_seen=today - timedelta(days=100),
            is_active=False,
            primary_instrument=self.trumpet
        )
        
        # Member without email (edge case)
        self.no_email_member = Member.objects.create(
            first_name='NoEmail',
            last_name='Member',
            last_seen=today - timedelta(days=100),
            is_active=True,
            primary_instrument=self.trumpet
        )

    def test_dry_run_mode(self):
        """Test command in dry-run mode doesn't make changes"""
        out = StringIO()
        call_command('cleanup_attendance_roster', '--dry-run', stdout=out)
        
        output = out.getvalue()
        
        # Check command output
        self.assertIn('Dry Run', output)
        self.assertIn('Found 2 members to mark as inactive', output)
        
        # Verify no changes were made
        self.inactive_member.refresh_from_db()
        self.assertTrue(self.inactive_member.is_active)
        
        # No emails should be sent in dry-run mode
        self.assertEqual(len(mail.outbox), 0)

    @patch('blowcomotion.views.make_gigo_api_request')
    def test_marks_inactive_members(self, mock_api):
        """Test command marks inactive members as inactive"""
        # Mock API response for successful toggle
        mock_api.return_value = {'is_occasional': True, 'member_id': '123', 'band_id': '1'}
        
        out = StringIO()
        call_command('cleanup_attendance_roster', stdout=out)
        
        output = out.getvalue()
        
        # Check command output
        self.assertIn('Found 2 members to mark as inactive', output)
        self.assertIn('Marked member Old Member as inactive', output)
        
        # Verify member was marked inactive
        self.inactive_member.refresh_from_db()
        self.assertFalse(self.inactive_member.is_active)
        
        # Verify active member is still active
        self.active_member.refresh_from_db()
        self.assertTrue(self.active_member.is_active)
        
        # Verify email was sent
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn('Attendance Cleanup Report', mail.outbox[0].subject)
        self.assertIn('Old Member', mail.outbox[0].body)

    @patch('blowcomotion.views.make_gigo_api_request')
    def test_calls_go3_api_with_correct_endpoint(self, mock_api):
        """Test command calls GO3 API with correct endpoint"""
        mock_api.return_value = {'is_occasional': True, 'member_id': '123', 'band_id': '1'}
        
        out = StringIO()
        with override_settings(DEBUG=False, GIGO_BAND_ID='456'):
            call_command('cleanup_attendance_roster', stdout=out)
        
        # Verify API was called with correct endpoint
        mock_api.assert_called()
        call_args = mock_api.call_args_list[-1]
        self.assertIn('/bands/456/members/123/occasional', call_args[0][0])
        self.assertEqual(call_args[1]['method'], 'PATCH')

    @override_settings(DEBUG=False, GIGO_BAND_ID='1', GIGO_API_URL='http://test', GIGO_API_KEY='test-key')
    @patch('blowcomotion.views.make_gigo_api_request')
    def test_toggle_verification_when_already_occasional(self, mock_api):
        """Test command toggles again if member is already occasional"""
        # First call returns False (member was regular, now occasional)
        # Second call should return True (member was occasional, now regular... wait, we want True)
        mock_api.side_effect = [
            {'is_occasional': False, 'member_id': '123', 'band_id': '1'},  # First toggle failed
            {'is_occasional': True, 'member_id': '123', 'band_id': '1'}   # Second toggle succeeded
        ]
        
        out = StringIO()
        call_command('cleanup_attendance_roster', stdout=out)
        
        output = out.getvalue()
        
        # Verify command detected the issue and toggled again
        self.assertIn('was already occasional', output)
        self.assertIn('toggling back', output)
        self.assertIn('Confirmed member', output)
        
        # Verify API was called twice
        self.assertEqual(mock_api.call_count, 2)

    @override_settings(DEBUG=False, GIGO_BAND_ID='1', GIGO_API_URL='http://test', GIGO_API_KEY='test-key')
    @patch('blowcomotion.views.make_gigo_api_request')
    def test_handles_api_errors_gracefully(self, mock_api):
        """Test command handles API errors gracefully"""
        mock_api.side_effect = Exception('API connection failed')
        
        out = StringIO()
        call_command('cleanup_attendance_roster', stdout=out)
        
        output = out.getvalue()
        
        # Member should still be marked inactive locally
        self.inactive_member.refresh_from_db()
        self.assertFalse(self.inactive_member.is_active)
        
        # Error should be logged
        self.assertIn('Error marking member', output)

    @patch('blowcomotion.views.make_gigo_api_request')
    def test_handles_member_without_gigo_id(self, mock_api):
        """Test command handles members without Gig-O-Matic ID"""
        # Member without gigomatic_id and no email
        out = StringIO()
        call_command('cleanup_attendance_roster', stdout=out)
        
        output = out.getvalue()
        
        # Verify member was still marked inactive locally
        self.no_email_member.refresh_from_db()
        self.assertFalse(self.no_email_member.is_active)
        
        # Warning should be logged
        self.assertIn('No Gigo ID found', output)

    def test_day_restriction(self):
        """Test command respects day-of-week restriction"""
        out = StringIO()
        today = date.today()
        # Set day_to_run to a different day than today
        different_day = (today.weekday() + 1) % 7
        
        call_command('cleanup_attendance_roster', f'--day-to-run={different_day}', stdout=out)
        
        output = out.getvalue()
        
        # Command should exit early
        self.assertIn('intended to be run on', output)
        self.assertIn('Exiting', output)
        
        # No changes should be made
        self.inactive_member.refresh_from_db()
        self.assertTrue(self.inactive_member.is_active)

    def test_no_inactive_members(self):
        """Test command when there are no inactive members"""
        # Mark all test members as active with recent last_seen dates
        today = date.today()
        for member in Member.objects.all():
            member.is_active = True
            member.last_seen = today - timedelta(days=1)
            member.save()
        
        out = StringIO()
        call_command('cleanup_attendance_roster', stdout=out)
        
        output = out.getvalue()
        
        # Check command output
        self.assertIn('No members to mark as inactive', output)
        
        # Email should still be sent
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn('0 members', mail.outbox[0].body)

    def test_no_site_settings(self):
        """Test command handles missing SiteSettings gracefully"""
        SiteSettings.objects.all().delete()
        Site.objects.all().delete()
        
        out = StringIO()
        call_command('cleanup_attendance_roster', stdout=out)
        
        output = out.getvalue()
        
        # Command should exit with error
        self.assertIn('No Site configured', output)

    @override_settings(GIGO_BAND_ID_LOCAL='789', DEBUG=True)
    @patch('blowcomotion.views.make_gigo_api_request')
    def test_uses_local_band_id_in_debug_mode(self, mock_api):
        """Test command uses GIGO_BAND_ID_LOCAL in DEBUG mode"""
        mock_api.return_value = {'is_occasional': True, 'member_id': '123', 'band_id': '789'}
        
        out = StringIO()
        call_command('cleanup_attendance_roster', stdout=out)
        
        # Verify API was called with local band ID
        call_args = mock_api.call_args_list[-1]
        self.assertIn('/bands/789/members/123/occasional', call_args[0][0])

    def test_email_contains_member_details(self):
        """Test notification email contains member details"""
        with patch('blowcomotion.views.make_gigo_api_request') as mock_api:
            mock_api.return_value = {'is_occasional': True, 'member_id': '123', 'band_id': '1'}
            
            out = StringIO()
            call_command('cleanup_attendance_roster', stdout=out)
        
        # Check email content
        self.assertEqual(len(mail.outbox), 1)
        email_body = mail.outbox[0].body
        
        self.assertIn('Old Member', email_body)
        self.assertIn('Trumpet', email_body)
        self.assertIn('Last seen:', email_body)
        self.assertIn(str(self.inactive_member.last_seen), email_body)

    def test_multiple_recipients(self):
        """Test email is sent to multiple recipients"""
        self.site_settings.attendance_cleanup_notification_recipients = 'admin1@example.com,admin2@example.com'
        self.site_settings.save()
        
        with patch('blowcomotion.views.make_gigo_api_request') as mock_api:
            mock_api.return_value = {'is_occasional': True, 'member_id': '123', 'band_id': '1'}
            
            out = StringIO()
            call_command('cleanup_attendance_roster', stdout=out)
        
        # Verify email was sent to multiple recipients
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn('admin1@example.com', mail.outbox[0].to)
        self.assertIn('admin2@example.com', mail.outbox[0].to)
