"""
Unit tests for birthday views.
"""

from datetime import date, timedelta
from django.test import TestCase, Client
from django.urls import reverse

from blowcomotion.models import Member


class BirthdayViewTests(TestCase):
    """Test cases for the birthdays view"""

    def setUp(self):
        """Set up test data"""
        self.client = Client()
        
        # Create test members with different birthday scenarios
        today = date.today()
        
        # Member with birthday today
        self.member_today = Member.objects.create(
            first_name="John",
            last_name="Today",
            birth_month=today.month,
            birth_day=today.day,
            birth_year=1990,
            is_active=True
        )
        
        # Member with birthday yesterday (recent)
        yesterday = today - timedelta(days=1)
        self.member_yesterday = Member.objects.create(
            first_name="Jane",
            last_name="Yesterday",
            birth_month=yesterday.month,
            birth_day=yesterday.day,
            birth_year=1985,
            is_active=True
        )
        
        # Member with birthday in 5 days (upcoming)
        future_date = today + timedelta(days=5)
        self.member_upcoming = Member.objects.create(
            first_name="Bob",
            last_name="Future",
            birth_month=future_date.month,
            birth_day=future_date.day,
            birth_year=1988,
            is_active=True
        )
        
        # Member with birthday 15 days ago (should not appear)
        old_date = today - timedelta(days=15)
        self.member_old = Member.objects.create(
            first_name="Alice",
            last_name="Old",
            birth_month=old_date.month,
            birth_day=old_date.day,
            birth_year=1992,
            is_active=True
        )
        
        # Inactive member with birthday today (should not appear)
        self.member_inactive = Member.objects.create(
            first_name="Inactive",
            last_name="Member",
            birth_month=today.month,
            birth_day=today.day,
            birth_year=1995,
            is_active=False
        )
        
        # Member with preferred name
        self.member_preferred = Member.objects.create(
            first_name="Robert",
            last_name="Preferred",
            preferred_name="Bobby",
            birth_month=today.month,
            birth_day=today.day,
            birth_year=1993,
            is_active=True
        )

    def test_birthdays_view_accessible(self):
        """Test that the birthdays view is accessible"""
        response = self.client.get(reverse('birthdays'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Member Birthdays")

    def test_today_birthdays_displayed(self):
        """Test that today's birthdays are displayed correctly"""
        response = self.client.get(reverse('birthdays'))
        
        # Check that today's birthday members are in the context
        today_birthdays = response.context['today_birthdays']
        self.assertEqual(len(today_birthdays), 2)  # John and Bobby
        
        # Check that the members are included
        member_names = [b['member'].first_name for b in today_birthdays]
        self.assertIn("John", member_names)
        self.assertIn("Robert", member_names)
        
        # Check that inactive member is not included
        self.assertNotIn("Inactive", member_names)

    def test_upcoming_birthdays_displayed(self):
        """Test that upcoming birthdays are displayed correctly"""
        response = self.client.get(reverse('birthdays'))
        
        # Check that upcoming birthday members are in the context
        upcoming_birthdays = response.context['upcoming_birthdays']
        self.assertEqual(len(upcoming_birthdays), 1)  # Bob
        
        # Check that Bob is included
        self.assertEqual(upcoming_birthdays[0]['member'].first_name, "Bob")
        self.assertEqual(upcoming_birthdays[0]['days_until'], 5)

    def test_recent_birthdays_displayed(self):
        """Test that recent birthdays are displayed correctly"""
        response = self.client.get(reverse('birthdays'))
        
        # Check that recent birthday members are in the context
        recent_birthdays = response.context['recent_birthdays']
        self.assertEqual(len(recent_birthdays), 1)  # Jane
        
        # Check that Jane is included
        self.assertEqual(recent_birthdays[0]['member'].first_name, "Jane")
        self.assertEqual(recent_birthdays[0]['days_ago'], 1)

    def test_old_birthdays_not_displayed(self):
        """Test that birthdays outside the 10-day range are not displayed"""
        response = self.client.get(reverse('birthdays'))
        
        # Alice's birthday was 15 days ago, should not appear in any list
        all_members = []
        for birthday_list in [response.context['today_birthdays'], 
                             response.context['upcoming_birthdays'], 
                             response.context['recent_birthdays']]:
            all_members.extend([b['member'].first_name for b in birthday_list])
        
        self.assertNotIn("Alice", all_members)

    def test_preferred_name_used(self):
        """Test that preferred names are used when available"""
        response = self.client.get(reverse('birthdays'))
        
        # Find Bobby in today's birthdays
        today_birthdays = response.context['today_birthdays']
        bobby_birthday = next((b for b in today_birthdays if b['member'].first_name == "Robert"), None)
        
        self.assertIsNotNone(bobby_birthday)
        self.assertEqual(bobby_birthday['display_name'], "Bobby")

    def test_age_calculation(self):
        """Test that ages are calculated correctly"""
        response = self.client.get(reverse('birthdays'))
        
        # Check John's age calculation
        today_birthdays = response.context['today_birthdays']
        john_birthday = next((b for b in today_birthdays if b['member'].first_name == "John"), None)
        
        self.assertIsNotNone(john_birthday)
        expected_age = date.today().year - 1990
        self.assertEqual(john_birthday['age'], expected_age)

    def test_members_without_birth_info_excluded(self):
        """Test that members without complete birth information are excluded"""
        # Create a member without birth month/day
        Member.objects.create(
            first_name="NoBirth",
            last_name="Member",
            is_active=True
        )
        
        response = self.client.get(reverse('birthdays'))
        
        # Check that this member doesn't appear anywhere
        all_members = []
        for birthday_list in [response.context['today_birthdays'], 
                             response.context['upcoming_birthdays'], 
                             response.context['recent_birthdays']]:
            all_members.extend([b['member'].first_name for b in birthday_list])
        
        self.assertNotIn("NoBirth", all_members)

    def test_template_renders_correctly(self):
        """Test that the template renders without errors"""
        response = self.client.get(reverse('birthdays'))
        
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Member Birthdays")
        self.assertContains(response, "Celebrating our members")
        self.assertContains(response, "Today")
        self.assertContains(response, "Upcoming")
        self.assertContains(response, "Recent")
