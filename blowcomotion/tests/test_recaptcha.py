"""
Unit tests for reCAPTCHA v3 validation in form submissions.
"""

from unittest.mock import MagicMock, patch

from django.test import Client, TestCase, override_settings
from django.urls import reverse

from blowcomotion.views import _validate_recaptcha


class ValidateRecaptchaFunctionTests(TestCase):
    """Test cases for the _validate_recaptcha helper function."""

    def _make_mock_request(self, post_data=None):
        """Create a mock request object with POST data."""
        mock_request = MagicMock()
        mock_request.POST = post_data or {}
        mock_request.META = {'REMOTE_ADDR': '127.0.0.1'}
        return mock_request

    def test_skips_validation_when_no_keys_configured(self):
        """When RECAPTCHA keys are not set, validation should be skipped."""
        mock_request = self._make_mock_request()
        
        with override_settings(RECAPTCHA_PUBLIC_KEY=None, RECAPTCHA_PRIVATE_KEY=None):
            is_valid, error = _validate_recaptcha(mock_request)
        
        self.assertTrue(is_valid)
        self.assertIsNone(error)

    def test_skips_validation_when_only_public_key_set(self):
        """When only public key is set, validation should be skipped."""
        mock_request = self._make_mock_request()
        
        with override_settings(RECAPTCHA_PUBLIC_KEY='test-public', RECAPTCHA_PRIVATE_KEY=None):
            is_valid, error = _validate_recaptcha(mock_request)
        
        self.assertTrue(is_valid)
        self.assertIsNone(error)

    @override_settings(RECAPTCHA_PUBLIC_KEY='test-public', RECAPTCHA_PRIVATE_KEY='test-private')
    def test_fails_when_token_missing(self):
        """When keys are configured but token is missing, validation should fail."""
        mock_request = self._make_mock_request({'some_field': 'value'})
        
        is_valid, error = _validate_recaptcha(mock_request)
        
        self.assertFalse(is_valid)
        self.assertEqual(error, "reCAPTCHA verification failed. Please try again.")

    @override_settings(RECAPTCHA_PUBLIC_KEY='test-public', RECAPTCHA_PRIVATE_KEY='test-private')
    @patch('blowcomotion.views.requests.post')
    def test_fails_when_google_returns_success_false(self, mock_post):
        """When Google returns success=false, validation should fail."""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            'success': False,
            'error-codes': ['invalid-input-response']
        }
        mock_response.raise_for_status = MagicMock()
        mock_post.return_value = mock_response

        mock_request = self._make_mock_request({'g-recaptcha-response': 'test-token'})
        
        is_valid, error = _validate_recaptcha(mock_request)
        
        self.assertFalse(is_valid)
        self.assertEqual(error, "reCAPTCHA verification failed. Please try again.")

    @override_settings(RECAPTCHA_PUBLIC_KEY='test-public', RECAPTCHA_PRIVATE_KEY='test-private', RECAPTCHA_REQUIRED_SCORE=0.5)
    @patch('blowcomotion.views.requests.post')
    def test_fails_when_score_too_low(self, mock_post):
        """When reCAPTCHA score is below threshold, validation should fail."""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            'success': True,
            'score': 0.3,  # Below 0.5 threshold
            'action': 'submit'
        }
        mock_response.raise_for_status = MagicMock()
        mock_post.return_value = mock_response

        mock_request = self._make_mock_request({'g-recaptcha-response': 'test-token'})
        
        is_valid, error = _validate_recaptcha(mock_request)
        
        self.assertFalse(is_valid)
        self.assertEqual(error, "reCAPTCHA verification failed. Please try again.")

    @override_settings(RECAPTCHA_PUBLIC_KEY='test-public', RECAPTCHA_PRIVATE_KEY='test-private')
    @patch('blowcomotion.views.requests.post')
    def test_fails_when_score_missing(self, mock_post):
        """When reCAPTCHA score is missing (fail closed), validation should fail."""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            'success': True,
            # No 'score' key - unexpected for v3
        }
        mock_response.raise_for_status = MagicMock()
        mock_post.return_value = mock_response

        mock_request = self._make_mock_request({'g-recaptcha-response': 'test-token'})
        
        is_valid, error = _validate_recaptcha(mock_request)
        
        self.assertFalse(is_valid)
        self.assertEqual(error, "reCAPTCHA verification failed. Please try again.")

    @override_settings(RECAPTCHA_PUBLIC_KEY='test-public', RECAPTCHA_PRIVATE_KEY='test-private', RECAPTCHA_REQUIRED_SCORE=0.5)
    @patch('blowcomotion.views.requests.post')
    def test_succeeds_when_score_meets_threshold(self, mock_post):
        """When reCAPTCHA score meets threshold, validation should succeed."""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            'success': True,
            'score': 0.9,  # Above 0.5 threshold
            'action': 'submit'
        }
        mock_response.raise_for_status = MagicMock()
        mock_post.return_value = mock_response

        mock_request = self._make_mock_request({'g-recaptcha-response': 'test-token'})
        
        is_valid, error = _validate_recaptcha(mock_request)
        
        self.assertTrue(is_valid)
        self.assertIsNone(error)

    @override_settings(RECAPTCHA_PUBLIC_KEY='test-public', RECAPTCHA_PRIVATE_KEY='test-private')
    @patch('blowcomotion.views.requests.post')
    def test_fails_on_api_request_exception(self, mock_post):
        """When Google API request fails, validation should fail closed."""
        import requests as req
        mock_post.side_effect = req.RequestException("Connection error")

        mock_request = self._make_mock_request({'g-recaptcha-response': 'test-token'})
        
        is_valid, error = _validate_recaptcha(mock_request)
        
        self.assertFalse(is_valid)
        self.assertEqual(error, "reCAPTCHA verification failed. Please try again.")

    @override_settings(RECAPTCHA_PUBLIC_KEY='test-public', RECAPTCHA_PRIVATE_KEY='test-private')
    @patch('blowcomotion.views.requests.post')
    def test_fails_on_invalid_json_response(self, mock_post):
        """When Google returns non-JSON response, validation should fail gracefully."""
        mock_response = MagicMock()
        mock_response.json.side_effect = ValueError("No JSON object could be decoded")
        mock_response.raise_for_status = MagicMock()
        mock_post.return_value = mock_response

        mock_request = self._make_mock_request({'g-recaptcha-response': 'test-token'})
        
        is_valid, error = _validate_recaptcha(mock_request)
        
        self.assertFalse(is_valid)
        self.assertEqual(error, "reCAPTCHA verification failed. Please try again.")

    @override_settings(RECAPTCHA_PUBLIC_KEY='test-public', RECAPTCHA_PRIVATE_KEY='test-private')
    @patch('blowcomotion.views.requests.post')
    def test_fails_on_http_error_status(self, mock_post):
        """When Google returns HTTP error, validation should fail."""
        import requests as req
        mock_response = MagicMock()
        mock_response.raise_for_status.side_effect = req.HTTPError("500 Server Error")
        mock_post.return_value = mock_response

        mock_request = self._make_mock_request({'g-recaptcha-response': 'test-token'})
        
        is_valid, error = _validate_recaptcha(mock_request)
        
        self.assertFalse(is_valid)
        self.assertEqual(error, "reCAPTCHA verification failed. Please try again.")


class ProcessFormRecaptchaIntegrationTests(TestCase):
    """Integration tests for reCAPTCHA validation in process_form view."""

    def setUp(self):
        """Set up test client."""
        self.client = Client()
        self.url = reverse('process-form')

    def test_form_submission_succeeds_without_recaptcha_when_keys_not_set(self):
        """Form submission should work when reCAPTCHA keys are not configured."""
        # Submit a simple feedback form (doesn't require email)
        response = self.client.post(self.url, {
            'form_type': 'feedback_form',
            'name': 'Test User',
            'message': 'Test message',
            'best_color': 'purple',  # Honeypot
        })
        
        # Should succeed (render success template)
        self.assertEqual(response.status_code, 200)
        # Check it's not the error template
        self.assertNotContains(response, 'reCAPTCHA verification failed')

    @override_settings(RECAPTCHA_PUBLIC_KEY='test-public', RECAPTCHA_PRIVATE_KEY='test-private')
    def test_form_submission_fails_when_recaptcha_token_missing(self):
        """Form submission should fail when reCAPTCHA is configured but token missing."""
        response = self.client.post(self.url, {
            'form_type': 'feedback_form',
            'name': 'Test User',
            'message': 'Test message',
            'best_color': 'purple',
            # No g-recaptcha-response
        })
        
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'reCAPTCHA verification failed')

    @override_settings(RECAPTCHA_PUBLIC_KEY='test-public', RECAPTCHA_PRIVATE_KEY='test-private', RECAPTCHA_REQUIRED_SCORE=0.5)
    @patch('blowcomotion.views.requests.post')
    def test_form_submission_fails_when_recaptcha_score_low(self, mock_post):
        """Form submission should fail when reCAPTCHA score is too low."""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            'success': True,
            'score': 0.2,  # Low score indicates bot
        }
        mock_response.raise_for_status = MagicMock()
        mock_post.return_value = mock_response

        response = self.client.post(self.url, {
            'form_type': 'feedback_form',
            'name': 'Test User',
            'message': 'Test message',
            'best_color': 'purple',
            'g-recaptcha-response': 'test-token',
        })
        
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'reCAPTCHA verification failed')

    @override_settings(RECAPTCHA_PUBLIC_KEY='test-public', RECAPTCHA_PRIVATE_KEY='test-private', RECAPTCHA_REQUIRED_SCORE=0.5)
    @patch('blowcomotion.views.requests.post')
    def test_form_submission_succeeds_when_recaptcha_valid(self, mock_post):
        """Form submission should succeed when reCAPTCHA validation passes."""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            'success': True,
            'score': 0.9,  # High score indicates human
        }
        mock_response.raise_for_status = MagicMock()
        mock_post.return_value = mock_response

        response = self.client.post(self.url, {
            'form_type': 'feedback_form',
            'name': 'Test User',
            'message': 'Test message',
            'best_color': 'purple',
            'g-recaptcha-response': 'test-token',
        })
        
        self.assertEqual(response.status_code, 200)
        # Should not contain error
        self.assertNotContains(response, 'reCAPTCHA verification failed')
