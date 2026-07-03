from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from blowcomotion.models import Member

User = get_user_model()


class HeaderNavMemberGateTests(TestCase):
    """member-login page renders header.html; use it to check nav visibility."""

    def setUp(self):
        self.url = reverse("member-login")

    def test_anonymous_sees_member_login_link(self):
        response = self.client.get(self.url)
        self.assertContains(response, "header__auth-link")
        self.assertContains(response, "Member Login")

    def test_staff_without_linked_member_sees_no_profile_or_logout(self):
        user = User.objects.create_user(username="staffonly", password="pw", is_staff=True)
        self.client.force_login(user)
        response = self.client.get(self.url)
        self.assertNotContains(response, reverse("member-profile"))
        self.assertNotContains(response, "header__auth-logout")

    def test_member_without_staff_sees_profile_link(self):
        user = User.objects.create_user(username="memberonly", password="pw")
        Member.objects.create(first_name="Sam", last_name="Player", email="sam@example.com", user=user)
        self.client.force_login(user)
        response = self.client.get(self.url)
        self.assertContains(response, reverse("member-profile"))

    def test_staff_with_linked_member_sees_profile_link(self):
        user = User.objects.create_user(username="merged", password="pw", is_staff=True)
        Member.objects.create(first_name="Sam", last_name="Player", email="sam2@example.com", user=user)
        self.client.force_login(user)
        response = self.client.get(self.url)
        self.assertContains(response, reverse("member-profile"))

    def test_nonstaff_without_linked_member_still_sees_logout(self):
        """Orphaned User (Member deleted, on_delete=SET_NULL) must keep a way to log out."""
        user = User.objects.create_user(username="orphaned", password="pw")
        self.client.force_login(user)
        response = self.client.get(self.url)
        self.assertContains(response, reverse("member-profile"))
        self.assertContains(response, "header__auth-logout")
