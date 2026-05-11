"""
Tests for fetch_embed_data view endpoint.
"""

from unittest.mock import Mock, patch

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.test import Client, TestCase

User = get_user_model()


class FetchEmbedDataViewTests(TestCase):
    """Test cases for fetch_embed_data admin endpoint"""

    def setUp(self):
        self.client = Client()
        self.url = '/admin/embeds/fetch/'
        
        # Create superuser (has all permissions including Wagtail admin access)
        self.admin_user = User.objects.create_superuser(
            username='admin',
            password='testpass',
            email='admin@test.com'
        )
        
        # Create staff user with Wagtail admin access
        self.staff_user = User.objects.create_user(
            username='staff',
            password='testpass',
            is_staff=True
        )
        # Add Wagtail admin access permission
        try:
            admin_permission = Permission.objects.get(
                content_type__app_label='wagtailadmin',
                codename='access_admin'
            )
            self.staff_user.user_permissions.add(admin_permission)
        except Permission.DoesNotExist:
            pass  # Permission might not exist in test DB
        
        self.regular_user = User.objects.create_user(
            username='regular',
            password='testpass',
            is_staff=False
        )

    def test_requires_authentication(self):
        """Test that unauthenticated requests are redirected to login"""
        response = self.client.post(self.url, {'url': 'https://www.youtube.com/watch?v=test'})
        self.assertEqual(response.status_code, 302)

    def test_requires_staff_status(self):
        """Test that non-staff users are rejected"""
        self.client.login(username='regular', password='testpass')
        response = self.client.post(self.url, {'url': 'https://www.youtube.com/watch?v=test'})
        self.assertEqual(response.status_code, 302)  # Redirected by Wagtail admin

    def test_requires_url_parameter(self):
        """Test that missing URL parameter returns 400"""
        self.client.login(username='admin', password='testpass')
        response = self.client.post(self.url, {})
        self.assertEqual(response.status_code, 400)
        data = response.json()
        self.assertIn('error', data)
        self.assertEqual(data['error'], 'URL parameter is required')

    def test_rejects_non_http_schemes(self):
        """Test that non-HTTP(S) URLs are rejected"""
        self.client.login(username='admin', password='testpass')
        
        invalid_urls = [
            'ftp://example.com/video',
            'file:///etc/passwd',
        ]
        
        for url in invalid_urls:
            with self.subTest(url=url):
                response = self.client.post(self.url, {'url': url})
                self.assertEqual(response.status_code, 400)
                self.assertIn('HTTP/HTTPS', response.json()['error'])

    def test_rejects_urls_without_hostname(self):
        """Test that URLs without hostname are rejected"""
        self.client.login(username='admin', password='testpass')
        response = self.client.post(self.url, {'url': 'http://'})
        self.assertEqual(response.status_code, 400)
        data = response.json()
        self.assertIn('missing hostname', data['error'])

    def test_rejects_non_allowlisted_domains(self):
        """Test that non-YouTube/Vimeo URLs are rejected"""
        self.client.login(username='admin', password='testpass')
        
        disallowed_urls = [
            'https://example.com/video',
            'https://evilyoutube.com/video',  # Bypass attempt
            'https://youtube.com.evil.com/video',  # Another bypass
            'https://dailymotion.com/video',
        ]
        
        for url in disallowed_urls:
            with self.subTest(url=url):
                response = self.client.post(self.url, {'url': url})
                self.assertEqual(response.status_code, 400)
                self.assertIn('YouTube and Vimeo', response.json()['error'])

    @patch('wagtail.embeds.embeds.get_embed')
    def test_allows_youtube_domains(self, mock_get_embed):
        """Test that YouTube URLs are accepted"""
        self.client.login(username='admin', password='testpass')
        
        mock_embed = Mock()
        mock_embed.title = 'Test Video'
        mock_embed.thumbnail_url = 'https://example.com/thumb.jpg'
        mock_embed.author_name = 'Test Author'
        mock_embed.provider_name = 'YouTube'
        mock_get_embed.return_value = mock_embed
        
        youtube_urls = [
            'https://www.youtube.com/watch?v=test',
            'https://youtube.com/watch?v=test',
            'https://m.youtube.com/watch?v=test',
            'https://youtu.be/test',
        ]
        
        for url in youtube_urls:
            with self.subTest(url=url):
                response = self.client.post(self.url, {'url': url})
                self.assertEqual(response.status_code, 200, f"Failed for {url}")

    @patch('wagtail.embeds.embeds.get_embed')
    def test_handles_urls_with_ports(self, mock_get_embed):
        """Test that URLs with explicit ports are handled correctly"""
        self.client.login(username='admin', password='testpass')
        
        mock_embed = Mock()
        mock_embed.title = 'Test Video'
        mock_embed.thumbnail_url = 'https://example.com/thumb.jpg'
        mock_embed.author_name = 'Test Author'
        mock_embed.provider_name = 'YouTube'
        mock_get_embed.return_value = mock_embed
        
        response = self.client.post(self.url, {'url': 'https://www.youtube.com:443/watch?v=test'})
        self.assertEqual(response.status_code, 200)

    @patch('wagtail.embeds.embeds.get_embed')
    def test_successful_response_structure(self, mock_get_embed):
        """Test that successful response has correct structure"""
        self.client.login(username='admin', password='testpass')
        
        mock_embed = Mock()
        mock_embed.title = 'Test Video Title'
        mock_embed.thumbnail_url = 'https://example.com/thumb.jpg'
        mock_embed.author_name = 'Test Author'
        mock_embed.provider_name = 'YouTube'
        mock_get_embed.return_value = mock_embed
        
        response = self.client.post(self.url, {'url': 'https://www.youtube.com/watch?v=test123'})
        
        self.assertEqual(response.status_code, 200)
        data = response.json()
        
        self.assertIn('title', data)
        self.assertIn('thumbnail_url', data)
        self.assertIn('author_name', data)
        self.assertIn('provider_name', data)
        
        self.assertEqual(data['title'], 'Test Video Title')
        self.assertEqual(data['thumbnail_url'], 'https://example.com/thumb.jpg')
        self.assertEqual(data['author_name'], 'Test Author')
        self.assertEqual(data['provider_name'], 'YouTube')

    @patch('wagtail.embeds.embeds.get_embed')
    def test_handles_embed_exception(self, mock_get_embed):
        """Test that EmbedException is handled gracefully"""
        from wagtail.embeds.exceptions import EmbedException
        
        self.client.login(username='admin', password='testpass')
        mock_get_embed.side_effect = EmbedException('Embed not found')
        
        response = self.client.post(self.url, {'url': 'https://www.youtube.com/watch?v=invalid'})
        
        self.assertEqual(response.status_code, 400)
        self.assertIn('error', response.json())
        self.assertIn('Unable to fetch embed data', response.json()['error'])
