"""
Tests for Member model methods.
"""

from unittest.mock import MagicMock, patch

from django.conf import settings
from django.test import TestCase, override_settings

from blowcomotion.models import Instrument, Member, Section


class MemberGetGigoIdTests(TestCase):
    """Test cases for Member.get_gigo_id() method"""

    def setUp(self):
        """Set up test data"""
        # Create test sections and instruments
        self.brass_section = Section.objects.create(name='Brass')
        self.trumpet = Instrument.objects.create(name='Trumpet', section=self.brass_section)

    def test_returns_cached_gigomatic_id(self):
        """Test that get_gigo_id returns cached gigomatic_id if available"""
        member = Member.objects.create(
            first_name='John',
            last_name='Doe',
            email='john@example.com',
            primary_instrument=self.trumpet,
            gigomatic_id=123
        )
        
        # Should return cached value without making API call
        with patch('blowcomotion.utils.make_gigo_api_request') as mock_api:
            result = member.get_gigo_id()
            
            self.assertEqual(result, 123)
            mock_api.assert_not_called()

    def test_returns_none_when_no_email(self):
        """Test that get_gigo_id returns None when member has no email"""
        member = Member.objects.create(
            first_name='Jane',
            last_name='Doe',
            primary_instrument=self.trumpet
        )
        
        # Should return None without making API call
        with patch('blowcomotion.utils.make_gigo_api_request') as mock_api:
            result = member.get_gigo_id()
            
            self.assertIsNone(result)
            mock_api.assert_not_called()

    @override_settings(GIGO_API_URL='', GIGO_API_KEY='')
    def test_returns_none_when_api_not_configured(self):
        """Test that get_gigo_id returns None when API is not configured"""
        member = Member.objects.create(
            first_name='Bob',
            last_name='Smith',
            email='bob@example.com',
            primary_instrument=self.trumpet
        )
        
        with patch('blowcomotion.utils.make_gigo_api_request') as mock_api:
            result = member.get_gigo_id()
            
            self.assertIsNone(result)
            mock_api.assert_not_called()

    @override_settings(GIGO_API_URL='http://localhost:8000', GIGO_API_KEY='test-key')
    @patch('blowcomotion.utils.make_gigo_api_request')
    def test_queries_api_and_caches_result(self, mock_api):
        """Test that get_gigo_id queries API and caches the result"""
        mock_api.return_value = {
            'member_id': 456,
            'email': 'alice@example.com',
            'username': 'alice'
        }
        
        member = Member.objects.create(
            first_name='Alice',
            last_name='Johnson',
            email='alice@example.com',
            primary_instrument=self.trumpet
        )
        
        # First call should query API
        result = member.get_gigo_id()
        
        self.assertEqual(result, 456)
        mock_api.assert_called_once_with('/members/query?email=alice%40example.com')
        
        # Verify value was cached in database
        member.refresh_from_db()
        self.assertEqual(member.gigomatic_id, 456)

    @override_settings(GIGO_API_URL='http://localhost:8000', GIGO_API_KEY='test-key')
    @patch('blowcomotion.utils.make_gigo_api_request')
    def test_returns_none_when_member_not_found_in_api(self, mock_api):
        """Test that get_gigo_id returns None when member is not found in API"""
        mock_api.return_value = {}  # Empty response, member not found
        
        member = Member.objects.create(
            first_name='Charlie',
            last_name='Brown',
            email='charlie@example.com',
            primary_instrument=self.trumpet
        )
        mock_api.reset_mock()  # Reset after creation save
        
        result = member.get_gigo_id()
        
        self.assertIsNone(result)
        mock_api.assert_called_once()
        
        # Verify nothing was cached
        member.refresh_from_db()
        self.assertIsNone(member.gigomatic_id)

    @override_settings(GIGO_API_URL='http://localhost:8000', GIGO_API_KEY='test-key')
    @patch('blowcomotion.utils.make_gigo_api_request')
    def test_handles_api_errors_gracefully(self, mock_api):
        """Test that get_gigo_id handles API errors gracefully"""
        mock_api.side_effect = Exception('Connection timeout')
        
        member = Member.objects.create(
            first_name='David',
            last_name='Lee',
            email='david@example.com',
            primary_instrument=self.trumpet
        )
        mock_api.reset_mock()  # Reset after creation save
        
        result = member.get_gigo_id()
        
        self.assertIsNone(result)
        mock_api.assert_called_once()

    @override_settings(GIGO_API_URL='http://localhost:8000', GIGO_API_KEY='test-key')
    @patch('blowcomotion.utils.make_gigo_api_request')
    def test_handles_malformed_api_response(self, mock_api):
        """Test that get_gigo_id handles malformed API responses"""
        mock_api.return_value = {'wrong_key': 'value'}  # Missing member_id key
        
        member = Member.objects.create(
            first_name='Eve',
            last_name='Wilson',
            email='eve@example.com',
            primary_instrument=self.trumpet
        )
        
        result = member.get_gigo_id()
        
        self.assertIsNone(result)

    @override_settings(GIGO_API_URL='http://localhost:8000', GIGO_API_KEY='test-key')
    @patch('blowcomotion.utils.make_gigo_api_request')
    def test_subsequent_calls_use_cached_value(self, mock_api):
        """Test that subsequent calls use cached value instead of querying API"""
        mock_api.return_value = {
            'member_id': 789,
            'email': 'frank@example.com',
            'username': 'frank'
        }
        
        member = Member.objects.create(
            first_name='Frank',
            last_name='Miller',
            email='frank@example.com',
            primary_instrument=self.trumpet
        )
        
        # First call
        result1 = member.get_gigo_id()
        self.assertEqual(result1, 789)
        self.assertEqual(mock_api.call_count, 1)
        
        # Second call should use cached value
        result2 = member.get_gigo_id()
        self.assertEqual(result2, 789)
        self.assertEqual(mock_api.call_count, 1)  # Still only called once

    @override_settings(GIGO_API_URL='http://localhost:8000', GIGO_API_KEY='test-key')
    @patch('blowcomotion.utils.make_gigo_api_request')
    def test_handles_none_response_from_api(self, mock_api):
        """Test that get_gigo_id handles None response from API"""
        mock_api.return_value = None
        
        member = Member.objects.create(
            first_name='Grace',
            last_name='Taylor',
            email='grace@example.com',
            primary_instrument=self.trumpet
        )
        
        result = member.get_gigo_id()
        
        self.assertIsNone(result)

    @override_settings(GIGO_API_URL='http://localhost:8000', GIGO_API_KEY='test-key')
    @patch('blowcomotion.utils.make_gigo_api_request')
    def test_saves_only_gigomatic_id_field(self, mock_api):
        """Test that get_gigo_id only updates gigomatic_id field"""
        mock_api.return_value = {
            'member_id': 999,
            'email': 'henry@example.com',
            'username': 'henry'
        }
        
        member = Member.objects.create(
            first_name='Henry',
            last_name='Anderson',
            email='henry@example.com',
            primary_instrument=self.trumpet
        )
        
        # Modify member but don't save
        member.first_name = 'Hank'
        
        # Call get_gigo_id
        result = member.get_gigo_id()
        
        # Reload from database
        member.refresh_from_db()
        
        # gigomatic_id should be saved, but first_name should not
        self.assertEqual(member.gigomatic_id, 999)
        self.assertEqual(member.first_name, 'Henry')  # Not 'Hank'


class MemberSaveMethodTests(TestCase):
    """Test cases for Member.save() method with GO3 integration"""

    def setUp(self):
        """Set up test data"""
        self.brass_section = Section.objects.create(name='Brass')
        self.trumpet = Instrument.objects.create(name='Trumpet', section=self.brass_section)

    @override_settings(DEBUG=False, GIGO_BAND_ID='1', GIGO_API_URL='http://test', GIGO_API_KEY='test-key')
    @patch('blowcomotion.utils.make_gigo_api_request')
    def test_save_deactivating_member_updates_id_and_syncs_to_occasional(self, mock_api):
        """Test that deactivating updates member ID/username and marks them as occasional in GO3"""
        member = Member.objects.create(
            first_name='John',
            last_name='Doe',
            email='john@example.com',
            primary_instrument=self.trumpet,
            gigomatic_id=123,
            gigomatic_username='old_username',
            is_active=True
        )
        
        # Reset mock to ignore the creation save() call
        mock_api.reset_mock()
        
        mock_api.side_effect = [
            {'member_id': 999, 'email': 'john@example.com', 'username': 'johndoe'},
            {'is_occasional': True, 'member_id': 999, 'band_id': 1}
        ]
        
        member.is_active = False
        member.save()
        
        member.refresh_from_db()
        self.assertEqual(member.gigomatic_id, 999)
        self.assertEqual(member.gigomatic_username, 'johndoe')
        self.assertFalse(member.is_active)
        
        self.assertEqual(mock_api.call_count, 2)
        verify_call = mock_api.call_args_list[0]
        self.assertIn('/members/query?email=john%40example.com', verify_call[0][0])
        toggle_call = mock_api.call_args_list[1]
        self.assertIn('/bands/1/members/999/occasional', toggle_call[0][0])
        self.assertEqual(toggle_call[1]['method'], 'PATCH')

    @override_settings(DEBUG=False, GIGO_BAND_ID='1', GIGO_API_URL='http://test', GIGO_API_KEY='test-key')
    @patch('blowcomotion.utils.make_gigo_api_request')
    def test_save_activating_member_updates_id_and_syncs_to_regular(self, mock_api):
        """Test that activating updates member ID/username and marks them as regular in GO3"""
        member = Member.objects.create(
            first_name='Jane',
            last_name='Smith',
            email='jane@example.com',
            primary_instrument=self.trumpet,
            gigomatic_id=456,
            gigomatic_username='old_username',
            is_active=False
        )
        
        # Reset mock to ignore the creation save() call
        mock_api.reset_mock()
        
        mock_api.side_effect = [
            {'member_id': 789, 'email': 'jane@example.com', 'username': 'janesmith'},
            {'is_occasional': False, 'member_id': 789, 'band_id': 1}
        ]
        
        member.is_active = True
        member.save()
        
        member.refresh_from_db()
        self.assertEqual(member.gigomatic_id, 789)
        self.assertEqual(member.gigomatic_username, 'janesmith')
        self.assertTrue(member.is_active)
        
        self.assertEqual(mock_api.call_count, 2)
        toggle_call = mock_api.call_args_list[1]
        self.assertIn('/bands/1/members/789/occasional', toggle_call[0][0])
        self.assertEqual(toggle_call[1]['method'], 'PATCH')

    @override_settings(DEBUG=False, GIGO_BAND_ID='1', GIGO_API_URL='http://test', GIGO_API_KEY='test-key')
    @patch('blowcomotion.utils.make_gigo_api_request')
    def test_save_toggle_verification_retries_on_wrong_state(self, mock_api):
        """Test that save toggles again if first toggle returns wrong state"""
        member = Member.objects.create(
            first_name='Bob',
            last_name='Jones',
            email='bob@example.com',
            primary_instrument=self.trumpet,
            gigomatic_id=789,
            gigomatic_username='bobjones',
            is_active=True
        )
        
        # Reset mock to ignore the creation save() call
        mock_api.reset_mock()
        
        mock_api.side_effect = [
            {'member_id': 789, 'email': 'bob@example.com', 'username': 'bobjones'},
            {'is_occasional': False, 'member_id': 789, 'band_id': 1},
            {'is_occasional': True, 'member_id': 789, 'band_id': 1}
        ]
        
        member.is_active = False
        member.save()
        
        self.assertEqual(mock_api.call_count, 3)

    @override_settings(DEBUG=False, GIGO_BAND_ID='1', GIGO_API_URL='http://test', GIGO_API_KEY='test-key')
    @patch('blowcomotion.utils.make_gigo_api_request')
    def test_save_without_is_active_change_doesnt_toggle_status(self, mock_api):
        """Test that save doesn't call GO3 API when ID/username already set and nothing important changed"""
        member = Member.objects.create(
            first_name='David',
            last_name='Lee',
            email='david@example.com',
            primary_instrument=self.trumpet,
            gigomatic_id=222,
            gigomatic_username='davidlee',
            is_active=True
        )
        
        # Reset mock to ignore the creation save() call
        mock_api.reset_mock()
        
        # Change a field that doesn't require GO3 sync
        member.first_name = 'Dave'
        member.save()
        
        # Should NOT call GO3 API since gigomatic_id/username are set and is_active/email didn't change
        self.assertEqual(mock_api.call_count, 0)

    @override_settings(DEBUG=False, GIGO_BAND_ID='1', GIGO_API_URL='http://test', GIGO_API_KEY='test-key')
    @patch('blowcomotion.utils.make_gigo_api_request')
    def test_save_syncs_id_and_username_when_missing(self, mock_api):
        """Test that save syncs ID and username from GO3 when they're missing"""
        # Create member instance without saving
        member = Member(
            first_name='Emily',
            last_name='Chen',
            email='emily@example.com',
            primary_instrument=self.trumpet,
            gigomatic_id=None,  # Missing ID
            gigomatic_username=None,  # Missing username
            is_active=True
        )
        # Save with sync_go3=False to skip GO3 sync during creation
        member.save(sync_go3=False)
        
        # Reset mock to clear any potential calls
        mock_api.reset_mock()
        
        # Set mock response for the test save
        mock_api.return_value = {
            'member_id': 999,
            'email': 'emily@example.com',
            'username': 'emily_chen'
        }
        
        # Change something to trigger a save
        member.first_name = 'Em'
        member.save()
        
        # Verify ID and username were fetched and updated
        member.refresh_from_db()
        self.assertEqual(member.gigomatic_id, 999)
        self.assertEqual(member.gigomatic_username, 'emily_chen')
        
        # Should call member query API since ID/username were missing
        self.assertEqual(mock_api.call_count, 1)
        call_args = mock_api.call_args_list[0]
        self.assertIn('/members/query?email=emily%40example.com', call_args[0][0])

    @override_settings(DEBUG=False, GIGO_BAND_ID='1', GIGO_API_URL='http://test', GIGO_API_KEY='test-key')
    @patch('blowcomotion.utils.make_gigo_api_request')
    def test_save_handles_api_errors_gracefully(self, mock_api):
        """Test that save doesn't fail when GO3 API errors occur"""
        member = Member.objects.create(
            first_name='Alice',
            last_name='Brown',
            email='alice@example.com',
            primary_instrument=self.trumpet,
            gigomatic_id=111,
            is_active=True
        )
        
        # Reset mock to ignore the creation save() call
        mock_api.reset_mock()
        
        mock_api.side_effect = Exception('Connection timeout')
        
        member.is_active = False
        member.save()
        
        member.refresh_from_db()
        self.assertFalse(member.is_active)

    @override_settings(DEBUG=False, GIGO_BAND_ID='1', GIGO_API_URL='http://test', GIGO_API_KEY='test-key')
    @patch('blowcomotion.utils.make_gigo_api_request')
    def test_save_syncs_when_email_changes(self, mock_api):
        """Test that save syncs with GO3 when email changes"""
        member = Member.objects.create(
            first_name='Frank',
            last_name='Miller',
            email='frank@example.com',
            primary_instrument=self.trumpet,
            gigomatic_id=555,
            gigomatic_username='frank',
            is_active=True
        )
        
        # Reset mock to ignore the creation save() call
        mock_api.reset_mock()
        
        # Mock member query response
        mock_api.return_value = {
            'member_id': 666,
            'email': 'frank.miller@example.com',
            'username': 'frank_m'
        }
        
        # Change email
        member.email = 'frank.miller@example.com'
        member.save()
        
        # Should call GO3 API because email changed
        self.assertEqual(mock_api.call_count, 1)
        call_args = mock_api.call_args_list[0]
        self.assertIn('/members/query?email=frank.miller%40example.com', call_args[0][0])

    @override_settings(DEBUG=False, GIGO_BAND_ID='1', GIGO_API_URL='http://test', GIGO_API_KEY='test-key')
    @patch('blowcomotion.utils.make_gigo_api_request')
    def test_save_respects_sync_go3_false(self, mock_api):
        """Test that save doesn't sync with GO3 when sync_go3=False"""
        # Create member instance without saving
        member = Member(
            first_name='Grace',
            last_name='Wilson',
            email='grace@example.com',
            primary_instrument=self.trumpet,
            is_active=True
        )
        # Save with sync_go3=False to skip GO3 sync during creation
        member.save(sync_go3=False)
        
        # Reset mock to clear any potential calls
        mock_api.reset_mock()
        
        # Change is_active (which normally triggers sync)
        member.is_active = False
        member.save(sync_go3=False)
        
        # Should NOT call GO3 API because sync_go3=False
        self.assertEqual(mock_api.call_count, 0)

    @override_settings(DEBUG=False, GIGO_BAND_ID='1', GIGO_API_URL='http://test', GIGO_API_KEY='test-key')
    @patch('blowcomotion.utils.make_gigo_api_request')
    def test_save_ignores_mutated_fields_not_in_update_fields(self, mock_api):
        """Test that save doesn't sync when field is mutated but excluded from update_fields"""
        member = Member.objects.create(
            first_name='Henry',
            last_name='Taylor',
            email='henry@example.com',
            primary_instrument=self.trumpet,
            gigomatic_id=777,
            gigomatic_username='henry_t',
            is_active=True
        )
        
        # Reset mock to ignore the creation save() call
        mock_api.reset_mock()
        
        # Mutate is_active in memory but don't include it in update_fields
        member.is_active = False
        member.save(update_fields=['first_name'])
        
        # Should NOT call GO3 API because is_active wasn't in update_fields
        self.assertEqual(mock_api.call_count, 0)
        
        # Verify database still has old value
        member.refresh_from_db()
        self.assertTrue(member.is_active)
        
    @override_settings(DEBUG=False, GIGO_BAND_ID='1', GIGO_API_URL='http://test', GIGO_API_KEY='test-key')
    @patch('blowcomotion.utils.make_gigo_api_request')
    def test_save_syncs_when_field_in_update_fields(self, mock_api):
        """Test that save DOES sync when field is mutated and included in update_fields"""
        member = Member.objects.create(
            first_name='Iris',
            last_name='White',
            email='iris@example.com',
            primary_instrument=self.trumpet,
            gigomatic_id=888,
            gigomatic_username='iris_w',
            is_active=True
        )
        
        # Reset mock to ignore the creation save() call
        mock_api.reset_mock()
        
        mock_api.side_effect = [
            {'member_id': 888, 'email': 'iris@example.com', 'username': 'iris_w'},
            {'is_occasional': True, 'member_id': 888, 'band_id': 1}
        ]
        
        # Mutate is_active and include it in update_fields
        member.is_active = False
        member.save(update_fields=['is_active'])
        
        # Should call GO3 API because is_active was in update_fields
        self.assertEqual(mock_api.call_count, 2)
        
        # Verify database has new value
        member.refresh_from_db()
        self.assertFalse(member.is_active)
