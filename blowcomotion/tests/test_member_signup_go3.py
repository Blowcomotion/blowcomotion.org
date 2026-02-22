"""
Unit tests for member signup with GO3 band invite integration.
"""

from unittest.mock import MagicMock, patch

from wagtail.models import Site

from django.test import Client, TestCase, override_settings
from django.urls import reverse

from blowcomotion.models import Instrument, Member, Section, SiteSettings
from blowcomotion.utils import send_member_to_go3_band_invite


class GO3BandInviteUtilsTests(TestCase):
    """Test cases for the send_member_to_go3_band_invite utility function"""

    def setUp(self):
        """Set up test data"""
        self.test_email = "test@example.com"
        self.test_band_id = 1
        self.test_api_key = "test-key"
        self.test_api_url = "http://localhost:8001/api"

    @override_settings(
        GIGO_API_URL="http://localhost:8001/api",
        GIGO_API_KEY="test-key",
        GIGO_BAND_ID_LOCAL=1,
        DEBUG=True
    )
    @patch('requests.post')
    def test_successful_invite(self, mock_post):
        """Test successful member invitation to GO3 band"""
        # Mock successful response
        mock_response = MagicMock()
        mock_response.json.return_value = {
            'invited': [self.test_email],
            'in_band': [],
            'invalid': []
        }
        mock_response.raise_for_status.return_value = None
        mock_post.return_value = mock_response

        result = send_member_to_go3_band_invite(self.test_email, use_local_band=True)

        self.assertEqual(result['status'], 'success')
        self.assertEqual(result['message'], 'Invitation sent successfully')
        self.assertIsNotNone(result['data'])
        self.assertFalse(result['in_band'])
        self.assertFalse(result['invalid'])
        
        # Verify the API was called correctly
        mock_post.assert_called_once()
        args, kwargs = mock_post.call_args
        self.assertIn('/1/invites', args[0])  # Local band ID
        self.assertEqual(kwargs['json']['emails'], [self.test_email])
        self.assertEqual(kwargs['headers']['X-API-KEY'], 'test-key')

    @override_settings(
        GIGO_API_URL="http://localhost:8001/api",
        GIGO_API_KEY="test-key",
        GIGO_BAND_ID_LOCAL=1,
        DEBUG=False
    )
    @patch('requests.post')
    def test_production_band_invite(self, mock_post):
        """Test that production mode fails when no GIGO_BAND_ID is set"""
        # When DEBUG=False and GIGO_BAND_ID is not set, should return error
        result = send_member_to_go3_band_invite(self.test_email, use_local_band=False)

        self.assertEqual(result['status'], 'error')
        self.assertIn('not configured', result['message'])

    @override_settings(
        GIGO_API_URL="http://localhost:8001/api",
        GIGO_API_KEY="test-key",
        GIGO_BAND_ID_LOCAL=1
    )
    @patch('requests.post')
    def test_member_already_in_band(self, mock_post):
        """Test handling of member already in band response"""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            'invited': [],
            'in_band': [self.test_email],
            'invalid': []
        }
        mock_response.raise_for_status.return_value = None
        mock_post.return_value = mock_response

        result = send_member_to_go3_band_invite(self.test_email, use_local_band=True)

        self.assertEqual(result['status'], 'success')
        self.assertEqual(result['message'], 'Member already in band')
        self.assertTrue(result['in_band'])
        self.assertFalse(result['invalid'])

    @override_settings(
        GIGO_API_URL="http://localhost:8001/api",
        GIGO_API_KEY="test-key",
        GIGO_BAND_ID_LOCAL=1
    )
    @patch('requests.post')
    def test_invalid_email(self, mock_post):
        """Test handling of invalid email response"""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            'invited': [],
            'in_band': [],
            'invalid': [self.test_email]
        }
        mock_response.raise_for_status.return_value = None
        mock_post.return_value = mock_response

        result = send_member_to_go3_band_invite(self.test_email, use_local_band=True)

        self.assertEqual(result['status'], 'error')
        self.assertEqual(result['message'], 'Invalid email address')
        self.assertFalse(result['in_band'])
        self.assertTrue(result['invalid'])

    @override_settings(
        GIGO_API_URL=None,
        GIGO_API_KEY="test-key",
        GIGO_BAND_ID_LOCAL=1
    )
    def test_missing_api_url(self):
        """Test error handling when GO3_API_URL is not configured"""
        result = send_member_to_go3_band_invite(self.test_email, use_local_band=True)

        self.assertEqual(result['status'], 'error')
        self.assertEqual(result['message'], 'GO3 band invite not configured')
        self.assertIsNone(result['data'])

    @override_settings(
        GIGO_API_URL="http://localhost:8001/api",
        GIGO_API_KEY=None,
        GIGO_BAND_ID_LOCAL=1
    )
    def test_missing_api_key(self):
        """Test error handling when GO3_API_KEY is not configured"""
        result = send_member_to_go3_band_invite(self.test_email, use_local_band=True)

        self.assertEqual(result['status'], 'error')
        self.assertEqual(result['message'], 'GO3 band invite not configured')

    @override_settings(
        GIGO_API_URL="http://localhost:8001/api",
        GIGO_API_KEY="test-key",
        GIGO_BAND_ID_LOCAL=None
    )
    def test_missing_band_id(self):
        """Test error handling when GO3_BAND_ID_LOCAL is not configured"""
        result = send_member_to_go3_band_invite(self.test_email, use_local_band=True)

        self.assertEqual(result['status'], 'error')
        self.assertEqual(result['message'], 'GO3 band invite not configured')

    @override_settings(
        GIGO_API_URL="http://localhost:8001/api",
        GIGO_API_KEY="test-key",
        GIGO_BAND_ID_LOCAL=1
    )
    @patch('requests.post')
    def test_timeout_error(self, mock_post):
        """Test handling of timeout errors"""
        import requests
        mock_post.side_effect = requests.exceptions.Timeout()

        result = send_member_to_go3_band_invite(self.test_email, use_local_band=True)

        self.assertEqual(result['status'], 'error')
        self.assertEqual(result['message'], 'Timeout connecting to GO3')

    @override_settings(
        GIGO_API_URL="http://localhost:8001/api",
        GIGO_API_KEY="test-key",
        GIGO_BAND_ID_LOCAL=1
    )
    @patch('requests.post')
    def test_connection_error(self, mock_post):
        """Test handling of connection errors"""
        import requests
        mock_post.side_effect = requests.exceptions.ConnectionError()

        result = send_member_to_go3_band_invite(self.test_email, use_local_band=True)

        self.assertEqual(result['status'], 'error')
        self.assertEqual(result['message'], 'Could not connect to GO3')

    @override_settings(
        GIGO_API_URL="http://localhost:8001/api",
        GIGO_API_KEY="test-key",
        GIGO_BAND_ID_LOCAL=1
    )
    @patch('requests.post')
    def test_http_error(self, mock_post):
        """Test handling of HTTP errors"""
        import requests
        mock_response = MagicMock()
        mock_response.status_code = 403
        mock_response.raise_for_status.side_effect = requests.exceptions.HTTPError(response=mock_response)
        mock_post.return_value = mock_response

        result = send_member_to_go3_band_invite(self.test_email, use_local_band=True)

        self.assertEqual(result['status'], 'error')
        self.assertIn('HTTP error', result['message'])

    @override_settings(
        GIGO_API_URL="http://localhost:8001/api",
        GIGO_API_KEY="test-key",
        GIGO_BAND_ID_LOCAL=1
    )
    @patch('requests.post')
    def test_generic_exception(self, mock_post):
        """Test handling of generic exceptions"""
        mock_post.side_effect = Exception("Something went wrong")

        result = send_member_to_go3_band_invite(self.test_email, use_local_band=True)

        self.assertEqual(result['status'], 'error')
        self.assertIn('Error sending invite', result['message'])


class MemberSignupGO3IntegrationTests(TestCase):
    """Test cases for member signup view with GO3 integration"""

    def setUp(self):
        """Set up test data"""
        self.client = Client()
        self.site = Site.objects.get(is_default_site=True)
        
        # Create site settings
        SiteSettings.objects.create(
            site=self.site,
            member_signup_notification_recipients='admin@example.com'
        )
        
        # Create a test instrument
        section = Section.objects.create(name="Test Section")
        self.instrument = Instrument.objects.create(
            name="Test Instrument",
            section=section
        )

    @override_settings(
        GIGO_API_URL="http://localhost:8001/api",
        GIGO_API_KEY="test-key",
        GIGO_BAND_ID_LOCAL=1,
        DEBUG=True
    )
    @patch('blowcomotion.views.send_member_to_go3_band_invite')
    @patch('blowcomotion.views._send_form_email')
    def test_signup_calls_go3_invite(self, mock_email, mock_go3_invite):
        """Test that signup view calls GO3 invite API"""
        mock_go3_invite.return_value = {
            'status': 'success',
            'message': 'Invitation sent successfully',
            'data': {}
        }
        
        form_data = {
            'first_name': 'John',
            'last_name': 'Doe',
            'email': 'john@example.com',
            'primary_instrument': self.instrument.pk
        }
        
        response = self.client.post(reverse('member-signup'), form_data)
        
        # Verify the member was created
        member = Member.objects.get(email='john@example.com')
        self.assertEqual(member.first_name, 'John')
        
        # Verify GO3 invite was called with the correct email
        mock_go3_invite.assert_called_once_with('john@example.com', use_local_band=True)

    @override_settings(
        GIGO_API_URL="http://localhost:8001/api",
        GIGO_API_KEY="test-key",
        GIGO_BAND_ID_LOCAL=1,
        DEBUG=True
    )
    def test_signup_without_email_fails_validation(self):
        """Test that signup requires email field (needed for GO3 invite)"""
        form_data = {
            'first_name': 'Jane',
            'last_name': 'Doe',
            'primary_instrument': self.instrument.pk
        }
        
        # Submit form without email
        response = self.client.post(reverse('member-signup'), form_data)
        
        # Since email is required and not provided, member should not be created
        self.assertFalse(Member.objects.filter(first_name='Jane').exists())
        
        # Response should not redirect (form re-rendered with errors)
        self.assertEqual(response.status_code, 200)
        self.assertIn('This field is required', response.content.decode())

    @override_settings(
        GIGO_API_URL="http://localhost:8001/api",
        GIGO_API_KEY="test-key",
        GIGO_BAND_ID_LOCAL=1,
        DEBUG=True
    )
    @patch('blowcomotion.views.send_member_to_go3_band_invite')
    @patch('blowcomotion.views._send_form_email')
    def test_signup_continues_on_go3_failure(self, mock_email, mock_go3_invite):
        """Test that signup continues even if GO3 invite fails"""
        mock_go3_invite.return_value = {
            'status': 'error',
            'message': 'Could not connect to GO3',
            'data': None
        }
        
        form_data = {
            'first_name': 'Bob',
            'last_name': 'Smith',
            'email': 'bob@example.com',
            'primary_instrument': self.instrument.pk
        }
        
        response = self.client.post(reverse('member-signup'), form_data)
        
        # Verify the member was created despite GO3 failure
        member = Member.objects.get(email='bob@example.com')
        self.assertEqual(member.first_name, 'Bob')
        
        # Verify we still sent the success page
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'Thank you for signing up', response.content)

    @override_settings(
        GIGO_API_URL="http://localhost:8001/api",
        GIGO_API_KEY="test-key",
        GIGO_BAND_ID_LOCAL=1,
        GIGO_BAND_ID=999,
        DEBUG=False  # Production mode
    )
    @patch('blowcomotion.views.send_member_to_go3_band_invite')
    @patch('blowcomotion.views._send_form_email')
    def test_signup_uses_production_band_in_production(self, mock_email, mock_go3_invite):
        """Test that production mode uses production band ID"""
        mock_go3_invite.return_value = {
            'status': 'success',
            'message': 'Invitation sent successfully',
            'data': {}
        }
        
        form_data = {
            'first_name': 'Alice',
            'last_name': 'Johnson',
            'email': 'alice@example.com',
            'primary_instrument': self.instrument.pk
        }
        
        response = self.client.post(reverse('member-signup'), form_data)
        
        # Verify GO3 was called with use_local_band=False (production mode)
        mock_go3_invite.assert_called_once_with('alice@example.com', use_local_band=False)
        
        # Verify the API was called with production band ID
        args, kwargs = mock_go3_invite.call_args
        self.assertNotIn('/1/invites', args)  # Should not be local band

    @override_settings(
        GIGO_API_URL="http://localhost:8001/api",
        GIGO_API_KEY="test-key",
        GIGO_BAND_ID_LOCAL=1,
        DEBUG=True
    )
    @patch('blowcomotion.views.send_member_to_go3_band_invite')
    @patch('blowcomotion.views._send_form_email')
    def test_admin_email_sent_after_go3_invite(self, mock_email, mock_go3_invite):
        """Test that admin notification email is sent after GO3 invite"""
        mock_go3_invite.return_value = {
            'status': 'success',
            'message': 'Invitation sent successfully',
            'data': {}
        }
        
        form_data = {
            'first_name': 'Charlie',
            'last_name': 'Brown',
            'email': 'charlie@example.com',
            'primary_instrument': self.instrument.pk,
            'phone': '555-1234'
        }
        
        response = self.client.post(reverse('member-signup'), form_data)
        
        # Verify emails were sent
        self.assertEqual(mock_email.call_count, 2)  # One to admin, one to member
        
        # Verify first call was admin notification
        first_call_args = mock_email.call_args_list[0]
        self.assertEqual(first_call_args[1]['subject'], 'New Member Signup')
        
        # Verify second call was member confirmation
        second_call_args = mock_email.call_args_list[1]
        self.assertEqual(second_call_args[1]['subject'], 'Welcome to Blowcomotion - Application Received')
