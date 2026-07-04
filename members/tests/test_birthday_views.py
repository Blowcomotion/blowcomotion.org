"""
Unit tests for birthday views.

Tests have been updated to work with BIRTHDAY_RANGE_DAYS = 30 (changed from 10).
The birthday view displays birthdays from 30 days in the past to 30 days in the future.
"""

from datetime import date, timedelta

from django.contrib.auth.models import Permission, User
from django.test import Client, TestCase
from django.urls import reverse

from blowcomotion.models import Member


def login_with_perms(client, username, *codenames, superuser=False):
    """Create a user with the given permission codenames (or a superuser) and log them in."""
    if superuser:
        User.objects.create_superuser(username=username, email=f'{username}@example.com', password='pw')
    else:
        user = User.objects.create_user(username=username, password='pw', is_staff=True)
        for codename in codenames:
            user.user_permissions.add(Permission.objects.get(codename=codename))
    client.login(username=username, password='pw')


class BirthdayViewTests(TestCase):
    """Test cases for the birthdays view"""

    def setUp(self):
        """Set up test data"""
        self.client = Client()
        login_with_perms(self.client, 'taker', 'view_attendancerecord')

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
        
        # Member with birthday 25 days ago (recent, should appear)
        recent_date = today - timedelta(days=25)
        self.member_recent_edge = Member.objects.create(
            first_name="Charlie",
            last_name="RecentEdge",
            birth_month=recent_date.month,
            birth_day=recent_date.day,
            birth_year=1990,
            is_active=True
        )
        
        # Member with birthday in 25 days (upcoming, should appear)
        future_edge_date = today + timedelta(days=25)
        self.member_upcoming_edge = Member.objects.create(
            first_name="Diana",
            last_name="UpcomingEdge",
            birth_month=future_edge_date.month,
            birth_day=future_edge_date.day,
            birth_year=1987,
            is_active=True
        )
        
        # Member with birthday 35 days ago (should not appear)
        old_date = today - timedelta(days=35)
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
        self.assertEqual(len(upcoming_birthdays), 2)  # Bob (5 days) and Diana (25 days)
        
        # Check that Bob is included
        bob_birthday = next((b for b in upcoming_birthdays if b['member'].first_name == "Bob"), None)
        self.assertIsNotNone(bob_birthday)
        self.assertEqual(bob_birthday['days_until'], 5)
        
        # Check that Diana is included
        diana_birthday = next((b for b in upcoming_birthdays if b['member'].first_name == "Diana"), None)
        self.assertIsNotNone(diana_birthday)
        self.assertEqual(diana_birthday['days_until'], 25)

    def test_recent_birthdays_displayed(self):
        """Test that recent birthdays are displayed correctly"""
        response = self.client.get(reverse('birthdays'))
        
        # Check that recent birthday members are in the context
        recent_birthdays = response.context['recent_birthdays']
        self.assertEqual(len(recent_birthdays), 2)  # Jane (1 day ago) and Charlie (25 days ago)
        
        # Check that Jane is included
        jane_birthday = next((b for b in recent_birthdays if b['member'].first_name == "Jane"), None)
        self.assertIsNotNone(jane_birthday)
        self.assertEqual(jane_birthday['days_ago'], 1)
        
        # Check that Charlie is included
        charlie_birthday = next((b for b in recent_birthdays if b['member'].first_name == "Charlie"), None)
        self.assertIsNotNone(charlie_birthday)
        self.assertEqual(charlie_birthday['days_ago'], 25)

    def test_old_birthdays_not_displayed(self):
        """Test that birthdays outside the 30-day range are not displayed"""
        response = self.client.get(reverse('birthdays'))
        
        # Alice's birthday was 35 days ago, should not appear in any list
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
        self.assertEqual(bobby_birthday['display_name'], "\"Bobby\" Robert")

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


    def test_thirty_day_range_boundary(self):
        """Test that the 30-day range boundary is correctly enforced"""
        response = self.client.get(reverse('birthdays'))
        
        # Verify that members within 30 days are included
        all_displayed_members = []
        for birthday_list in [response.context['today_birthdays'], 
                             response.context['upcoming_birthdays'], 
                             response.context['recent_birthdays']]:
            all_displayed_members.extend([b['member'].first_name for b in birthday_list])
        
        # Should include: John, Robert (today), Jane (1 day ago), Charlie (25 days ago),
        # Bob (5 days future), Diana (25 days future)
        expected_members = ["John", "Robert", "Jane", "Charlie", "Bob", "Diana"]
        for member_name in expected_members:
            self.assertIn(member_name, all_displayed_members, 
                         f"Member {member_name} should be displayed within 30-day range")
        
        # Should not include: Alice (35 days ago), Inactive (inactive member)
        excluded_members = ["Alice", "Inactive"]
        for member_name in excluded_members:
            self.assertNotIn(member_name, all_displayed_members,
                           f"Member {member_name} should not be displayed")

    def test_edge_case_birthdays_included(self):
        """Test that birthdays exactly at the 25-day edges are included"""
        response = self.client.get(reverse('birthdays'))
        
        # Check that Charlie (25 days ago) is in recent birthdays
        recent_birthdays = response.context['recent_birthdays']
        charlie_names = [b['member'].first_name for b in recent_birthdays if b['member'].first_name == "Charlie"]
        self.assertEqual(len(charlie_names), 1, "Charlie should be included in recent birthdays")
        
        # Check that Diana (25 days future) is in upcoming birthdays
        upcoming_birthdays = response.context['upcoming_birthdays']
        diana_names = [b['member'].first_name for b in upcoming_birthdays if b['member'].first_name == "Diana"]
        self.assertEqual(len(diana_names), 1, "Diana should be included in upcoming birthdays")


class BirthdayPermissionTests(TestCase):
    """Test cases for permission-based access to the birthdays view"""

    def setUp(self):
        self.client = Client()

    def test_anonymous_redirected_to_login(self):
        response = self.client.get(reverse('birthdays'))
        self.assertEqual(response.status_code, 302)
        self.assertIn('/member/login/', response.url)

    def test_staff_without_permission_denied(self):
        login_with_perms(self.client, 'staff')
        response = self.client.get(reverse('birthdays'))
        self.assertEqual(response.status_code, 403)

    def test_view_permission_allows_access(self):
        login_with_perms(self.client, 'taker', 'view_attendancerecord')
        response = self.client.get(reverse('birthdays'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Member Birthdays")

    def test_superuser_allowed(self):
        login_with_perms(self.client, 'admin', superuser=True)
        response = self.client.get(reverse('birthdays'))
        self.assertEqual(response.status_code, 200)
