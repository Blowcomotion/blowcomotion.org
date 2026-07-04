from datetime import date, timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from blowcomotion.models import AttendanceRecord, Instrument, Member
from members.auth import create_member_user
from members.views import _attendance_streaks, _count_tuesdays

User = get_user_model()


def make_member(**kwargs):
    defaults = dict(first_name="Casey", last_name="Player", email="casey@example.com")
    defaults.update(kwargs)
    return Member.objects.create(**defaults)


def last_tuesday(before=None):
    """Most recent Tuesday on or before the given date (default today)."""
    d = before or date.today()
    return d - timedelta(days=(d.weekday() - 1) % 7)


class AttendanceViewAuthTests(TestCase):
    def test_anonymous_redirects_to_login(self):
        response = self.client.get(reverse("member-attendance"))
        self.assertRedirects(
            response,
            "/member/login/?next=/member/attendance/",
            fetch_redirect_response=False,
        )

    def test_staff_user_without_member_redirects(self):
        User.objects.create_user(username="staff@example.com", password="StaffP@ss!")
        self.client.login(username="staff@example.com", password="StaffP@ss!")
        response = self.client.get(reverse("member-attendance"))
        self.assertEqual(response.status_code, 302)

    def test_post_not_allowed(self):
        member = make_member()
        user = create_member_user(member)
        user.set_password("Pass123!")
        user.save()
        self.client.login(username="casey@example.com", password="Pass123!")
        response = self.client.post(reverse("member-attendance"))
        self.assertEqual(response.status_code, 405)


class AttendanceViewTests(TestCase):
    def setUp(self):
        self.member = make_member(join_date=date.today() - timedelta(weeks=52))
        self.user = create_member_user(self.member)
        self.user.set_password("Pass123!")
        self.user.save()
        self.client.login(username="casey@example.com", password="Pass123!")

    def test_empty_state_renders(self):
        response = self.client.get(reverse("member-attendance"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "No attendance has been recorded")

    def test_records_and_stats_render(self):
        instrument = Instrument.objects.create(name="Trombone")
        tuesday = last_tuesday()
        for weeks_ago in range(3):
            AttendanceRecord.objects.create(
                member=self.member,
                date=tuesday - timedelta(weeks=weeks_ago),
                played_instrument=instrument,
                notes="Rehearsal",
            )
        response = self.client.get(reverse("member-attendance"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Total events attended")
        self.assertContains(response, "Trombone")
        self.assertContains(response, "Rehearsal")
        self.assertEqual(response.context["stats"]["total"], 3)
        self.assertEqual(response.context["stats"]["current_streak"], 3)
        self.assertEqual(response.context["stats"]["longest_streak"], 3)

    def test_does_not_show_other_members_records(self):
        other = make_member(first_name="Riley", email="riley@example.com")
        AttendanceRecord.objects.create(member=other, date=last_tuesday())
        response = self.client.get(reverse("member-attendance"))
        self.assertContains(response, "No attendance has been recorded")

    def test_guest_records_are_excluded(self):
        AttendanceRecord.objects.create(guest_name="Some Guest", date=last_tuesday())
        response = self.client.get(reverse("member-attendance"))
        self.assertContains(response, "No attendance has been recorded")

    def test_pagination(self):
        start = last_tuesday()
        for weeks_ago in range(60):
            AttendanceRecord.objects.create(
                member=self.member, date=start - timedelta(weeks=weeks_ago)
            )
        response = self.client.get(reverse("member-attendance"))
        self.assertEqual(len(response.context["page_obj"]), 50)
        response = self.client.get(reverse("member-attendance"), {"page": 2})
        self.assertEqual(len(response.context["page_obj"]), 10)

    def test_profile_page_shows_attendance_summary(self):
        AttendanceRecord.objects.create(member=self.member, date=last_tuesday())
        response = self.client.get(reverse("member-profile"))
        self.assertContains(response, "View Attendance Record")
        self.assertEqual(response.context["attendance_total"], 1)


class AttendanceHelperTests(TestCase):
    def test_count_tuesdays_one_week(self):
        # Mon 2026-06-22 .. Sun 2026-06-28 contains one Tuesday (2026-06-23)
        self.assertEqual(_count_tuesdays(date(2026, 6, 22), date(2026, 6, 28)), 1)

    def test_count_tuesdays_empty_range(self):
        self.assertEqual(_count_tuesdays(date(2026, 6, 24), date(2026, 6, 22)), 0)

    def test_streaks_empty(self):
        self.assertEqual(_attendance_streaks([], date(2026, 6, 23)), (0, 0))

    def test_streaks_consecutive_weeks(self):
        today = date(2026, 6, 25)  # Thursday
        tuesdays = [date(2026, 6, 23), date(2026, 6, 16), date(2026, 6, 9)]
        self.assertEqual(_attendance_streaks(tuesdays, today), (3, 3))

    def test_streak_broken_by_gap(self):
        today = date(2026, 6, 25)
        dates = [date(2026, 6, 23), date(2026, 6, 9), date(2026, 6, 2)]
        current, longest = _attendance_streaks(dates, today)
        self.assertEqual(current, 1)
        self.assertEqual(longest, 2)

    def test_current_streak_zero_when_stale(self):
        today = date(2026, 6, 25)
        dates = [date(2026, 5, 5), date(2026, 4, 28)]
        current, longest = _attendance_streaks(dates, today)
        self.assertEqual(current, 0)
        self.assertEqual(longest, 2)

    def test_current_streak_anchors_on_last_week(self):
        # No record yet this week, but last week attended
        today = date(2026, 6, 22)  # Monday, before this week's practice
        dates = [date(2026, 6, 16), date(2026, 6, 9)]
        self.assertEqual(_attendance_streaks(dates, today), (2, 2))

    def test_streak_across_year_boundary(self):
        today = date(2026, 1, 8)
        dates = [date(2026, 1, 6), date(2025, 12, 30)]
        self.assertEqual(_attendance_streaks(dates, today), (2, 2))
