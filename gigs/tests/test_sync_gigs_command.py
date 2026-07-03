"""
Tests for the sync_gigs management command.
"""
import datetime
from io import StringIO
from unittest.mock import patch

from django.core.management import call_command
from django.test import TestCase, override_settings

from blowcomotion.models import CachedGig

# Use a fixed future date for testing
TEST_DATE = datetime.date(2027, 7, 15)


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
    @patch('gigs.management.commands.sync_gigs.make_gigo_api_request')
    def test_sync_gigs_creates_new_gigs(self, mock_request):
        """Test that sync creates new CachedGig records."""
        # Mock API response
        mock_request.return_value = {
            'gigs': [
                {
                    'id': 123,
                    'title': 'Test Concert',
                    'date': TEST_DATE.strftime('%Y-%m-%d'),
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
    @patch('gigs.management.commands.sync_gigs.make_gigo_api_request')
    def test_sync_gigs_updates_existing_gigs(self, mock_request):
        """Test that sync updates existing CachedGig records."""
        # Create existing gig
        CachedGig.objects.create(
            gig_id=123,
            title='Old Title',
            date=TEST_DATE,
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
                    'date': TEST_DATE.strftime('%Y-%m-%d'),
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
    @patch('gigs.management.commands.sync_gigs.make_gigo_api_request')
    def test_sync_gigs_filters_by_band(self, mock_request):
        """Test that sync filters gigs by GIGO_BAND_NAME."""
        # Mock API response with mixed bands
        mock_request.return_value = {
            'gigs': [
                {
                    'id': 123,
                    'title': 'Test Concert',
                    'date': TEST_DATE.strftime('%Y-%m-%d'),
                    'call_time': '18:00',
                    'address': 'Test Venue',
                    'gig_status': 'confirmed',
                    'band': 'TestBand',
                },
                {
                    'id': 124,
                    'title': 'Other Concert',
                    'date': (TEST_DATE + datetime.timedelta(days=1)).strftime('%Y-%m-%d'),
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
    @patch('gigs.management.commands.sync_gigs.make_gigo_api_request')
    def test_sync_gigs_dry_run(self, mock_request):
        """Test that dry run doesn't save changes."""
        # Mock API response
        mock_request.return_value = {
            'gigs': [
                {
                    'id': 123,
                    'title': 'Test Concert',
                    'date': TEST_DATE.strftime('%Y-%m-%d'),
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
    @patch('gigs.management.commands.sync_gigs.make_gigo_api_request')
    def test_sync_gigs_skips_invalid_gigs(self, mock_request):
        """Test that sync skips gigs with invalid data."""
        # Mock API response with invalid gigs
        mock_request.return_value = {
            'gigs': [
                {
                    # Missing ID
                    'title': 'No ID Concert',
                    'date': TEST_DATE.strftime('%Y-%m-%d'),
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
                    'date': TEST_DATE.strftime('%Y-%m-%d'),
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
        # Missing ID causes error during processing
        self.assertIn('1 errors', output)
        # Invalid date gig should be reported as having an invalid date, not as a past gig
        self.assertIn('Skipped 1 gigs with invalid dates', output)
    
    @override_settings(
        GIGO_API_URL='http://test-api/api',
        GIGO_API_KEY='test-key',
        GIGO_BAND_NAME='TestBand'
    )
    @patch('gigs.management.commands.sync_gigs.make_gigo_api_request')
    def test_sync_gigs_handles_api_failure(self, mock_request):
        """Test that sync handles API request failures gracefully."""
        # Mock API failure
        mock_request.return_value = None
        
        out = StringIO()
        call_command('sync_gigs', stdout=out)
        
        output = out.getvalue()
        self.assertIn('failed to fetch', output.lower())
    
    @override_settings(
        GIGO_API_URL='http://test-api/api',
        GIGO_API_KEY='test-key',
        GIGO_BAND_NAME='TestBand'
    )
    @patch('gigs.management.commands.sync_gigs.make_gigo_api_request')
    def test_sync_gigs_filters_past_gigs(self, mock_request):
        """Test that sync filters out gigs before today's date."""
        past_date = datetime.date.today() - datetime.timedelta(days=7)
        
        # Mock API response with past and future gigs
        mock_request.return_value = {
            'gigs': [
                {
                    'id': 123,
                    'title': 'Past Concert',
                    'date': past_date.strftime('%Y-%m-%d'),
                    'call_time': '18:00',
                    'address': 'Test Venue',
                    'gig_status': 'confirmed',
                    'band': 'TestBand',
                },
                {
                    'id': 124,
                    'title': 'Future Concert',
                    'date': TEST_DATE.strftime('%Y-%m-%d'),
                    'call_time': '19:00',
                    'address': 'Test Venue',
                    'gig_status': 'confirmed',
                    'band': 'TestBand',
                },
            ]
        }
        
        out = StringIO()
        call_command('sync_gigs', stdout=out, verbosity=2)
        
        # Verify only future gig was created
        self.assertEqual(CachedGig.objects.count(), 1)
        gig = CachedGig.objects.first()
        self.assertEqual(gig.title, 'Future Concert')
        
        output = out.getvalue()
        self.assertIn('Filtered out 1 past gigs', output)
    
    @override_settings(
        GIGO_API_URL='http://test-api/api',
        GIGO_API_KEY='test-key',
        GIGO_BAND_NAME='TestBand'
    )
    @patch('gigs.management.commands.sync_gigs.make_gigo_api_request')
    def test_sync_gigs_deletes_old_cached_gigs(self, mock_request):
        """Test that sync deletes cached gigs before today's date."""
        past_date = datetime.date.today() - datetime.timedelta(days=7)
        
        # Create old cached gig
        CachedGig.objects.create(
            gig_id=999,
            title='Old Cached Concert',
            date=past_date,
            time=datetime.time(18, 0),
            address='Old Venue',
            gig_status='confirmed',
            band='TestBand',
        )
        
        # Mock API response with only future gigs
        mock_request.return_value = {
            'gigs': [
                {
                    'id': 124,
                    'title': 'Future Concert',
                    'date': TEST_DATE.strftime('%Y-%m-%d'),
                    'call_time': '19:00',
                    'address': 'Test Venue',
                    'gig_status': 'confirmed',
                    'band': 'TestBand',
                },
            ]
        }
        
        out = StringIO()
        call_command('sync_gigs', stdout=out, verbosity=2)
        
        # Verify old gig was deleted and only future gig exists
        self.assertEqual(CachedGig.objects.count(), 1)
        gig = CachedGig.objects.first()
        self.assertEqual(gig.title, 'Future Concert')
        
        output = out.getvalue()
        self.assertIn('Deleted 1 cached gigs', output)
    
    @override_settings(
        GIGO_API_URL='http://test-api/api',
        GIGO_API_KEY='test-key',
        GIGO_BAND_NAME='TestBand'
    )
    @patch('gigs.management.commands.sync_gigs.make_gigo_api_request')
    def test_sync_gigs_dry_run_deletes_old_gigs(self, mock_request):
        """Test that dry run reports old gigs that would be deleted."""
        past_date = datetime.date.today() - datetime.timedelta(days=7)
        
        # Create old cached gig
        CachedGig.objects.create(
            gig_id=999,
            title='Old Cached Concert',
            date=past_date,
            time=datetime.time(18, 0),
            address='Old Venue',
            gig_status='confirmed',
            band='TestBand',
        )
        
        # Mock API response
        mock_request.return_value = {
            'gigs': [
                {
                    'id': 124,
                    'title': 'Future Concert',
                    'date': TEST_DATE.strftime('%Y-%m-%d'),
                    'call_time': '19:00',
                    'address': 'Test Venue',
                    'gig_status': 'confirmed',
                    'band': 'TestBand',
                },
            ]
        }
        
        out = StringIO()
        call_command('sync_gigs', '--dry-run', stdout=out, verbosity=2)
        
        # Verify old gig was NOT deleted in dry run
        self.assertEqual(CachedGig.objects.filter(gig_id=999).count(), 1)
        
        output = out.getvalue()
        self.assertIn('Would delete 1 cached gigs', output)
    
    @override_settings(
        GIGO_API_URL='http://test-api/api',
        GIGO_API_KEY='test-key',
        GIGO_BAND_NAME='TestBand'
    )
    @patch('gigs.management.commands.sync_gigs.make_gigo_api_request')
    def test_sync_gigs_reports_invalid_dates_verbosely(self, mock_request):
        """Test that sync reports detailed invalid date warnings at verbosity=2."""
        # Mock API response with invalid date
        mock_request.return_value = {
            'gigs': [
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
                    'date': TEST_DATE.strftime('%Y-%m-%d'),
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
        # At verbosity=2, should see detailed invalid date warning
        self.assertIn('Skipping gig with invalid date', output)
        self.assertIn('not-a-date', output)
        self.assertIn('124', output)
        # Should also see summary of skipped gigs
        self.assertIn('Skipped 1 gigs with invalid dates', output)
