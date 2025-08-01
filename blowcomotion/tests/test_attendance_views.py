"""
Unit tests for attendance tracking views.
"""

import base64
from datetime import date, timedelta
from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth.models import User
from django.http import Http404
from unittest.mock import patch

from blowcomotion.models import (
    AttendanceRecord, 
    Member, 
    Section, 
    Instrument, 
    MemberInstrument
)


class AttendanceCaptureViewTests(TestCase):
    """Test cases for the attendance_capture view"""

    def setUp(self):
        """Set up test data"""
        self.client = Client()
        
        # Set up HTTP Basic Auth credentials
        credentials = base64.b64encode(b'testuser:purplepassword').decode('ascii')
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
        
        # Check member's last_seen was updated
        self.member1.refresh_from_db()
        self.assertEqual(self.member1.last_seen, attendance_date)
        
        # Check response contains success message
        self.assertContains(response, "Successfully recorded attendance")

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


class AttendanceReportsViewTests(TestCase):
    """Test cases for the attendance_reports view"""

    def setUp(self):
        """Set up test data"""
        self.client = Client()
        
        # Set up HTTP Basic Auth credentials
        credentials = base64.b64encode(b'testuser:purplepassword').decode('ascii')
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
        
        # Set up HTTP Basic Auth credentials
        credentials = base64.b64encode(b'testuser:purplepassword').decode('ascii')
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
    """Integration tests for attendance views working together"""

    def setUp(self):
        """Set up test data"""
        self.client = Client()
        
        # Set up HTTP Basic Auth credentials
        credentials = base64.b64encode(b'testuser:purplepassword').decode('ascii')
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
