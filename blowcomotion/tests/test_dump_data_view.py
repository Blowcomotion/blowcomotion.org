"""
Unit tests for admin dump_data view.
"""

import json

from django.contrib.auth.models import Permission, User
from django.test import Client, TestCase
from django.urls import reverse

from blowcomotion.models import Instrument, Member, Section


class DumpDataViewTests(TestCase):
    """Test cases for dump_data admin view with member data scrubbing"""

    def setUp(self):
        """Set up test data"""
        self.client = Client()
        
        # Create superuser for authentication
        self.superuser = User.objects.create_superuser(
            username='admin',
            email='admin@example.com',
            password='testpass123'
        )
        
        # Create test section and instrument for FK relationships
        self.section = Section.objects.create(name="Test Section")
        self.instrument = Instrument.objects.create(
            name="Test Instrument",
            section=self.section
        )
        
        # Create test members with various fields
        self.member1 = Member.objects.create(
            first_name="John",
            last_name="Doe",
            preferred_name="Johnny",
            email="john.doe@example.com",
            phone="555-1234",
            address="123 Real St",
            city="Austin",
            state="TX",
            zip_code="78701",
            country="USA",
            primary_instrument=self.instrument,
            birth_month=5,
            birth_day=15,
            birth_year=1990,
            bio="Real bio text",
            notes="Real notes text",
            inspired_by="Real inspiration",
            emergency_contact="Jane Doe 555-5678",
            is_active=True,
            instructor=False,
            board_member=True,
            renting=False
        )
        
        self.member2 = Member.objects.create(
            first_name="Jane",
            last_name="Smith",
            email="jane.smith@example.com",
            primary_instrument=self.instrument,
            is_active=False
        )

    def test_requires_permission(self):
        """Test that dump_data requires access_dev_tools or access_real_data_exports"""
        response = self.client.get(reverse('dump_data'))
        self.assertIn(response.status_code, [302, 403])  # Redirect to login or forbidden

        User.objects.create_user(
            username='regular',
            password='testpass123',
            is_staff=True,
        )
        self.client.login(username='regular', password='testpass123')
        response = self.client.get(reverse('dump_data'))
        self.assertIn(response.status_code, [302, 403])

        self.client.login(username='admin', password='testpass123')
        response = self.client.get(reverse('dump_data'))
        self.assertEqual(response.status_code, 200)

    def test_dev_can_access_scrubbed_dump_only(self):
        """Test that access_dev_tools grants scrubbed dump but not include_real_data"""
        dev_perm = Permission.objects.get(codename='access_dev_tools')
        dev_user = User.objects.create_user(
            username='dev',
            password='testpass123',
            is_staff=True,
            is_active=True
        )
        dev_user.user_permissions.add(dev_perm)

        # Add Wagtail admin access permission
        try:
            admin_permission = Permission.objects.get(
                content_type__app_label='wagtailadmin',
                codename='access_admin'
            )
            dev_user.user_permissions.add(admin_permission)
        except Permission.DoesNotExist:
            pass  # Permission might not exist in test DB

        self.client.login(username='dev', password='testpass123')

        response = self.client.get(reverse('dump_data'))
        self.assertEqual(response.status_code, 200)

        response = self.client.get(reverse('dump_data') + '?include_real_data=true')
        self.assertEqual(response.status_code, 403)

    def test_data_analyst_can_access_real_dump(self):
        """Test that access_real_data_exports grants include_real_data"""
        analyst_perm = Permission.objects.get(codename='access_real_data_exports')
        analyst_user = User.objects.create_user(
            username='analyst',
            password='testpass123',
            is_staff=True,
            is_active=True
        )
        analyst_user.user_permissions.add(analyst_perm)

        # Add Wagtail admin access permission
        try:
            admin_permission = Permission.objects.get(
                content_type__app_label='wagtailadmin',
                codename='access_admin'
            )
            analyst_user.user_permissions.add(admin_permission)
        except Permission.DoesNotExist:
            pass  # Permission might not exist in test DB

        self.client.login(username='analyst', password='testpass123')

        response = self.client.get(reverse('dump_data') + '?include_real_data=true')
        self.assertEqual(response.status_code, 200)

    def test_default_scrubs_member_data(self):
        """Test that member data is scrubbed by default for users without analyst access"""
        User.objects.create_user(
            username='dev_no_analyst',
            password='testpass123',
            is_staff=True,
        )
        dev_perm = Permission.objects.get(codename='access_dev_tools')
        dev_user = User.objects.get(username='dev_no_analyst')
        dev_user.user_permissions.add(dev_perm)
        try:
            admin_permission = Permission.objects.get(
                content_type__app_label='wagtailadmin',
                codename='access_admin'
            )
            dev_user.user_permissions.add(admin_permission)
        except Permission.DoesNotExist:
            pass  # Permission might not exist in test DB
        self.client.login(username='dev_no_analyst', password='testpass123')
        response = self.client.get(reverse('dump_data'))
        
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'application/json')
        
        data = json.loads(response.content)
        
        # Find member records in the dump
        member_records = [item for item in data if item.get('model') == 'blowcomotion.member']
        self.assertEqual(len(member_records), 2, "Should have 2 scrubbed member records")
        
        # Check that member1's data is scrubbed
        member1_record = next((r for r in member_records if r['pk'] == self.member1.pk), None)
        self.assertIsNotNone(member1_record)
        fields = member1_record['fields']
        
        # Verify scrubbed fields (first_name / last_name / email live on
        # auth.user, which is excluded from the dump entirely)
        self.assertNotIn('first_name', fields)
        self.assertNotIn('last_name', fields)
        self.assertNotIn('email', fields)
        self.assertEqual(fields['preferred_name'], 'Preferred1')
        self.assertEqual(fields['phone'], '555-0001')
        self.assertEqual(fields['address'], '1 Main Street')
        self.assertEqual(fields['city'], 'Austin')
        self.assertEqual(fields['state'], 'TX')
        self.assertEqual(fields['zip_code'], '00001')
        self.assertEqual(fields['country'], 'USA')
        self.assertEqual(fields['bio'], 'Scrubbed for privacy')
        self.assertEqual(fields['notes'], 'Scrubbed for privacy')
        self.assertEqual(fields['inspired_by'], 'Scrubbed for privacy')
        self.assertEqual(fields['emergency_contact'], 'Emergency Contact 1')
        
        # Verify preserved fields
        self.assertEqual(fields['primary_instrument'], self.instrument.pk)
        self.assertEqual(fields['birth_month'], 5)
        self.assertEqual(fields['birth_day'], 15)
        self.assertEqual(fields['birth_year'], 1990)
        self.assertTrue(fields['is_active'])
        self.assertFalse(fields['instructor'])
        self.assertTrue(fields['board_member'])
        self.assertFalse(fields['renting'])

    def test_include_real_data_parameter(self):
        """Test that ?include_real_data=true returns actual member data"""
        self.client.login(username='admin', password='testpass123')
        response = self.client.get(reverse('dump_data') + '?include_real_data=true')
        
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        
        # Find member records in the dump
        member_records = [item for item in data if item.get('model') == 'blowcomotion.member']
        self.assertEqual(len(member_records), 2, "Should have 2 real member records")
        
        # Check that member1's real data is included
        member1_record = next((r for r in member_records if r['pk'] == self.member1.pk), None)
        self.assertIsNotNone(member1_record)
        fields = member1_record['fields']
        
        # Verify real data is present (name/email live on auth.user, which
        # is excluded from the dump)
        self.assertEqual(fields['preferred_name'], 'Johnny')
        self.assertEqual(fields['phone'], '555-1234')
        self.assertEqual(fields['address'], '123 Real St')
        self.assertEqual(fields['city'], 'Austin')
        self.assertEqual(fields['state'], 'TX')
        self.assertEqual(fields['bio'], 'Real bio text')
        self.assertEqual(fields['notes'], 'Real notes text')

        # Users and site settings should never be exported (even when including real member data)
        dumped_models = {item.get('model') for item in data}
        self.assertNotIn('auth.user', dumped_models)
        self.assertNotIn('blowcomotion.sitesettings', dumped_models)

    def test_fake_members_after_dependencies(self):
        """Test that dumpdata orders member records after instrument records (FK dependency ordering)"""
        self.client.login(username='admin', password='testpass123')
        response = self.client.get(reverse('dump_data'))
        
        data = json.loads(response.content)
        
        # Find indices
        instrument_indices = [i for i, item in enumerate(data) if item.get('model') == 'blowcomotion.instrument']
        member_indices = [i for i, item in enumerate(data) if item.get('model') == 'blowcomotion.member']
        
        if instrument_indices and member_indices:
            # Members should come after instruments
            last_instrument_index = max(instrument_indices)
            first_member_index = min(member_indices)
            self.assertGreater(
                first_member_index, 
                last_instrument_index,
                "Member records should be serialized after instruments to satisfy FK constraints"
            )

    def test_deterministic_ordering(self):
        """Test that member ordering is deterministic across multiple dumps"""
        self.client.login(username='admin', password='testpass123')
        
        # Get two dumps
        response1 = self.client.get(reverse('dump_data'))
        response2 = self.client.get(reverse('dump_data'))
        
        data1 = json.loads(response1.content)
        data2 = json.loads(response2.content)
        
        # Extract member records
        members1 = [item for item in data1 if item.get('model') == 'blowcomotion.member']
        members2 = [item for item in data2 if item.get('model') == 'blowcomotion.member']
        
        # PKs should be in the same order
        pks1 = [m['pk'] for m in members1]
        pks2 = [m['pk'] for m in members2]
        self.assertEqual(pks1, pks2, "Member PKs should be in consistent order")
        
        # Scrubbed values should be consistent
        names1 = [m['fields']['preferred_name'] for m in members1]
        names2 = [m['fields']['preferred_name'] for m in members2]
        self.assertEqual(names1, names2, "Scrubbed member fields should be deterministic")

    def test_preserves_expected_member_fields(self):
        """Test that the expected member fields are included in scrubbed output"""
        self.client.login(username='admin', password='testpass123')
        response = self.client.get(reverse('dump_data'))
        
        data = json.loads(response.content)
        member_records = [item for item in data if item.get('model') == 'blowcomotion.member']
        
        if member_records:
            fields = member_records[0]['fields']
            
            # Check all expected fields are present
            expected_fields = [
                'preferred_name', 'primary_instrument',
                'birth_month', 'birth_day', 'birth_year', 'phone',
                'address', 'city', 'state', 'zip_code', 'country',
                'emergency_contact', 'inspired_by', 'is_active', 'instructor',
                'board_member', 'join_date', 'last_seen', 'separation_date',
                'reactivated_date', 'bio', 'notes', 'renting'
            ]
            
            for field_name in expected_fields:
                self.assertIn(
                    field_name, 
                    fields, 
                    f"Field '{field_name}' should be included in scrubbed member data"
                )

    def test_user_fks_are_cleared(self):
        """Test that user FK fields are nulled to prevent dangling references"""
        self.client.login(username='admin', password='testpass123')
        response = self.client.get(reverse('dump_data'))
        
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        
        # Check that any user FK fields in the dump are nulled
        user_fk_field_names = {'uploaded_by_user', 'user', 'locked_by', 'owner'}
        for item in data:
            fields = item.get('fields', {})
            for field_name in user_fk_field_names:
                if field_name in fields:
                    self.assertIsNone(
                        fields[field_name],
                        f"User FK field '{field_name}' in {item.get('model')} should be null"
                    )
