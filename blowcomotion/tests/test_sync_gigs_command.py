"""
Tests for the sync_gigs management command.
"""
import datetime
from io import StringIO
from unittest.mock import patch

from django.core.management import call_command
from django.test import TestCase, override_settings

from blowcomotion.models import CachedGig


class SyncGigsCommandTests(TestCase):
    """Test cases for sync_gigs management command."""
    
    def setUp(self):
        """Set up test data."""
        # Clear any existing cached gigs
        CachedGig.objects.all().delete()
    
    def test_sync_gigs_missing_api_settings(self):
        """Test that command fails gracefully when API settings are missing."""
        with override_settings(GIGO_API_URL=None, GIGO_API_KEY=None):
            out = StringIO()
            call_command('sync_gigs', stdout=out)
            output = out.getvalue()
            self.assertIn('not configured', output.lower())
    
    @override_settings(
        GIGO_API_URL='http://test-api/api',
        GIGO_API_KEY='test-key',
        GIGO_BAND_NAME='TestBand'
    )
    @patch('blowcomotion.management.commands.sync_gigs.make_gigo_api_request')
    def test_sync_gigs_creates_new_gigs(self, mock_request):
        """Test that sync creates new CachedGig records."""
        # Mock API response
        mock_request.return_value = {
            'gigs': [
                {
                    'id': 123,
                    'title': 'Test Concert',
                    'date': '2026-07-15',
                    'call_time': '18:00',
                    'address': 'Test Venue',
                    'gig_status': 'confirmed',
                    'band': 'TestBand',
                }
            ]
        }
        
        out = StringIO()
        call_command('sync_gigs', stdout=out, verbosity=2)
        
        # Verify gig was created
        self.assertEqual(CachedGig.objects.count(), 1)
        gig = CachedGig.objects.first()
        self.assertEqual(gig.gig_id, 123)
        self.assertEqual(gig.title, 'Test Concert')
        self.assertEqual(gig.band, 'TestBand')
        
        output = out.getvalue()
        self.assertIn('1 created', output)
    
    @override_settings(
        GIGO_API_URL='http://test-api/api',
        GIGO_API_KEY='test-key',
        GIGO_BAND_NAME='TestBand'
    )
    @patch('blowcomotion.management.commands.sync_gigs.make_gigo_api_request')
    def test_sync_gigs_updates_existing_gigs(self, mock_request):
        """Test that sync updates existing CachedGig records."""
        # Create existing gig
        CachedGig.objects.create(
            gig_id=123,
            title='Old Title',
            date=datetime.date(2026, 7, 15),
            time=datetime.time(18, 0),
            address='Old Venue',
            gig_status='confirmed',
            band='TestBand',
        )
        
        # Mock API response with updated data
        mock_request.return_value = {
            'gigs': [
                {
                    'id': 123,
                    'title': 'Updated Concert',
                    'date': '2026-07-15',
                    'call_time': '19:00',
                    'address': 'New Venue',
                    'gig_status': 'confirmed',
                    'band': 'TestBand',
                }
            ]
        }
        
        out = StringIO()
        call_command('sync_gigs', stdout=out, verbosity=2)
        
        # Verify gig was updated
        self.assertEqual(CachedGig.objects.count(), 1)
        gig = CachedGig.objects.first()
        self.assertEqual(gig.title, 'Updated Concert')
        self.assertEqual(gig.address, 'New Venue')
        # Time is converted from UTC to Central (19:00 UTC -> 14:00 CDT in July)
        self.assertEqual(gig.time, datetime.time(14, 0))
        
        output = out.getvalue()
        self.assertIn('1 updated', output)
    
    @override_settings(
        GIGO_API_URL='http://test-api/api',
        GIGO_API_KEY='test-key',
        GIGO_BAND_NAME='TestBand'
    )
    @patch('blowcomotion.management.commands.sync_gigs.make_gigo_api_request')
    def test_sync_gigs_filters_by_band(self, mock_request):
        """Test that sync filters gigs by GIGO_BAND_NAME."""
        # Mock API response with mixed bands
        mock_request.return_value = {
            'gigs': [
                {
                    'id': 123,
                    'title': 'Test Concert',
                    'date': '2026-07-15',
                    'call_time': '18:00',
                    'address': 'Test Venue',
                    'gig_status': 'confirmed',
                    'band': 'TestBand',
                },
                {
                    'id': 124,
                    'title': 'Other Concert',
                    'date': '2026-07-16',
                    'call_time': '19:00',
                    'address': 'Other Venue',
                    'gig_status': 'confirmed',
                    'band': 'OtherBand',
                },
            ]
        }
        
        out = StringIO()
        call_command('sync_gigs', stdout=out, verbosity=2)
        
        # Verify only TestBand gig was created
        self.assertEqual(CachedGig.objects.count(), 1)
        gig = CachedGig.objects.first()
        self.assertEqual(gig.band, 'TestBand')
        
        output = out.getvalue()
        self.assertIn('Filtered to 1 gigs', output)
    
    @override_settings(
        GIGO_API_URL='http://test-api/api',
        GIGO_API_KEY='test-key',
        GIGO_BAND_NAME='TestBand'
    )
    @patch('blowcomotion.management.commands.sync_gigs.make_gigo_api_request')
    def test_sync_gigs_dry_run(self, mock_request):
        """Test that dry run doesn't save changes."""
        # Mock API response
        mock_request.return_value = {
            'gigs': [
                {
                    'id': 123,
                    'title': 'Test Concert',
                    'date': '2026-07-15',
                    'call_time': '18:00',
                    'address': 'Test Venue',
                    'gig_status': 'confirmed',
                    'band': 'TestBand',
                }
            ]
        }
        
        out = StringIO()
        call_command('sync_gigs', '--dry-run', stdout=out, verbosity=2)
        
        # Verify no gigs were created
        self.assertEqual(CachedGig.objects.count(), 0)
        
        output = out.getvalue()
        self.assertIn('DRY RUN', output)
        self.assertIn('would be created', output)
    
    @override_settings(
        GIGO_API_URL='http://test-api/api',
        GIGO_API_KEY='test-key',
        GIGO_BAND_NAME='TestBand'
    )
    @patch('blowcomotion.management.commands.sync_gigs.make_gigo_api_request')
    def test_sync_gigs_skips_invalid_gigs(self, mock_request):
        """Test that sync skips gigs with invalid data."""
        # Mock API response with invalid gigs
        mock_request.return_value = {
            'gigs': [
                {
                    # Missing ID
                    'title': 'No ID Concert',
                    'date': '2026-07-15',
                    'call_time': '18:00',
                    'address': 'Test Venue',
                    'gig_status': 'confirmed',
                    'band': 'TestBand',
                },
                {
                    'id': 124,
                    'title': 'Invalid Date Concert',
                    'date': 'not-a-date',
                    'call_time': '18:00',
                    'address': 'Test Venue',
                    'gig_status': 'confirmed',
                    'band': 'TestBand',
                },
                {
                    'id': 125,
                    'title': 'Valid Concert',
                    'date': '2026-07-15',
                    'call_time': '18:00',
                    'address': 'Test Venue',
                    'gig_status': 'confirmed',
                    'band': 'TestBand',
                },
            ]
        }
        
        out = StringIO()
        call_command('sync_gigs', stdout=out, verbosity=2)
        
        # Verify only valid gig was created
        self.assertEqual(CachedGig.objects.count(), 1)
        gig = CachedGig.objects.first()
        self.assertEqual(gig.title, 'Valid Concert')
        
        output = out.getvalue()
        self.assertIn('2 errors', output)
    
    @override_settings(
        GIGO_API_URL='http://test-api/api',
        GIGO_API_KEY='test-key',
        GIGO_BAND_NAME='TestBand'
    )
    @patch('blowcomotion.management.commands.sync_gigs.make_gigo_api_request')
    def test_sync_gigs_handles_api_failure(self, mock_request):
        """Test that sync handles API request failures gracefully."""
        # Mock API failure
        mock_request.return_value = None
        
        out = StringIO()
        call_command('sync_gigs', stdout=out)
        
        output = out.getvalue()
        self.assertIn('failed to fetch', output.lower())
