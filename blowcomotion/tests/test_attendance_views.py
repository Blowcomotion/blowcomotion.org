"""
Unit tests for attendance tracking views.
"""

import base64
from datetime import date, timedelta
from unittest.mock import patch

from wagtail.models import Site

from django.contrib.auth.models import User
from django.http import Http404
from django.test import Client, TestCase, override_settings
from django.urls import reverse

from blowcomotion.models import (
    AttendanceRecord,
    Instrument,
    Member,
    MemberInstrument,
    Section,
    SiteSettings,
)


class AttendanceAuthenticationTests(TestCase):
    """Test cases for SiteSettings-based authentication"""

    def setUp(self):
        """Set up test data"""
        self.client = Client()
        self.site = Site.objects.get(is_default_site=True)
        
        # Create test section for basic functionality
        self.section = Section.objects.create(name="Test Section")

    def test_no_auth_when_no_password_set(self):
        """Test that authentication is skipped when no password is set in SiteSettings"""
        # Create SiteSettings with no password
        SiteSettings.objects.create(
            site=self.site,
            attendance_password=None
        )
        
        # Should be able to access without authentication
        response = self.client.get(reverse('attendance-capture', args=['test-section']))
        self.assertEqual(response.status_code, 200)

    def test_no_auth_when_empty_password_set(self):
        """Test that authentication is skipped when empty password is set in SiteSettings"""
        # Create SiteSettings with empty password
        SiteSettings.objects.create(
            site=self.site,
            attendance_password=''
        )
        
        # Should be able to access without authentication
        response = self.client.get(reverse('attendance-capture', args=['test-section']))
        self.assertEqual(response.status_code, 200)

    def test_auth_required_when_password_set(self):
        """Test that authentication is required when password is set in SiteSettings"""
        # Create SiteSettings with password
        SiteSettings.objects.create(
            site=self.site,
            attendance_password='testpassword'
        )
        
        # Should require authentication
        response = self.client.get(reverse('attendance-capture', args=['test-section']))
        self.assertEqual(response.status_code, 401)
        self.assertIn('WWW-Authenticate', response)

    def test_correct_password_allows_access(self):
        """Test that correct password allows access"""
        # Create SiteSettings with password
        SiteSettings.objects.create(
            site=self.site,
            attendance_password='testpassword'
        )
        
        # Set up correct credentials
        credentials = base64.b64encode(b'testuser:testpassword').decode('ascii')
        self.client.defaults['HTTP_AUTHORIZATION'] = f'Basic {credentials}'
        
        # Should allow access
        response = self.client.get(reverse('attendance-capture', args=['test-section']))
        self.assertEqual(response.status_code, 200)

    def test_wrong_password_denies_access(self):
        """Test that wrong password denies access"""
        # Create SiteSettings with password
        SiteSettings.objects.create(
            site=self.site,
            attendance_password='testpassword'
        )
        
        # Set up wrong credentials
        credentials = base64.b64encode(b'testuser:wrongpassword').decode('ascii')
        self.client.defaults['HTTP_AUTHORIZATION'] = f'Basic {credentials}'
        
        # Should deny access
        response = self.client.get(reverse('attendance-capture', args=['test-section']))
        self.assertEqual(response.status_code, 401)


class AttendanceCaptureViewTests(TestCase):
    """Test cases for the attendance_capture view"""

    def setUp(self):
        """Set up test data"""
        self.client = Client()
        
        # Set up SiteSettings with test password
        self.site = Site.objects.get(is_default_site=True)
        self.site_settings = SiteSettings.objects.create(
            site=self.site,
            attendance_password='testpassword'
        )
        
        # Set up HTTP Basic Auth credentials
        credentials = base64.b64encode(b'testuser:testpassword').decode('ascii')
        self.client.defaults['HTTP_AUTHORIZATION'] = f'Basic {credentials}'
        
        # Create test sections
        self.high_brass = Section.objects.create(name="High Brass")
        self.low_brass = Section.objects.create(name="Low Brass")
        
        # Create test instruments
        self.trumpet = Instrument.objects.create(name="Trumpet", section=self.high_brass)
        self.trombone = Instrument.objects.create(name="Trombone", section=self.low_brass)
        
        # Create test members
        self.member1 = Member.objects.create(
            first_name="John",
            last_name="Doe",
            email="john.doe@example.com",
            is_active=True,
            join_date=date.today() - timedelta(days=30)
        )
        self.member2 = Member.objects.create(
            first_name="Jane",
            last_name="Smith", 
            email="jane.smith@example.com",
            is_active=True,
            join_date=date.today() - timedelta(days=60)
        )
        self.inactive_member = Member.objects.create(
            first_name="Bob",
            last_name="Wilson",
            email="bob.wilson@example.com", 
            is_active=False
        )
        
        # Assign instruments to members
        MemberInstrument.objects.create(member=self.member1, instrument=self.trumpet)
        MemberInstrument.objects.create(member=self.member2, instrument=self.trombone)
        MemberInstrument.objects.create(member=self.inactive_member, instrument=self.trumpet)
        self.member1.primary_instrument = self.trumpet
        self.member1.save(update_fields=['primary_instrument'])
        self.member2.primary_instrument = self.trombone
        self.member2.save(update_fields=['primary_instrument'])
        self.inactive_member.primary_instrument = self.trumpet
        self.inactive_member.save(update_fields=['primary_instrument'])
        
        # Create a member without any instrument assignment for no-section testing
        self.no_section_member = Member.objects.create(
            first_name="No",
            last_name="Section",
            email="no.section@example.com",
            is_active=True
        )

    def test_attendance_capture_get_no_section(self):
        """Test GET request to main attendance page without section"""
        response = self.client.get(reverse('attendance-main'))
        
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Attendance Tracking")
        self.assertContains(response, "High Brass")
        self.assertContains(response, "Low Brass")
        self.assertIsNone(response.context['section'])
        self.assertEqual(list(response.context['sections']), [self.high_brass, self.low_brass])
        self.assertEqual(list(response.context['section_members']), [])

    def test_attendance_capture_get_with_section(self):
        """Test GET request to attendance page with specific section"""
        response = self.client.get(reverse('attendance-capture', args=['high-brass']))
        
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['section'], self.high_brass)
        # Only active members should be included
        section_members = list(response.context['section_members'])
        self.assertIn(self.member1, section_members)
        self.assertNotIn(self.inactive_member, section_members)
        
        # Check that event type and event notes fields are present in the template
        self.assertContains(response, 'name="event_type"')
        self.assertContains(response, 'name="event_notes"')
        self.assertContains(response, 'value="rehearsal"')
        self.assertContains(response, 'value="performance_no_gig"')
        self.assertContains(response, 'Event Type')
        self.assertContains(response, 'Event Notes')

    def test_attendance_capture_get_with_invalid_section(self):
        """Test GET request with non-existent section should return 404"""
        response = self.client.get(reverse('attendance-capture', args=['non-existent']))
        self.assertEqual(response.status_code, 404)

    def test_attendance_capture_htmx_request(self):
        """Test HTMX request returns partial template"""
        response = self.client.get(
            reverse('attendance-capture', args=['high-brass']),
            HTTP_HX_REQUEST='true'
        )
        
        self.assertEqual(response.status_code, 200)
        # Should return partial template for HTMX
        self.assertContains(response, "Attendance Tracking")

    def test_attendance_capture_post_member_attendance(self):
        """Test POST request to record member attendance"""
        attendance_date = date.today()
        
        response = self.client.post(
            reverse('attendance-capture', args=['high-brass']),
            {
                'attendance_date': attendance_date.strftime('%Y-%m-%d'),
                f'member_{self.member1.id}': 'on',
            }
        )
        
        self.assertEqual(response.status_code, 200)
        
        # Check attendance record was created
        attendance_record = AttendanceRecord.objects.get(
            date=attendance_date,
            member=self.member1
        )
        self.assertIsNotNone(attendance_record)
        self.assertEqual(attendance_record.played_instrument, self.trumpet)
        
        # Check member's last_seen was updated
        self.member1.refresh_from_db()
        self.assertEqual(self.member1.last_seen, attendance_date)
        
        # Check response contains success message
        self.assertContains(response, "Successfully recorded attendance")

    def test_attendance_capture_records_additional_instrument_members(self):
        """Members with additional instruments should appear in that section and record the selected instrument."""
        woodwinds = Section.objects.create(name="Woodwinds")
        flute = Instrument.objects.create(name="Flute", section=woodwinds)

        MemberInstrument.objects.create(member=self.member1, instrument=flute)

        response = self.client.get(reverse('attendance-capture', args=['woodwinds']))
        self.assertEqual(response.status_code, 200)
        section_members = list(response.context['section_members'])
        self.assertIn(self.member1, section_members)

        entry = response.context['member_entries_map'][self.member1.id]
        self.assertEqual(entry['display_instrument'], flute)

        attendance_date = date.today()
        post_response = self.client.post(
            reverse('attendance-capture', args=['woodwinds']),
            {
                'attendance_date': attendance_date.strftime('%Y-%m-%d'),
                f'member_{self.member1.id}': 'on',
            }
        )

        self.assertEqual(post_response.status_code, 200)
        record = AttendanceRecord.objects.get(date=attendance_date, member=self.member1)
        self.assertEqual(record.played_instrument, flute)

    def test_attendance_capture_post_member_attendance_rehearsal(self):
        """Test POST request to record member attendance for rehearsal (default event type)"""
        attendance_date = date.today()
        
        response = self.client.post(
            reverse('attendance-capture', args=['high-brass']),
            {
                'attendance_date': attendance_date.strftime('%Y-%m-%d'),
                'event_type': 'rehearsal',
                f'member_{self.member1.id}': 'on',
            }
        )
        
        self.assertEqual(response.status_code, 200)
        
        # Check attendance record was created with correct notes
        attendance_record = AttendanceRecord.objects.get(
            date=attendance_date,
            member=self.member1
        )
        self.assertEqual(attendance_record.notes, 'Rehearsal')
        self.assertEqual(attendance_record.played_instrument, self.trumpet)

    def test_attendance_capture_post_member_attendance_rehearsal_with_notes(self):
        """Test POST request to record member attendance for rehearsal with custom notes"""
        attendance_date = date.today()
        custom_notes = "Working on new arrangements"
        
        response = self.client.post(
            reverse('attendance-capture', args=['high-brass']),
            {
                'attendance_date': attendance_date.strftime('%Y-%m-%d'),
                'event_type': 'rehearsal',
                'event_notes': custom_notes,
                f'member_{self.member1.id}': 'on',
            }
        )
        
        self.assertEqual(response.status_code, 200)
        
        # Check attendance record was created with correct notes
        attendance_record = AttendanceRecord.objects.get(
            date=attendance_date,
            member=self.member1
        )
        self.assertEqual(attendance_record.notes, f'Rehearsal: {custom_notes}')
        self.assertEqual(attendance_record.played_instrument, self.trumpet)

    def test_attendance_capture_post_member_attendance_performance_no_name(self):
        """Test POST request to record member attendance for performance without event name"""
        attendance_date = date.today()
        
        response = self.client.post(
            reverse('attendance-capture', args=['high-brass']),
            {
                'attendance_date': attendance_date.strftime('%Y-%m-%d'),
                'event_type': 'performance_no_gig',
                f'member_{self.member1.id}': 'on',
            }
        )
        
        self.assertEqual(response.status_code, 200)
        
        # Check attendance record was created with correct notes
        attendance_record = AttendanceRecord.objects.get(
            date=attendance_date,
            member=self.member1
        )
        self.assertEqual(attendance_record.notes, 'Performance')
        self.assertEqual(attendance_record.played_instrument, self.trumpet)

    def test_attendance_capture_post_member_attendance_performance_with_notes(self):
        """Test POST request to record member attendance for performance with custom notes"""
        attendance_date = date.today()
        custom_notes = "Summer Concert"
        
        response = self.client.post(
            reverse('attendance-capture', args=['high-brass']),
            {
                'attendance_date': attendance_date.strftime('%Y-%m-%d'),
                'event_type': 'performance_no_gig',
                'event_notes': custom_notes,
                f'member_{self.member1.id}': 'on',
            }
        )
        
        self.assertEqual(response.status_code, 200)
        
        # Check attendance record was created with correct notes
        attendance_record = AttendanceRecord.objects.get(
            date=attendance_date,
            member=self.member1
        )
        self.assertEqual(attendance_record.notes, f'Performance: {custom_notes}')
        self.assertEqual(attendance_record.played_instrument, self.trumpet)

    def test_attendance_capture_post_guest_attendance_rehearsal(self):
        """Test POST request to record guest attendance for rehearsal"""
        attendance_date = date.today()
        guest_names = "Guest One\nGuest Two"
        
        response = self.client.post(
            reverse('attendance-capture', args=['high-brass']),
            {
                'attendance_date': attendance_date.strftime('%Y-%m-%d'),
                'event_type': 'rehearsal',
                f'guest_{self.high_brass.id}': guest_names,
            }
        )
        
        self.assertEqual(response.status_code, 200)
        
        # Check guest attendance records were created with correct notes
        guest_records = AttendanceRecord.objects.filter(
            date=attendance_date,
            guest_name__isnull=False
        )
        self.assertEqual(guest_records.count(), 2)
        
        for record in guest_records:
            self.assertEqual(record.notes, 'Guest - Rehearsal')

    def test_attendance_capture_post_guest_attendance_rehearsal_with_notes(self):
        """Test POST request to record guest attendance for rehearsal with custom notes"""
        attendance_date = date.today()
        guest_names = "Guest One\nGuest Two"
        custom_notes = "Section rehearsal"
        
        response = self.client.post(
            reverse('attendance-capture', args=['high-brass']),
            {
                'attendance_date': attendance_date.strftime('%Y-%m-%d'),
                'event_type': 'rehearsal',
                'event_notes': custom_notes,
                f'guest_{self.high_brass.id}': guest_names,
            }
        )
        
        self.assertEqual(response.status_code, 200)
        
        # Check guest attendance records were created with correct notes
        guest_records = AttendanceRecord.objects.filter(
            date=attendance_date,
            guest_name__isnull=False
        )
        self.assertEqual(guest_records.count(), 2)
        
        for record in guest_records:
            self.assertEqual(record.notes, f'Guest - Rehearsal: {custom_notes}')

    def test_attendance_capture_post_guest_attendance_performance_with_notes(self):
        """Test POST request to record guest attendance for performance with custom notes"""
        attendance_date = date.today()
        guest_names = "Guest Musician"
        custom_notes = "Holiday Show"
        
        response = self.client.post(
            reverse('attendance-capture', args=['high-brass']),
            {
                'attendance_date': attendance_date.strftime('%Y-%m-%d'),
                'event_type': 'performance_no_gig',
                'event_notes': custom_notes,
                f'guest_{self.high_brass.id}': guest_names,
            }
        )
        
        self.assertEqual(response.status_code, 200)
        
        # Check guest attendance record was created with correct notes
        guest_record = AttendanceRecord.objects.get(
            date=attendance_date,
            guest_name="Guest Musician"
        )
        self.assertEqual(guest_record.notes, f'Guest - Performance: {custom_notes}')

    def test_attendance_capture_post_mixed_attendance_with_event_info(self):
        """Test POST request with both member and guest attendance for a named performance"""
        attendance_date = date.today()
        custom_notes = "Spring Festival"
        guest_names = "Special Guest"
        
        # Create a second member in the same section for this test
        member2_high_brass = Member.objects.create(
            first_name="Second",
            last_name="Member",
            email="second@example.com",
            is_active=True,
            join_date=date.today() - timedelta(days=30)
        )
        MemberInstrument.objects.create(member=member2_high_brass, instrument=self.trumpet)
        
        response = self.client.post(
            reverse('attendance-capture', args=['high-brass']),
            {
                'attendance_date': attendance_date.strftime('%Y-%m-%d'),
                'event_type': 'performance_no_gig',
                'event_notes': custom_notes,
                f'member_{self.member1.id}': 'on',
                f'member_{member2_high_brass.id}': 'on',
                f'guest_{self.high_brass.id}': guest_names,
            }
        )
        
        self.assertEqual(response.status_code, 200)
        
        # Check member attendance records
        member_records = AttendanceRecord.objects.filter(
            date=attendance_date,
            member__isnull=False
        )
        self.assertEqual(member_records.count(), 2)
        for record in member_records:
            self.assertEqual(record.notes, f'Performance: {custom_notes}')
        
        # Check guest attendance record
        guest_record = AttendanceRecord.objects.get(
            date=attendance_date,
            guest_name="Special Guest"
        )
        self.assertEqual(guest_record.notes, f'Guest - Performance: {custom_notes}')

    def test_attendance_capture_post_existing_notes_preservation(self):
        """Test that existing notes are preserved when updating attendance records"""
        attendance_date = date.today()
        existing_notes = "Already has some notes"
        
        # Create an existing attendance record with notes
        existing_record = AttendanceRecord.objects.create(
            date=attendance_date,
            member=self.member1,
            notes=existing_notes,
            played_instrument=self.trumpet
        )
        
        response = self.client.post(
            reverse('attendance-capture', args=['high-brass']),
            {
                'attendance_date': attendance_date.strftime('%Y-%m-%d'),
                'event_type': 'performance_no_gig',
                'event_notes': 'New Performance',
                f'member_{self.member1.id}': 'on',
            }
        )
        
        self.assertEqual(response.status_code, 200)
        
        # Check that existing notes are preserved and event info is appended
        existing_record.refresh_from_db()
        expected_notes = f"{existing_notes}; Performance: New Performance"
        self.assertEqual(existing_record.notes, expected_notes)
        self.assertEqual(existing_record.played_instrument, self.trumpet)

    def test_attendance_capture_post_default_event_type(self):
        """Test that attendance capture works without explicit event_type (defaults to rehearsal)"""
        attendance_date = date.today()
        
        response = self.client.post(
            reverse('attendance-capture', args=['high-brass']),
            {
                'attendance_date': attendance_date.strftime('%Y-%m-%d'),
                f'member_{self.member1.id}': 'on',
                # No event_type provided - should default to 'rehearsal'
            }
        )
        
        self.assertEqual(response.status_code, 200)
        
        # Check attendance record was created with default rehearsal notes
        attendance_record = AttendanceRecord.objects.get(
            date=attendance_date,
            member=self.member1
        )
        self.assertEqual(attendance_record.notes, 'Rehearsal')

    def test_attendance_capture_post_guest_attendance(self):
        """Test POST request to record guest attendance"""
        attendance_date = date.today()
        guest_names = "Guest One\nGuest Two\n\nGuest Three"
        
        response = self.client.post(
            reverse('attendance-capture', args=['high-brass']),
            {
                'attendance_date': attendance_date.strftime('%Y-%m-%d'),
                f'guest_{self.high_brass.id}': guest_names,
            }
        )
        
        self.assertEqual(response.status_code, 200)
        
        # Check guest attendance records were created
        guest_records = AttendanceRecord.objects.filter(
            date=attendance_date,
            guest_name__isnull=False
        )
        self.assertEqual(guest_records.count(), 3)
        
        guest_names_recorded = [record.guest_name for record in guest_records]
        self.assertIn("Guest One", guest_names_recorded)
        self.assertIn("Guest Two", guest_names_recorded)
        self.assertIn("Guest Three", guest_names_recorded)

    def test_attendance_capture_post_duplicate_member(self):
        """Test that duplicate member attendance on same date doesn't create multiple records"""
        attendance_date = date.today()
        
        # Create initial attendance record
        AttendanceRecord.objects.create(
            date=attendance_date,
            member=self.member1
        )
        
        response = self.client.post(
            reverse('attendance-capture', args=['high-brass']),
            {
                'attendance_date': attendance_date.strftime('%Y-%m-%d'),
                f'member_{self.member1.id}': 'on',
            }
        )
        
        self.assertEqual(response.status_code, 200)
        
        # Should still only have one record
        attendance_count = AttendanceRecord.objects.filter(
            date=attendance_date,
            member=self.member1
        ).count()
        self.assertEqual(attendance_count, 1)

    def test_attendance_capture_post_htmx_request(self):
        """Test POST HTMX request returns success partial"""
        attendance_date = date.today()
        
        response = self.client.post(
            reverse('attendance-capture', args=['high-brass']),
            {
                'attendance_date': attendance_date.strftime('%Y-%m-%d'),
                f'member_{self.member1.id}': 'on',
            },
            HTTP_HX_REQUEST='true'
        )
        
        self.assertEqual(response.status_code, 200)
        # Should contain success message elements
        self.assertContains(response, "Attendance Recorded Successfully!")

    def test_attendance_capture_post_no_section(self):
        """Test POST request without section (main attendance page)"""
        attendance_date = date.today()
        
        response = self.client.post(
            reverse('attendance-main'),
            {
                'attendance_date': attendance_date.strftime('%Y-%m-%d'),
            }
        )
        
        self.assertEqual(response.status_code, 200)

    @patch('blowcomotion.views.date')
    def test_attendance_capture_post_date_handling(self, mock_date):
        """Test proper date handling in POST requests"""
        # Mock today's date
        test_date = date(2024, 1, 15)
        mock_date.today.return_value = test_date
        
        response = self.client.post(
            reverse('attendance-capture', args=['high-brass']),
            {
                'attendance_date': '2024-01-10',
                f'member_{self.member1.id}': 'on',
            }
        )
        
        self.assertEqual(response.status_code, 200)
        
        # Check record was created with correct date
        attendance_record = AttendanceRecord.objects.get(member=self.member1)
        self.assertEqual(attendance_record.date, date(2024, 1, 10))

    def test_attendance_capture_get_no_section(self):
        """Test GET request to no-section attendance page"""
        response = self.client.get(reverse('attendance-capture', args=['no-section']))
        
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context['is_no_section'])
        self.assertIsNone(response.context['section'])
        self.assertContains(response, "Members Without Instruments")
        
        # Should include member without instrument assignment
        section_members = list(response.context['section_members'])
        self.assertIn(self.no_section_member, section_members)
        # Should not include members with instrument assignments
        self.assertNotIn(self.member1, section_members)
        self.assertNotIn(self.member2, section_members)

    def test_attendance_capture_post_no_section_member(self):
        """Test POST request to record attendance for no-section member"""
        attendance_date = date.today()
        
        response = self.client.post(
            reverse('attendance-capture', args=['no-section']),
            {
                'attendance_date': attendance_date.strftime('%Y-%m-%d'),
                f'member_{self.no_section_member.id}': 'on',
            }
        )
        
        self.assertEqual(response.status_code, 200)
        
        # Check attendance record was created
        attendance_record = AttendanceRecord.objects.get(
            date=attendance_date,
            member=self.no_section_member
        )
        self.assertIsNotNone(attendance_record)
        
        # Check member's last_seen was updated
        self.no_section_member.refresh_from_db()
        self.assertEqual(self.no_section_member.last_seen, attendance_date)

    def test_attendance_capture_post_no_section_guest(self):
        """Test POST request to record guest attendance for no-section"""
        attendance_date = date.today()
        guest_names = "No Section Guest\nAnother Guest"
        
        response = self.client.post(
            reverse('attendance-capture', args=['no-section']),
            {
                'attendance_date': attendance_date.strftime('%Y-%m-%d'),
                'guest_no_section': guest_names,
            }
        )
        
        self.assertEqual(response.status_code, 200)
        
        # Check guest attendance records were created
        guest_records = AttendanceRecord.objects.filter(
            date=attendance_date,
            guest_name__isnull=False
        )
        self.assertEqual(guest_records.count(), 2)
        
        guest_names_recorded = [record.guest_name for record in guest_records]
        self.assertIn("No Section Guest", guest_names_recorded)
        self.assertIn("Another Guest", guest_names_recorded)

    def test_attendance_capture_post_no_section_member_with_event_type(self):
        """Test POST request to record no-section member attendance with event type"""
        attendance_date = date.today()
        custom_notes = "Community Concert"
        
        response = self.client.post(
            reverse('attendance-capture', args=['no-section']),
            {
                'attendance_date': attendance_date.strftime('%Y-%m-%d'),
                'event_type': 'performance_no_gig',
                'event_notes': custom_notes,
                f'member_{self.no_section_member.id}': 'on',
            }
        )
        
        self.assertEqual(response.status_code, 200)
        
        # Check attendance record was created with correct notes
        attendance_record = AttendanceRecord.objects.get(
            date=attendance_date,
            member=self.no_section_member
        )
        self.assertEqual(attendance_record.notes, f'Performance: {custom_notes}')

    def test_attendance_capture_post_no_section_guest_with_event_type(self):
        """Test POST request to record no-section guest attendance with event type"""
        attendance_date = date.today()
        guest_names = "Community Guest"
        
        response = self.client.post(
            reverse('attendance-capture', args=['no-section']),
            {
                'attendance_date': attendance_date.strftime('%Y-%m-%d'),
                'event_type': 'rehearsal',
                'guest_no_section': guest_names,
            }
        )
        
        self.assertEqual(response.status_code, 200)
        
        # Check guest attendance record was created with correct notes
        guest_record = AttendanceRecord.objects.get(
            date=attendance_date,
            guest_name="Community Guest"
        )
        self.assertEqual(guest_record.notes, 'Guest - Rehearsal')

    def test_attendance_capture_post_populates_join_date_if_null(self):
        """Test that recording attendance populates join_date if it hasn't been set yet"""
        attendance_date = date.today()
        
        # Create a member without a join_date
        member_no_join_date = Member.objects.create(
            first_name="New",
            last_name="Member",
            email="new.member@example.com",
            is_active=True,
            join_date=None  # Explicitly set to None
        )
        MemberInstrument.objects.create(member=member_no_join_date, instrument=self.trumpet)
        
        # Verify join_date is None before attendance
        self.assertIsNone(member_no_join_date.join_date)
        
        response = self.client.post(
            reverse('attendance-capture', args=['high-brass']),
            {
                'attendance_date': attendance_date.strftime('%Y-%m-%d'),
                f'member_{member_no_join_date.id}': 'on',
            }
        )
        
        self.assertEqual(response.status_code, 200)
        
        # Check that join_date was populated with attendance date
        member_no_join_date.refresh_from_db()
        self.assertEqual(member_no_join_date.join_date, attendance_date)
        
        # Check that last_seen was also updated
        self.assertEqual(member_no_join_date.last_seen, attendance_date)

    def test_attendance_capture_post_preserves_existing_join_date(self):
        """Test that recording attendance preserves existing join_date"""
        attendance_date = date.today()
        existing_join_date = date.today() - timedelta(days=30)
        
        # Create a member with an existing join_date
        member_with_join_date = Member.objects.create(
            first_name="Existing",
            last_name="Member",
            email="existing.member@example.com",
            is_active=True,
            join_date=existing_join_date
        )
        MemberInstrument.objects.create(member=member_with_join_date, instrument=self.trumpet)
        
        # Verify join_date is set before attendance
        self.assertEqual(member_with_join_date.join_date, existing_join_date)
        
        response = self.client.post(
            reverse('attendance-capture', args=['high-brass']),
            {
                'attendance_date': attendance_date.strftime('%Y-%m-%d'),
                f'member_{member_with_join_date.id}': 'on',
            }
        )
        
        self.assertEqual(response.status_code, 200)
        
        # Check that join_date was NOT changed
        member_with_join_date.refresh_from_db()
        self.assertEqual(member_with_join_date.join_date, existing_join_date)
        
        # Check that last_seen was updated
        self.assertEqual(member_with_join_date.last_seen, attendance_date)

    def test_attendance_capture_post_activates_inactive_member(self):
        """Test that recording attendance sets is_active to True for inactive members"""
        attendance_date = date.today()
        
        # Create an inactive member
        inactive_member = Member.objects.create(
            first_name="Inactive",
            last_name="Member",
            email="inactive.member@example.com",
            is_active=False,  # Explicitly set to False
            join_date=date.today() - timedelta(days=30)
        )
        MemberInstrument.objects.create(member=inactive_member, instrument=self.trumpet)
        
        # Verify member is inactive before attendance
        self.assertFalse(inactive_member.is_active)
        
        response = self.client.post(
            reverse('attendance-capture', args=['high-brass']),
            {
                'attendance_date': attendance_date.strftime('%Y-%m-%d'),
                f'member_{inactive_member.id}': 'on',
            }
        )
        
        self.assertEqual(response.status_code, 200)
        
        # Check that is_active was set to True
        inactive_member.refresh_from_db()
        self.assertTrue(inactive_member.is_active)
        
        # Check that last_seen was also updated
        self.assertEqual(inactive_member.last_seen, attendance_date)

    def test_attendance_capture_post_preserves_active_status(self):
        """Test that recording attendance preserves is_active=True for already active members"""
        attendance_date = date.today()
        
        # Create an active member
        active_member = Member.objects.create(
            first_name="Active",
            last_name="Member",
            email="active.member@example.com",
            is_active=True,
            join_date=date.today() - timedelta(days=30)
        )
        MemberInstrument.objects.create(member=active_member, instrument=self.trumpet)
        
        # Verify member is active before attendance
        self.assertTrue(active_member.is_active)
        
        response = self.client.post(
            reverse('attendance-capture', args=['high-brass']),
            {
                'attendance_date': attendance_date.strftime('%Y-%m-%d'),
                f'member_{active_member.id}': 'on',
            }
        )
        
        self.assertEqual(response.status_code, 200)
        
        # Check that is_active remains True
        active_member.refresh_from_db()
        self.assertTrue(active_member.is_active)
        
        # Check that last_seen was updated
        self.assertEqual(active_member.last_seen, attendance_date)


class AttendanceReportsViewTests(TestCase):
    """Test cases for the attendance_reports view"""

    def setUp(self):
        """Set up test data"""
        self.client = Client()
        
        # Set up SiteSettings with test password
        self.site = Site.objects.get(is_default_site=True)
        self.site_settings = SiteSettings.objects.create(
            site=self.site,
            attendance_password='testpassword'
        )
        
        # Set up HTTP Basic Auth credentials
        credentials = base64.b64encode(b'testuser:testpassword').decode('ascii')
        self.client.defaults['HTTP_AUTHORIZATION'] = f'Basic {credentials}'
        
        # Create test section
        self.section = Section.objects.create(name="Test Section")
        
        # Create test member
        self.member = Member.objects.create(
            first_name="Test",
            last_name="Member",
            email="test@example.com",
            is_active=True
        )
        
        # Create test attendance records
        self.attendance1 = AttendanceRecord.objects.create(
            date=date.today(),
            member=self.member,
            notes="Test attendance"
        )
        self.attendance2 = AttendanceRecord.objects.create(
            date=date.today() - timedelta(days=1),
            guest_name="Test Guest",
            notes="Guest attendance"
        )

    def test_attendance_reports_get(self):
        """Test GET request to attendance reports"""
        response = self.client.get(reverse('attendance-reports'))
        
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Attendance Reports")
        self.assertEqual(response.context['total_records'], 2)
        self.assertEqual(response.context['member_records'], 1)
        self.assertEqual(response.context['guest_records'], 1)

    def test_attendance_reports_date_filtering(self):
        """Test filtering reports by date range"""
        yesterday = date.today() - timedelta(days=1)
        
        response = self.client.get(reverse('attendance-reports'), {
            'start_date': yesterday.strftime('%Y-%m-%d'),
            'end_date': yesterday.strftime('%Y-%m-%d')
        })
        
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['total_records'], 1)
        
        # Should only include records from yesterday
        records = list(response.context['attendance_records'])
        self.assertEqual(len(records), 1)
        self.assertEqual(records[0], self.attendance2)

    def test_attendance_reports_member_filtering(self):
        """Test filtering reports by specific member"""
        response = self.client.get(reverse('attendance-reports'), {
            'member': self.member.id
        })
        
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['total_records'], 1)
        
        # Should only include member records
        records = list(response.context['attendance_records'])
        self.assertEqual(len(records), 1)
        self.assertEqual(records[0], self.attendance1)

    def test_attendance_reports_htmx_filter_request(self):
        """Test HTMX filter request returns partial content"""
        response = self.client.get(
            reverse('attendance-reports'),
            {'start_date': date.today().strftime('%Y-%m-%d')},
            HTTP_HX_REQUEST='true'
        )
        
        self.assertEqual(response.status_code, 200)
        # Should return reports content partial for filter requests

    def test_attendance_reports_htmx_navigation_request(self):
        """Test HTMX navigation request returns navigation content"""
        response = self.client.get(
            reverse('attendance-reports'),
            HTTP_HX_REQUEST='true'
        )
        
        self.assertEqual(response.status_code, 200)
        # Should return all reports content for navigation


class AttendanceSectionReportViewTests(TestCase):
    """Test cases for the attendance_section_report_new view"""

    def setUp(self):
        """Set up test data"""
        self.client = Client()
        
        # Set up SiteSettings with test password
        self.site = Site.objects.get(is_default_site=True)
        self.site_settings = SiteSettings.objects.create(
            site=self.site,
            attendance_password='testpassword'
        )
        
        # Set up HTTP Basic Auth credentials
        credentials = base64.b64encode(b'testuser:testpassword').decode('ascii')
        self.client.defaults['HTTP_AUTHORIZATION'] = f'Basic {credentials}'
        
        # Create test section
        self.section = Section.objects.create(name="Test Section")
        
        # Create test instrument
        self.instrument = Instrument.objects.create(
            name="Test Instrument",
            section=self.section
        )
        
        # Create test members
        self.member1 = Member.objects.create(
            first_name="Member",
            last_name="One",
            email="member1@example.com",
            is_active=True,
            join_date=date.today() - timedelta(days=90)
        )
        self.member2 = Member.objects.create(
            first_name="Member", 
            last_name="Two",
            email="member2@example.com",
            is_active=True,
            join_date=date.today() - timedelta(days=60)
        )
        
        # Assign instruments
        MemberInstrument.objects.create(member=self.member1, instrument=self.instrument)
        MemberInstrument.objects.create(member=self.member2, instrument=self.instrument)
        
        # Create attendance records
        today = date.today()
        self.attendance1 = AttendanceRecord.objects.create(
            date=today,
            member=self.member1
        )
        self.attendance2 = AttendanceRecord.objects.create(
            date=today - timedelta(days=7),
            member=self.member2
        )
        self.attendance3 = AttendanceRecord.objects.create(
            date=today - timedelta(days=14),
            guest_name="Test Guest"
        )

    def test_section_report_get(self):
        """Test GET request to section report"""
        response = self.client.get(
            reverse('attendance-section-report', args=['test-section'])
        )
        
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['section'], self.section)
        self.assertContains(response, "Test Section")
        
        # Check that section members are included
        section_members = list(response.context['section_members'])
        self.assertIn(self.member1, section_members)
        self.assertIn(self.member2, section_members)

    def test_section_report_invalid_section(self):
        """Test section report with invalid section returns 404"""
        response = self.client.get(
            reverse('attendance-section-report', args=['invalid-section'])
        )
        self.assertEqual(response.status_code, 404)

    def test_section_report_date_range_filtering(self):
        """Test section report with custom date range"""
        start_date = date.today() - timedelta(days=10)
        end_date = date.today() - timedelta(days=5)
        
        response = self.client.get(
            reverse('attendance-section-report', args=['test-section']),
            {
                'start_date': start_date.strftime('%Y-%m-%d'),
                'end_date': end_date.strftime('%Y-%m-%d')
            }
        )
        
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['start_date'], start_date)
        self.assertEqual(response.context['end_date'], end_date)
        
        # Should only include records in date range
        records = list(response.context['attendance_records'])
        record_dates = [record.date for record in records]
        for record_date in record_dates:
            self.assertTrue(start_date <= record_date <= end_date)

    def test_section_report_member_attendance_calculation(self):
        """Test member attendance percentage calculation"""
        response = self.client.get(
            reverse('attendance-section-report', args=['test-section'])
        )
        
        self.assertEqual(response.status_code, 200)
        
        member_attendance = response.context['member_attendance']
        self.assertIn(self.member1, member_attendance)
        self.assertIn(self.member2, member_attendance)
        
        # Check attendance data structure
        member1_stats = member_attendance[self.member1]
        self.assertIn('count', member1_stats)
        self.assertIn('total_tuesdays', member1_stats)
        self.assertIn('percentage', member1_stats)
        
        # Member1 should have 1 attendance record
        self.assertEqual(member1_stats['count'], 1)

    def test_section_report_attendance_by_date(self):
        """Test attendance grouped by date"""
        response = self.client.get(
            reverse('attendance-section-report', args=['test-section'])
        )
        
        self.assertEqual(response.status_code, 200)
        
        attendance_by_date = list(response.context['attendance_by_date'])
        self.assertGreater(len(attendance_by_date), 0)
        
        # Check structure of attendance by date
        for date_record in attendance_by_date:
            self.assertIn('date', date_record)
            self.assertIn('member_count', date_record)
            self.assertIn('guest_count', date_record)
            self.assertIn('total_count', date_record)

    def test_section_report_htmx_request(self):
        """Test HTMX request returns partial template"""
        response = self.client.get(
            reverse('attendance-section-report', args=['test-section']),
            HTTP_HX_REQUEST='true'
        )
        
        self.assertEqual(response.status_code, 200)
        # Should return section report content partial

    def test_section_report_tuesday_calculation(self):
        """Test that Tuesday calculation works correctly for attendance percentage"""
        # Create a member with a specific join date
        join_date = date(2024, 1, 2)  # A Tuesday
        test_member = Member.objects.create(
            first_name="Test",
            last_name="Tuesday",
            email="tuesday@example.com",
            is_active=True,
            join_date=join_date
        )
        MemberInstrument.objects.create(member=test_member, instrument=self.instrument)
        
        # Create attendance for specific Tuesdays
        AttendanceRecord.objects.create(
            date=date(2024, 1, 9),  # Next Tuesday
            member=test_member
        )
        
        response = self.client.get(
            reverse('attendance-section-report', args=['test-section']),
            {
                'start_date': '2024-01-01',
                'end_date': '2024-01-31'
            }
        )
        
        self.assertEqual(response.status_code, 200)
        
        member_attendance = response.context['member_attendance']
        if test_member in member_attendance:
            stats = member_attendance[test_member]
            # Should calculate based on Tuesdays only
            self.assertGreater(stats['total_tuesdays'], 0)
            self.assertGreaterEqual(stats['percentage'], 0)
            self.assertLessEqual(stats['percentage'], 100)


class AttendanceViewsIntegrationTests(TestCase):
    def test_attendance_capture_post_populates_join_date_if_null(self):
        """Test that recording attendance populates join_date if it hasn't been set yet"""
        attendance_date = date.today()
        
        # Create a member without a join_date
        member_no_join_date = Member.objects.create(
            first_name="New",
            last_name="Member",
            email="new.member@example.com",
            is_active=True,
            join_date=None  # Explicitly set to None
        )
        MemberInstrument.objects.create(member=member_no_join_date, instrument=self.trumpet)
        
        # Verify join_date is None before attendance
        self.assertIsNone(member_no_join_date.join_date)
        
        response = self.client.post(
            reverse('attendance-capture', args=['high-brass']),
            {
                'attendance_date': attendance_date.strftime('%Y-%m-%d'),
                f'member_{member_no_join_date.id}': 'on',
            }
        )
        
        self.assertEqual(response.status_code, 200)
        
        # Check that join_date was populated with attendance date
        member_no_join_date.refresh_from_db()
        self.assertEqual(member_no_join_date.join_date, attendance_date)
        
        # Check that last_seen was also updated
        self.assertEqual(member_no_join_date.last_seen, attendance_date)
    
    def test_attendance_capture_post_preserves_existing_join_date(self):
        """Test that recording attendance preserves existing join_date"""
        attendance_date = date.today()
        existing_join_date = date.today() - timedelta(days=30)
        
        # Create a member with an existing join_date
        member_with_join_date = Member.objects.create(
            first_name="Existing",
            last_name="Member",
            email="existing.member@example.com",
            is_active=True,
            join_date=existing_join_date
        )
        MemberInstrument.objects.create(member=member_with_join_date, instrument=self.trumpet)
        
        # Verify join_date is set before attendance
        self.assertEqual(member_with_join_date.join_date, existing_join_date)
        
        response = self.client.post(
            reverse('attendance-capture', args=['high-brass']),
            {
                'attendance_date': attendance_date.strftime('%Y-%m-%d'),
                f'member_{member_with_join_date.id}': 'on',
            }
        )
        
        self.assertEqual(response.status_code, 200)
        
        # Check that join_date was NOT changed
        member_with_join_date.refresh_from_db()
        self.assertEqual(member_with_join_date.join_date, existing_join_date)
        
        # Check that last_seen was updated
        self.assertEqual(member_with_join_date.last_seen, attendance_date)


class AttendanceViewsIntegrationTests(TestCase):
    """Integration tests for attendance views working together"""

    def setUp(self):
        """Set up test data"""
        self.client = Client()
        
        # Set up SiteSettings with test password
        self.site = Site.objects.get(is_default_site=True)
        self.site_settings = SiteSettings.objects.create(
            site=self.site,
            attendance_password='testpassword'
        )
        
        # Set up HTTP Basic Auth credentials
        credentials = base64.b64encode(b'testuser:testpassword').decode('ascii')
        self.client.defaults['HTTP_AUTHORIZATION'] = f'Basic {credentials}'
        
        # Create comprehensive test data
        self.section1 = Section.objects.create(name="Brass")
        self.section2 = Section.objects.create(name="Woodwinds")
        
        self.instrument1 = Instrument.objects.create(name="Trumpet", section=self.section1)
        self.instrument2 = Instrument.objects.create(name="Clarinet", section=self.section2)
        
        self.member1 = Member.objects.create(
            first_name="John",
            last_name="Doe",
            email="john@example.com",
            is_active=True
        )
        self.member2 = Member.objects.create(
            first_name="Jane",
            last_name="Smith",
            email="jane@example.com",
            is_active=True
        )
        
        MemberInstrument.objects.create(member=self.member1, instrument=self.instrument1)
        MemberInstrument.objects.create(member=self.member2, instrument=self.instrument2)

    def test_full_attendance_workflow(self):
        """Test complete workflow from capture to reports"""
        # 1. Capture attendance
        attendance_date = date.today()
        
        capture_response = self.client.post(
            reverse('attendance-capture', args=['brass']),
            {
                'attendance_date': attendance_date.strftime('%Y-%m-%d'),
                f'member_{self.member1.id}': 'on',
                f'guest_{self.section1.id}': 'Test Guest',
            }
        )
        self.assertEqual(capture_response.status_code, 200)
        
        # 2. Check overall reports
        reports_response = self.client.get(reverse('attendance-reports'))
        self.assertEqual(reports_response.status_code, 200)
        self.assertEqual(reports_response.context['total_records'], 2)
        
        # 3. Check section-specific report
        section_report_response = self.client.get(
            reverse('attendance-section-report', args=['brass'])
        )
        self.assertEqual(section_report_response.status_code, 200)
        
        # Verify the data flows correctly between views
        section_records = list(section_report_response.context['attendance_records'])
        self.assertEqual(len(section_records), 2)  # Member + guest

    def test_navigation_between_views(self):
        """Test navigation URLs work correctly"""
        # Test main attendance page
        main_response = self.client.get(reverse('attendance-main'))
        self.assertEqual(main_response.status_code, 200)
        
        # Test section-specific capture
        section_response = self.client.get(
            reverse('attendance-capture', args=['brass'])
        )
        self.assertEqual(section_response.status_code, 200)
        
        # Test reports
        reports_response = self.client.get(reverse('attendance-reports'))
        self.assertEqual(reports_response.status_code, 200)
        
        # Test section reports
        section_report_response = self.client.get(
            reverse('attendance-section-report', args=['brass'])
        )
        self.assertEqual(section_report_response.status_code, 200)

    def test_slug_handling(self):
        """Test that section slug handling works correctly"""
        # Test various slug formats
        test_cases = [
            ('brass', self.section1),
            ('Brass', self.section1),
            ('BRASS', self.section1),
        ]
        
        for slug, expected_section in test_cases:
            response = self.client.get(
                reverse('attendance-capture', args=[slug])
            )
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.context['section'], expected_section)

    def test_error_handling(self):
        """Test error handling in views"""
        # Test invalid section slugs
        invalid_slugs = ['nonexistent', 'invalid-section']
        
        for slug in invalid_slugs:
            response = self.client.get(reverse('attendance-capture', args=[slug]))
            self.assertEqual(response.status_code, 404)


class GigsEndpointTests(TestCase):
    """Test cases for the gigs-for-date API endpoint"""

    def setUp(self):
        """Set up test data"""
        self.client = Client()
        self.site = Site.objects.get(is_default_site=True)
        
        # Create SiteSettings with no password for testing
        SiteSettings.objects.create(
            site=self.site,
            attendance_password=None
        )
        
        # Clear cache for clean tests
        from django.core.cache import cache
        cache.clear()

    def test_gigs_for_date_no_date_parameter(self):
        """Test gigs endpoint returns error when no date parameter provided"""
        response = self.client.get(reverse('gigs-for-date'))
        self.assertEqual(response.status_code, 400)
        data = response.json()
        self.assertIn('error', data)
        self.assertEqual(data['error'], 'Date parameter is required')

    def test_gigs_for_date_invalid_date_format(self):
        """Test gigs endpoint returns error for invalid date format"""
        response = self.client.get(reverse('gigs-for-date'), {'date': 'invalid-date'})
        self.assertEqual(response.status_code, 400)
        data = response.json()
        self.assertIn('error', data)
        self.assertEqual(data['error'], 'Invalid date format')

    @patch('requests.get')
    def test_gigs_for_date_api_success(self, mock_get):
        """Test successful gigs API response"""
        # Mock API response
        mock_response = mock_get.return_value
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "gigs": [
                {
                    "id": "123",
                    "title": "Test Concert",
                    "date": "2024-08-15",
                    "gig_status": "Confirmed",
                    "band": "Blowcomotion",
                    "address": "Test Venue"
                },
                {
                    "id": "124",
                    "title": "Different Band Gig",
                    "date": "2024-08-15",
                    "gig_status": "Confirmed",
                    "band": "Other Band",
                    "address": "Other Venue"
                },
                {
                    "id": "125",
                    "title": "Unconfirmed Gig",
                    "date": "2024-08-15",
                    "gig_status": "Tentative",
                    "band": "Blowcomotion",
                    "address": "Test Venue"
                }
            ]
        }
        
        response = self.client.get(reverse('gigs-for-date'), {'date': '2024-08-15'})
        self.assertEqual(response.status_code, 200)
        data = response.json()
        
        # Should only return confirmed Blowcomotion gigs
        self.assertIn('gigs', data)
        self.assertEqual(len(data['gigs']), 1)
        self.assertEqual(data['gigs'][0]['id'], '123')
        self.assertEqual(data['gigs'][0]['title'], 'Test Concert')

    @patch('requests.get')
    def test_gigs_for_date_api_error(self, mock_get):
        """Test handling of API errors"""
        # Mock API error
        mock_get.side_effect = Exception("API connection failed")
        
        response = self.client.get(reverse('gigs-for-date'), {'date': '2024-08-15'})
        self.assertEqual(response.status_code, 500)
        data = response.json()
        self.assertIn('error', data)

    @patch('requests.get')
    def test_gigs_for_date_no_matching_gigs(self, mock_get):
        """Test response when no gigs match the criteria"""
        # Clear cache to ensure clean test
        from django.core.cache import cache
        cache.clear()
        
        # Mock API response with no matching gigs
        mock_response = mock_get.return_value
        mock_response.status_code = 200
        mock_response.json.return_value = {"gigs": []}
        
        response = self.client.get(reverse('gigs-for-date'), {'date': '2024-08-15'})
        self.assertEqual(response.status_code, 200)
        data = response.json()
        
        self.assertIn('gigs', data)
        self.assertEqual(len(data['gigs']), 0)

    def test_attendance_capture_with_gig_selection(self):
        """Test attendance capture with gig selection"""
        # Create test data
        section = Section.objects.create(name="Test Section")
        instrument = Instrument.objects.create(name="Test Instrument", section=section)
        
        attendance_date = date.today()
        
        # Patch requests.get for both member creation and gig API call
        with patch('requests.get') as mock_get:
            # Create member (this will trigger member query API call)
            member = Member.objects.create(
                first_name="Test",
                last_name="Member",
                email="test@example.com",
                is_active=True,
                join_date=date.today() - timedelta(days=30)
            )
            MemberInstrument.objects.create(member=member, instrument=instrument)
            
            # Reset mock after member creation to only count subsequent API calls
            mock_get.reset_mock()
            
            # Mock the individual gig API call that happens during attendance submission
            mock_response = mock_get.return_value
            mock_response.status_code = 200
            mock_response.json.return_value = {
                "id": "123",
                "title": "Test Concert",
                "date": attendance_date.strftime('%Y-%m-%d'),
                "gig_status": "Confirmed",
                "band": "Blowcomotion"
            }
            
            # Submit attendance with gig selection
            response = self.client.post(
                reverse('attendance-capture', args=['test-section']),
                {
                    'attendance_date': attendance_date.strftime('%Y-%m-%d'),
                    'event_type': 'gig_123',
                    f'member_{member.id}': 'on',
                }
            )
            
            self.assertEqual(response.status_code, 200)
            
            # Verify the gig API was called to get gig details
            # Note: There will be additional API calls for member queries during attendance capture
            call_urls = [call[0][0] for call in mock_get.call_args_list]
            self.assertTrue(any('/gigs/123' in url for url in call_urls), 
                          f"Expected gig API call to /gigs/123 but got: {call_urls}")
            
            # Check attendance record was created with gig title
            attendance_record = AttendanceRecord.objects.get(
                date=attendance_date,
                member=member
            )
            self.assertEqual(attendance_record.notes, 'Performance: Test Concert')


class InactiveMembersViewTests(TestCase):
    """Test cases for the inactive_members view"""
    
    def setUp(self):
        # Create test section
        self.section = Section.objects.create(name="Test Section")
        
        # Create test instruments
        self.instrument = Instrument.objects.create(name="Test Instrument", section=self.section)
        
        # Create active and inactive members
        self.active_member = Member.objects.create(
            first_name="Active",
            last_name="Member",
            email="active@test.com",
            is_active=True
        )
        
        self.inactive_member1 = Member.objects.create(
            first_name="Inactive",
            last_name="Member1",
            email="inactive1@test.com",
            is_active=False,
            last_seen=date(2023, 1, 15),
            join_date=date(2022, 6, 1)
        )
        
        self.inactive_member2 = Member.objects.create(
            first_name="Inactive",
            last_name="Member2",
            email="inactive2@test.com",
            is_active=False
        )
        
        # Assign instrument to one inactive member
        MemberInstrument.objects.create(member=self.inactive_member1, instrument=self.instrument)
    
    def test_inactive_members_get_request(self):
        """Test GET request returns inactive members list"""
        response = self.client.get(reverse('inactive-members'))
        
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Inactive Members")
        self.assertContains(response, "Inactive Member1")
        self.assertContains(response, "Inactive Member2")
        self.assertNotContains(response, "Active Member")
        
        # Check that inactive members are in context
        self.assertIn('inactive_members', response.context)
        inactive_members = response.context['inactive_members']
        self.assertEqual(inactive_members.count(), 2)
        self.assertIn(self.inactive_member1, inactive_members)
        self.assertIn(self.inactive_member2, inactive_members)
        self.assertNotIn(self.active_member, inactive_members)
    
    def test_inactive_members_reactivate_member(self):
        """Test POST request to reactivate a member"""
        self.assertFalse(self.inactive_member1.is_active)
        
        response = self.client.post(
            reverse('inactive-members'),
            data={'member_id': self.inactive_member1.id}
        )
        
        self.assertEqual(response.status_code, 200)
        
        # Refresh member from database
        self.inactive_member1.refresh_from_db()
        self.assertTrue(self.inactive_member1.is_active)
        
        # Check success message
        self.assertContains(response, "Successfully reactivated")
        self.assertContains(response, "Inactive Member1")
    
    def test_reactivate_nonexistent_member(self):
        """Test reactivating a non-existent member returns error"""
        response = self.client.post(
            reverse('inactive-members'),
            data={'member_id': 99999}
        )
        
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Member not found or already active")
    
    def test_reactivate_already_active_member(self):
        """Test reactivating an already active member returns error"""
        response = self.client.post(
            reverse('inactive-members'),
            data={'member_id': self.active_member.id}
        )
        
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Member not found or already active")
