from unittest.mock import MagicMock, patch

from wagtail.models import Site

from django.core import mail
from django.db.models import Count, Q
from django.test import TestCase, override_settings

from blowcomotion.member_forms import InstrumentRentalRequestForm
from blowcomotion.models import (
    Instrument,
    InstrumentRentalRequestSubmission,
    LibraryInstrument,
    Member,
    SiteSettings,
)
from instruments.patreon import check_patreon_membership


def make_instrument(name="Trumpet"):
    return Instrument.objects.create(name=name)


def make_library_instrument(instrument, status=LibraryInstrument.STATUS_AVAILABLE, serial="SN001"):
    return LibraryInstrument.objects.create(
        instrument=instrument, serial_number=serial, status=status
    )


def make_member(**kwargs):
    defaults = dict(first_name="Sam", last_name="Player", email="sam@example.com",
                    phone="512-555-0100", address="123 Main St",
                    city="Austin", state="TX", zip_code="78701", country="US")
    defaults.update(kwargs)
    return Member.objects.create(**defaults)


class InstrumentRentalRequestSubmissionModelTest(TestCase):
    def setUp(self):
        self.instrument = make_instrument()
        self.member = make_member()

    def test_str_active_request(self):
        sub = InstrumentRentalRequestSubmission.objects.create(
            name="Sam Player",
            email="sam@example.com",
            instrument=self.instrument,
            member=self.member,
            policy_acknowledged=True,
        )
        self.assertIn("pending", str(sub))
        self.assertIn("Trumpet", str(sub))

    def test_str_waitlist(self):
        sub = InstrumentRentalRequestSubmission.objects.create(
            name="Sam Player",
            email="sam@example.com",
            instrument=self.instrument,
            member=self.member,
            is_waitlist=True,
            policy_acknowledged=True,
        )
        self.assertIn("pending", str(sub))

    def test_member_deletion_nulls_fk(self):
        sub = InstrumentRentalRequestSubmission.objects.create(
            name="Sam Player",
            email="sam@example.com",
            instrument=self.instrument,
            member=self.member,
            is_waitlist=False,
            policy_acknowledged=True,
        )
        self.member.delete()
        sub.refresh_from_db()
        self.assertIsNone(sub.member)


class InstrumentHideFieldsTest(TestCase):
    def test_hide_from_rental_default_false(self):
        instr = Instrument.objects.create(name="Piccolo")
        self.assertFalse(instr.hide_from_rental)

    def test_hide_from_member_forms_default_false(self):
        instr = Instrument.objects.create(name="Piccolo")
        self.assertFalse(instr.hide_from_member_forms)


class RentalSubmissionStatusTest(TestCase):
    def setUp(self):
        self.instrument = make_instrument()
        self.member = make_member()

    def test_default_status_is_pending(self):
        sub = InstrumentRentalRequestSubmission.objects.create(
            name="Sam Player", email="sam@example.com",
            instrument=self.instrument, member=self.member, policy_acknowledged=True,
        )
        self.assertEqual(sub.status, InstrumentRentalRequestSubmission.STATUS_PENDING)

    def test_str_includes_status(self):
        sub = InstrumentRentalRequestSubmission.objects.create(
            name="Sam Player", email="sam@example.com",
            instrument=self.instrument, member=self.member, policy_acknowledged=True,
        )
        self.assertIn("pending", str(sub))
        self.assertIn("Trumpet", str(sub))

    def test_second_and_third_choice_nullable(self):
        sub = InstrumentRentalRequestSubmission.objects.create(
            name="Sam Player", email="sam@example.com",
            instrument=self.instrument, member=self.member, policy_acknowledged=True,
        )
        self.assertIsNone(sub.second_choice)
        self.assertIsNone(sub.third_choice)

    def test_second_choice_can_be_set(self):
        other = Instrument.objects.create(name="Tuba")
        sub = InstrumentRentalRequestSubmission.objects.create(
            name="Sam Player", email="sam@example.com",
            instrument=self.instrument, member=self.member,
            second_choice=other, policy_acknowledged=True,
        )
        sub.refresh_from_db()
        self.assertEqual(sub.second_choice, other)


class InstrumentRentalRequestFormTest(TestCase):
    def setUp(self):
        self.instrument = make_instrument("Trombone")
        self.li = make_library_instrument(self.instrument, status=LibraryInstrument.STATUS_AVAILABLE)

    def test_valid_form(self):
        form = InstrumentRentalRequestForm(data={
            "instrument": self.instrument.pk,
            "notes": "Prefer medium bore",
            "policy_acknowledged": True,
        })
        self.assertTrue(form.is_valid(), form.errors)

    def test_instrument_required(self):
        form = InstrumentRentalRequestForm(data={"policy_acknowledged": True})
        self.assertFalse(form.is_valid())
        self.assertIn("instrument", form.errors)

    def test_policy_required(self):
        form = InstrumentRentalRequestForm(data={
            "instrument": self.instrument.pk,
            "policy_acknowledged": False,
        })
        self.assertFalse(form.is_valid())
        self.assertIn("policy_acknowledged", form.errors)

    def test_notes_optional(self):
        form = InstrumentRentalRequestForm(data={
            "instrument": self.instrument.pk,
            "policy_acknowledged": True,
        })
        self.assertTrue(form.is_valid(), form.errors)

    def test_label_shows_available_count(self):
        form = InstrumentRentalRequestForm()
        obj = Instrument.objects.annotate(
            available_count=Count(
                "library_inventory",
                filter=Q(library_inventory__status=LibraryInstrument.STATUS_AVAILABLE),
            )
        ).get(pk=self.instrument.pk)
        label = form.fields["instrument"].label_from_instance(obj)
        self.assertIn("1 available", label)

    def test_label_shows_waitlist_when_zero(self):
        self.li.status = LibraryInstrument.STATUS_RENTED
        self.li.save()
        form = InstrumentRentalRequestForm()
        obj = Instrument.objects.annotate(
            available_count=Count(
                "library_inventory",
                filter=Q(library_inventory__status=LibraryInstrument.STATUS_AVAILABLE),
            )
        ).get(pk=self.instrument.pk)
        label = form.fields["instrument"].label_from_instance(obj)
        self.assertIn("waitlist", label)

    def test_instrument_without_library_record_excluded(self):
        other = Instrument.objects.create(name="Tuba")
        # No LibraryInstrument for "other"
        form = InstrumentRentalRequestForm()
        pks = list(form.fields["instrument"].queryset.values_list("pk", flat=True))
        self.assertNotIn(other.pk, pks)


from django.urls import reverse

from blowcomotion.member_auth import create_member_user


class InstrumentRentalRequestViewTest(TestCase):
    def setUp(self):
        from wagtail.models import Site
        self.instrument = make_instrument("Trumpet")
        self.li = make_library_instrument(self.instrument, status=LibraryInstrument.STATUS_AVAILABLE)
        self.member = make_member()
        self.user = create_member_user(self.member)
        self.user.set_password("Pass123!")
        self.user.save()
        self.client.login(username="sam@example.com", password="Pass123!")
        self.site_settings = SiteSettings.for_site(Site.objects.get(is_default_site=True))
        self.site_settings.instrument_rental_policy = "You must return the instrument."
        patcher = patch("blowcomotion.member_views._validate_recaptcha", return_value=(True, None))
        patcher.start()
        self.addCleanup(patcher.stop)
        self.site_settings.save()

    def test_get_redirects_anonymous(self):
        self.client.logout()
        response = self.client.get(reverse("member-instrument-rental"))
        self.assertRedirects(
            response,
            "/member/login/?next=/member/instrument-rental/",
            fetch_redirect_response=False,
        )

    def test_get_returns_200(self):
        response = self.client.get(reverse("member-instrument-rental"))
        self.assertEqual(response.status_code, 200)

    def test_get_context_has_member_and_form(self):
        response = self.client.get(reverse("member-instrument-rental"))
        self.assertEqual(response.context["member"], self.member)
        self.assertIn("form", response.context)

    def _post(self, extra=None):
        data = {"instrument": self.instrument.pk, "policy_acknowledged": True}
        if extra:
            data.update(extra)
        return self.client.post(reverse("member-instrument-rental"), data)

    def test_post_creates_submission(self):
        self._post()
        self.assertEqual(InstrumentRentalRequestSubmission.objects.count(), 1)

    def test_post_active_request_not_waitlisted(self):
        self._post()
        sub = InstrumentRentalRequestSubmission.objects.first()
        self.assertFalse(sub.is_waitlist)

    def test_post_sets_waitlist_when_none_available(self):
        self.li.status = LibraryInstrument.STATUS_RENTED
        self.li.save()
        self._post()
        sub = InstrumentRentalRequestSubmission.objects.first()
        self.assertTrue(sub.is_waitlist)

    def test_post_snapshots_member_contact_info(self):
        self._post({"notes": "any note"})
        sub = InstrumentRentalRequestSubmission.objects.first()
        self.assertEqual(sub.name, self.member.full_name)
        self.assertEqual(sub.email, self.member.email)
        self.assertEqual(sub.phone, self.member.phone)
        self.assertEqual(sub.address, self.member.address)

    def test_post_stores_notes_in_message(self):
        self._post({"notes": "prefer small bore"})
        sub = InstrumentRentalRequestSubmission.objects.first()
        self.assertEqual(sub.message, "prefer small bore")

    @patch("blowcomotion.member_views._MemberEmail")
    def test_post_sends_two_emails(self, mock_email_cls):
        mock_email_cls.return_value.send.return_value = None
        site_settings = SiteSettings.for_site(Site.objects.get(is_default_site=True))
        site_settings.instrument_rental_notification_recipients = "test@example.com"
        site_settings.save()
        self._post()
        self.assertEqual(mock_email_cls.call_count, 2)

    def test_post_renders_success_state(self):
        response = self._post()
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context["submitted"])
        self.assertEqual(response.context["instrument"], self.instrument)

    def test_invalid_post_rerenders_form_with_errors(self):
        response = self.client.post(reverse("member-instrument-rental"), {"policy_acknowledged": True})
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.context.get("submitted", False))
        self.assertIn("instrument", response.context["form"].errors)

    def test_user_without_member_profile_redirects(self):
        from django.contrib.auth import get_user_model
        User = get_user_model()
        staff = User.objects.create_user(username="staff@example.com", password="StaffP@ss!")
        self.client.login(username="staff@example.com", password="StaffP@ss!")
        response = self.client.get(reverse("member-instrument-rental"))
        self.assertEqual(response.status_code, 302)

    def test_get_shows_coming_soon_when_policy_not_set(self):
        self.site_settings.instrument_rental_policy = ""
        self.site_settings.save()
        response = self.client.get(reverse("member-instrument-rental"))
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context["rental_not_configured"])

    def test_post_blocked_when_policy_not_set(self):
        self.site_settings.instrument_rental_policy = ""
        self.site_settings.save()
        self._post()
        self.assertEqual(InstrumentRentalRequestSubmission.objects.count(), 0)

    def test_get_redirects_when_profile_incomplete(self):
        self.member.phone = ""
        self.member.save(sync_go3=False)
        response = self.client.get(reverse("member-instrument-rental"))
        self.assertRedirects(response, reverse("member-profile"), fetch_redirect_response=False)

    def test_post_redirects_when_profile_incomplete(self):
        self.member.address = ""
        self.member.save(sync_go3=False)
        response = self._post()
        self.assertRedirects(response, reverse("member-profile"), fetch_redirect_response=False)

    def test_post_saves_second_and_third_choice(self):
        second = make_instrument("Trombone")
        make_library_instrument(second)
        third = make_instrument("Tuba")
        make_library_instrument(third)
        self.client.post(reverse("member-instrument-rental"), {
            "instrument": self.instrument.pk,
            "second_choice": second.pk,
            "third_choice": third.pk,
            "policy_acknowledged": True,
        })
        sub = InstrumentRentalRequestSubmission.objects.first()
        self.assertEqual(sub.second_choice, second)
        self.assertEqual(sub.third_choice, third)

    def test_post_sets_status_pending(self):
        self._post()
        sub = InstrumentRentalRequestSubmission.objects.first()
        self.assertEqual(sub.status, InstrumentRentalRequestSubmission.STATUS_PENDING)

    def test_post_success_no_patreon_in_context(self):
        response = self._post()
        self.assertNotIn("patreon_url", response.context)


class InstrumentRentalFormV2Test(TestCase):
    def setUp(self):
        self.visible = make_instrument("Trumpet")
        make_library_instrument(self.visible)
        self.hidden = Instrument.objects.create(name="Vintage Sousaphone", hide_from_rental=True)
        make_library_instrument(self.hidden, serial="RARE001")

    def test_hidden_instrument_excluded_from_rental_form(self):
        form = InstrumentRentalRequestForm()
        pks = list(form.fields["instrument"].queryset.values_list("pk", flat=True))
        self.assertNotIn(self.hidden.pk, pks)
        self.assertIn(self.visible.pk, pks)

    def test_second_choice_optional(self):
        form = InstrumentRentalRequestForm(data={
            "instrument": self.visible.pk,
            "policy_acknowledged": True,
        })
        self.assertTrue(form.is_valid(), form.errors)
        self.assertIsNone(form.cleaned_data["second_choice"])

    def test_second_choice_accepts_valid_instrument(self):
        second = make_instrument("Trombone")
        make_library_instrument(second)
        form = InstrumentRentalRequestForm(data={
            "instrument": self.visible.pk,
            "second_choice": second.pk,
            "policy_acknowledged": True,
        })
        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(form.cleaned_data["second_choice"], second)

    def test_hidden_instrument_excluded_from_second_choice(self):
        form = InstrumentRentalRequestForm()
        pks = list(form.fields["second_choice"].queryset.values_list("pk", flat=True))
        self.assertNotIn(self.hidden.pk, pks)


class InstrumentRentalTemplateTest(TestCase):
    def setUp(self):
        from wagtail.models import Site
        self.instrument = make_instrument("Trumpet")
        make_library_instrument(self.instrument)
        self.member = make_member()
        self.user = create_member_user(self.member)
        self.user.set_password("Pass123!")
        self.user.save()
        self.client.login(username="sam@example.com", password="Pass123!")
        self.site_settings = SiteSettings.for_site(Site.objects.get(is_default_site=True))
        self.site_settings.instrument_rental_policy = "You must return it."
        self.site_settings.save()
        patcher = patch("blowcomotion.member_views._validate_recaptcha", return_value=(True, None))
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_form_shows_coming_soon_when_policy_not_set(self):
        self.site_settings.instrument_rental_policy = ""
        self.site_settings.save()
        response = self.client.get(reverse("member-instrument-rental"))
        self.assertContains(response, "Coming soon")

    def test_form_shows_second_and_third_choice_fields(self):
        response = self.client.get(reverse("member-instrument-rental"))
        self.assertContains(response, "Second choice")
        self.assertContains(response, "Third choice")

    def test_success_state_has_no_patreon_prompt(self):
        with patch("blowcomotion.member_views._MemberEmail"):
            response = self.client.post(reverse("member-instrument-rental"), {
                "instrument": self.instrument.pk,
                "policy_acknowledged": True,
            })
        self.assertNotContains(response, "Patreon")
        self.assertNotContains(response, "patreon")

    def test_success_state_shows_in_touch(self):
        with patch("blowcomotion.member_views._MemberEmail"):
            response = self.client.post(reverse("member-instrument-rental"), {
                "instrument": self.instrument.pk,
                "policy_acknowledged": True,
            })
        self.assertContains(response, "in touch")


class RentalRequestsAdminViewTest(TestCase):
    def setUp(self):
        from django.contrib.auth import get_user_model
        User = get_user_model()
        self.instrument = make_instrument("Trumpet")
        self.li = make_library_instrument(self.instrument)
        self.member = make_member()
        self.submission = InstrumentRentalRequestSubmission.objects.create(
            name=self.member.full_name,
            email=self.member.email,
            instrument=self.instrument,
            member=self.member,
            status=InstrumentRentalRequestSubmission.STATUS_PENDING,
            policy_acknowledged=True,
        )
        self.admin_user = User.objects.create_superuser(
            username="admin@example.com",
            email="admin@example.com",
            password="AdminP@ss!",
        )
        self.client.force_login(self.admin_user)

    def test_dashboard_returns_200(self):
        response = self.client.get(reverse("rental_requests_dashboard"))
        self.assertEqual(response.status_code, 200)

    def test_review_get_returns_200(self):
        response = self.client.get(reverse("rental_request_review", args=[self.submission.pk]))
        self.assertEqual(response.status_code, 200)

    def test_dashboard_requires_login(self):
        self.client.logout()
        response = self.client.get(reverse("rental_requests_dashboard"))
        self.assertIn(response.status_code, [302, 403])

    @patch("instruments.views._MemberEmail")
    def test_approve_updates_submission_and_unit(self, mock_email_cls):
        mock_email_cls.return_value.send.return_value = None
        self.client.post(
            reverse("rental_request_review", args=[self.submission.pk]),
            {"action": "approve", "unit": self.li.pk, "message": "Pick up Tuesday."},
        )
        self.submission.refresh_from_db()
        self.assertEqual(self.submission.status, InstrumentRentalRequestSubmission.STATUS_APPROVED)
        self.assertEqual(self.submission.assigned_unit, self.li)
        self.li.refresh_from_db()
        self.assertEqual(self.li.status, LibraryInstrument.STATUS_RENTED)
        self.assertEqual(self.li.member, self.member)

    @patch("instruments.views._MemberEmail")
    def test_approve_sets_member_renting(self, mock_email_cls):
        mock_email_cls.return_value.send.return_value = None
        self.client.post(
            reverse("rental_request_review", args=[self.submission.pk]),
            {"action": "approve", "unit": self.li.pk, "message": "Go ahead."},
        )
        self.member.refresh_from_db()
        self.assertTrue(self.member.renting)

    @patch("instruments.views._MemberEmail")
    def test_approve_sends_email(self, mock_email_cls):
        mock_email_cls.return_value.send.return_value = None
        self.client.post(
            reverse("rental_request_review", args=[self.submission.pk]),
            {"action": "approve", "unit": self.li.pk, "message": "Approved."},
        )
        self.assertEqual(mock_email_cls.call_count, 1)

    @patch("instruments.views._MemberEmail")
    def test_deny_updates_submission(self, mock_email_cls):
        mock_email_cls.return_value.send.return_value = None
        self.client.post(
            reverse("rental_request_review", args=[self.submission.pk]),
            {"action": "deny", "message": "No units available."},
        )
        self.submission.refresh_from_db()
        self.assertEqual(self.submission.status, InstrumentRentalRequestSubmission.STATUS_DENIED)
        self.assertEqual(self.submission.admin_message, "No units available.")

    def test_approve_without_unit_stays_pending(self):
        self.client.post(
            reverse("rental_request_review", args=[self.submission.pk]),
            {"action": "approve", "message": "Approved."},
        )
        self.submission.refresh_from_db()
        self.assertEqual(self.submission.status, InstrumentRentalRequestSubmission.STATUS_PENDING)

    def test_action_on_non_pending_submission_does_nothing(self):
        self.submission.status = InstrumentRentalRequestSubmission.STATUS_APPROVED
        self.submission.save()
        self.client.post(
            reverse("rental_request_review", args=[self.submission.pk]),
            {"action": "deny", "message": "Denied."},
        )
        self.submission.refresh_from_db()
        self.assertEqual(self.submission.status, InstrumentRentalRequestSubmission.STATUS_APPROVED)

    def test_approve_email_does_not_html_encode_special_chars(self):
        self.client.post(
            reverse("rental_request_review", args=[self.submission.pk]),
            {"action": "approve", "unit": self.li.pk, "message": "You're all set & ready — bring your ID."},
        )
        self.assertEqual(len(mail.outbox), 1)
        body = mail.outbox[0].body
        self.assertIn("You're all set & ready", body)
        self.assertNotIn("&#x27;", body)
        self.assertNotIn("&amp;", body)

    def test_deny_email_does_not_html_encode_special_chars(self):
        self.client.post(
            reverse("rental_request_review", args=[self.submission.pk]),
            {"action": "deny", "message": "Sorry — no \"trumpet\" available right now."},
        )
        self.assertEqual(len(mail.outbox), 1)
        body = mail.outbox[0].body
        self.assertIn('no "trumpet"', body)
        self.assertNotIn("&quot;", body)
        self.assertNotIn("&#x27;", body)

    def _make_approved_submission(self):
        """Return a submission in STATUS_APPROVED with a rented unit assigned."""
        import datetime
        self.li.status = LibraryInstrument.STATUS_RENTED
        self.li.member = self.member
        self.li.last_nag_sent = None
        self.li.save()
        self.submission.status = InstrumentRentalRequestSubmission.STATUS_APPROVED
        self.submission.assigned_unit = self.li
        self.submission.save()

    def test_nag_one_sends_email_and_updates_last_nag_sent(self):
        self._make_approved_submission()
        self.client.post(
            reverse("rental_requests_dashboard"),
            {"action": "nag_one", "pk": self.submission.pk},
        )
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn(self.member.email, mail.outbox[0].to)
        self.li.refresh_from_db()
        self.assertIsNotNone(self.li.last_nag_sent)

    def test_nag_one_respects_cooldown(self):
        import datetime
        self._make_approved_submission()
        self.li.last_nag_sent = datetime.date.today()
        self.li.save()
        self.client.post(
            reverse("rental_requests_dashboard"),
            {"action": "nag_one", "pk": self.submission.pk},
        )
        self.assertEqual(len(mail.outbox), 0)

    def test_nag_all_emails_eligible_renter(self):
        self.li.status = LibraryInstrument.STATUS_RENTED
        self.li.member = self.member
        self.li.save()
        self.client.post(
            reverse("rental_requests_dashboard"),
            {"action": "nag_all"},
        )
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn(self.member.email, mail.outbox[0].to)

    def test_nag_all_skips_cooldown_renter(self):
        import datetime
        self.li.status = LibraryInstrument.STATUS_RENTED
        self.li.member = self.member
        self.li.last_nag_sent = datetime.date.today()
        self.li.save()
        self.client.post(
            reverse("rental_requests_dashboard"),
            {"action": "nag_all"},
        )
        self.assertEqual(len(mail.outbox), 0)

    def test_nag_one_no_assigned_unit(self):
        self.submission.status = InstrumentRentalRequestSubmission.STATUS_APPROVED
        self.submission.assigned_unit = None
        self.submission.save()
        self.client.post(
            reverse("rental_requests_dashboard"),
            {"action": "nag_one", "pk": self.submission.pk},
        )
        self.assertEqual(len(mail.outbox), 0)

    def test_nag_one_no_reasons_warns(self):
        import datetime
        self._make_approved_submission()
        # Mark member active in attendance and patreon
        self.member.last_seen = datetime.date.today()
        self.member.save()
        self.submission.patreon_validated = True
        self.submission.save()
        response = self.client.post(
            reverse("rental_requests_dashboard"),
            {"action": "nag_one", "pk": self.submission.pk},
            follow=True,
        )
        self.assertEqual(len(mail.outbox), 0)
        self.assertContains(response, "appears active")

    @override_settings(FORM_TEST_EMAIL="test@example.com")
    def test_nag_all_sends_admin_summary_and_copy(self):
        from wagtail.models import Site
        site_settings = SiteSettings.for_site(Site.objects.get(is_default_site=True))
        site_settings.instrument_rental_notification_recipients = "admin@example.com"
        site_settings.save()
        self.li.status = LibraryInstrument.STATUS_RENTED
        self.li.member = self.member
        self.li.save()
        self.client.post(
            reverse("rental_requests_dashboard"),
            {"action": "nag_all"},
        )
        # renter email + admin summary + FORM_TEST_EMAIL copy
        self.assertEqual(len(mail.outbox), 3)
        subjects = [m.subject for m in mail.outbox]
        self.assertTrue(any("Summary" in s for s in subjects))
        self.assertTrue(any("[COPY]" in s for s in subjects))

    def test_nag_all_preview_lists_eligible_renter_with_reason(self):
        self.li.status = LibraryInstrument.STATUS_RENTED
        self.li.member = self.member
        self.li.save()
        response = self.client.get(reverse("rental_requests_dashboard"))
        preview = response.context["nag_all_preview"]
        self.assertEqual(len(preview), 1)
        self.assertEqual(preview[0]["member"], self.member)
        self.assertIn("attendance", preview[0]["reasons"])
        self.assertFalse(preview[0]["in_cooldown"])
        self.assertIn(self.member.full_name, response.context["nag_all_confirm_message"])

    def test_nag_all_preview_matches_who_nag_all_actually_emails(self):
        # The preview (GET) and the real send (POST) must derive from the same
        # eligibility computation, or the confirm step could show a different
        # set of renters than actually get nagged. Includes a cooldown renter
        # so the full preview list and the sendable (non-cooldown) subset can
        # be told apart — comparing the full preview to sent mail would pass
        # even if cooldown-skipped renters leaked into the confirm text.
        import datetime
        other_instrument = make_instrument("Trombone")
        other_li = make_library_instrument(other_instrument, serial="SN002")
        other_member = make_member(email="other@example.com", first_name="Robin", last_name="Brass")

        self.li.status = LibraryInstrument.STATUS_RENTED
        self.li.member = self.member
        self.li.save()

        other_li.status = LibraryInstrument.STATUS_RENTED
        other_li.member = other_member
        other_li.last_nag_sent = datetime.date.today()
        other_li.save()

        response = self.client.get(reverse("rental_requests_dashboard"))
        preview = response.context["nag_all_preview"]
        confirm_message = response.context["nag_all_confirm_message"]
        preview_emails = {item["member"].email for item in preview}
        sendable_emails = {item["member"].email for item in preview if not item["in_cooldown"]}

        # Both renters are eligible, so both appear in the full preview...
        self.assertEqual(preview_emails, {self.member.email, other_member.email})
        # ...but only the non-cooldown renter is sendable, and only they're
        # named in the confirm text.
        self.assertEqual(sendable_emails, {self.member.email})
        self.assertIn(self.member.full_name, confirm_message)
        self.assertNotIn(other_member.full_name, confirm_message)

        self.client.post(reverse("rental_requests_dashboard"), {"action": "nag_all"})
        sent_emails = {addr for m in mail.outbox for addr in m.to}

        self.assertEqual(sendable_emails, sent_emails)

    def test_nag_all_preview_marks_cooldown_renter_but_excludes_from_confirm_text(self):
        import datetime
        self.li.status = LibraryInstrument.STATUS_RENTED
        self.li.member = self.member
        self.li.last_nag_sent = datetime.date.today()
        self.li.save()
        response = self.client.get(reverse("rental_requests_dashboard"))
        preview = response.context["nag_all_preview"]
        self.assertEqual(len(preview), 1)
        self.assertTrue(preview[0]["in_cooldown"])
        self.assertNotIn(self.member.full_name, response.context["nag_all_confirm_message"])

    def test_nag_all_confirm_message_when_none_eligible(self):
        response = self.client.get(reverse("rental_requests_dashboard"))
        self.assertEqual(response.context["nag_all_preview"], [])
        self.assertIn("No renters are currently eligible", response.context["nag_all_confirm_message"])

    def test_delete_removes_denied_submission(self):
        self.submission.status = InstrumentRentalRequestSubmission.STATUS_DENIED
        self.submission.save()
        pk = self.submission.pk
        self.client.post(
            reverse("rental_requests_dashboard"),
            {"action": "delete", "pk": pk},
        )
        self.assertFalse(
            InstrumentRentalRequestSubmission.objects.filter(pk=pk).exists()
        )

    def test_delete_on_non_denied_submission_returns_404(self):
        self.submission.status = InstrumentRentalRequestSubmission.STATUS_PENDING
        self.submission.save()
        pk = self.submission.pk
        response = self.client.post(
            reverse("rental_requests_dashboard"),
            {"action": "delete", "pk": pk},
        )
        self.assertEqual(response.status_code, 404)
        self.assertTrue(
            InstrumentRentalRequestSubmission.objects.filter(pk=pk).exists()
        )

    def test_delete_on_approved_submission_returns_404(self):
        self._make_approved_submission()
        pk = self.submission.pk
        response = self.client.post(
            reverse("rental_requests_dashboard"),
            {"action": "delete", "pk": pk},
        )
        self.assertEqual(response.status_code, 404)
        self.assertTrue(
            InstrumentRentalRequestSubmission.objects.filter(pk=pk).exists()
        )


class PatreonClientTest(TestCase):
    """Unit tests for check_patreon_membership() in patreon_client.py.

    Responses are shaped like real Patreon API v2 paginated member lists:
      - data: list of member objects with attributes.email and attributes.patron_status
      - links.next: URL for the next page (absent on the final page)
    """


    def _make_page(self, members, next_url=None):
        """Build a mock requests.Response representing one page of members."""
    
        resp = MagicMock()
        resp.raise_for_status.return_value = None
        payload = {
            "data": [
                {
                    "id": str(i),
                    "type": "member",
                    "attributes": {
                        "email": m["email"],
                        "patron_status": m["patron_status"],
                    },
                }
                for i, m in enumerate(members)
            ]
        }
        if next_url:
            payload["links"] = {"next": next_url}
        resp.json.return_value = payload
        return resp

    @patch("instruments.patreon.requests.get")
    def test_active_patron_returns_true(self, mock_get):


        mock_get.return_value = self._make_page([
            {"email": "patron@example.com", "patron_status": "active_patron"}
        ])
        with override_settings(PATREON_ACCESS_TOKEN="tok", PATREON_CAMPAIGN_ID="cam123"):
            result = check_patreon_membership("patron@example.com")
        self.assertTrue(result["is_active"])

    @patch("instruments.patreon.requests.get")
    def test_declined_patron_returns_false(self, mock_get):


        mock_get.return_value = self._make_page([
            {"email": "lapsed@example.com", "patron_status": "declined_patron"}
        ])
        with override_settings(PATREON_ACCESS_TOKEN="tok", PATREON_CAMPAIGN_ID="cam123"):
            result = check_patreon_membership("lapsed@example.com")
        self.assertFalse(result["is_active"])

    @patch("instruments.patreon.requests.get")
    def test_member_not_found_returns_false(self, mock_get):


        mock_get.return_value = self._make_page([])
        with override_settings(PATREON_ACCESS_TOKEN="tok", PATREON_CAMPAIGN_ID="cam123"):
            result = check_patreon_membership("nobody@example.com")
        self.assertFalse(result["is_active"])

    def test_missing_token_returns_none(self):


        with override_settings(PATREON_ACCESS_TOKEN=None, PATREON_CAMPAIGN_ID=None):
            result = check_patreon_membership("any@example.com")
        self.assertIsNone(result)

    def test_missing_campaign_id_returns_none(self):


        with override_settings(PATREON_ACCESS_TOKEN="tok", PATREON_CAMPAIGN_ID=None):
            result = check_patreon_membership("any@example.com")
        self.assertIsNone(result)

    @patch("instruments.patreon.requests.get")
    def test_email_match_is_case_insensitive(self, mock_get):


        mock_get.return_value = self._make_page([
            {"email": "Patron@Example.COM", "patron_status": "active_patron"}
        ])
        with override_settings(PATREON_ACCESS_TOKEN="tok", PATREON_CAMPAIGN_ID="cam123"):
            result = check_patreon_membership("patron@example.com")
        self.assertTrue(result["is_active"])

    @patch("instruments.patreon.requests.get")
    def test_member_found_on_second_page(self, mock_get):
        """Email appears on page 2 — pagination must be followed."""


        page1 = self._make_page(
            [{"email": "other@example.com", "patron_status": "active_patron"}],
            next_url="https://www.patreon.com/api/oauth2/v2/campaigns/cam123/members?page[cursor]=abc",
        )
        page2 = self._make_page(
            [{"email": "patron@example.com", "patron_status": "active_patron"}]
        )
        mock_get.side_effect = [page1, page2]
        with override_settings(PATREON_ACCESS_TOKEN="tok", PATREON_CAMPAIGN_ID="cam123"):
            result = check_patreon_membership("patron@example.com")
        self.assertTrue(result["is_active"])
        self.assertEqual(mock_get.call_count, 2)

    @patch("instruments.patreon.requests.get")
    def test_timeout_returns_none(self, mock_get):
        import requests as req_lib



        mock_get.side_effect = req_lib.exceptions.Timeout
        with override_settings(PATREON_ACCESS_TOKEN="tok", PATREON_CAMPAIGN_ID="cam123"):
            result = check_patreon_membership("patron@example.com")
        self.assertIsNone(result)

    @patch("instruments.patreon.requests.get")
    def test_connection_error_returns_none(self, mock_get):
        import requests as req_lib



        mock_get.side_effect = req_lib.exceptions.ConnectionError
        with override_settings(PATREON_ACCESS_TOKEN="tok", PATREON_CAMPAIGN_ID="cam123"):
            result = check_patreon_membership("patron@example.com")
        self.assertIsNone(result)

    @patch("instruments.patreon.requests.get")
    def test_http_error_returns_none(self, mock_get):
        import requests as req_lib



        mock_resp = req_lib.models.Response()
        mock_resp.status_code = 401
        mock_get.side_effect = req_lib.exceptions.HTTPError(response=mock_resp)
        with override_settings(PATREON_ACCESS_TOKEN="tok", PATREON_CAMPAIGN_ID="cam123"):
            result = check_patreon_membership("patron@example.com")
        self.assertIsNone(result)


_PATREON_ACTIVE = {"is_active": True, "pledge_cents": None, "last_charge_date": None, "last_charge_status": None, "patron_since": None, "lifetime_cents": None}
_PATREON_INACTIVE = {"is_active": False, "pledge_cents": None, "last_charge_date": None, "last_charge_status": None, "patron_since": None, "lifetime_cents": None}


class PatreonValidationIntegrationTest(TestCase):
    """Integration tests verifying Patreon validation is triggered during rental submission."""

    def setUp(self):
        from wagtail.models import Site

        from blowcomotion.member_auth import create_member_user
        self.instrument = make_instrument("Trumpet")
        self.li = make_library_instrument(self.instrument, status=LibraryInstrument.STATUS_AVAILABLE)
        self.member = make_member()
        self.user = create_member_user(self.member)
        self.user.set_password("Pass123!")
        self.user.save()
        self.client.login(username="sam@example.com", password="Pass123!")
        self.site_settings = SiteSettings.for_site(Site.objects.get(is_default_site=True))
        self.site_settings.instrument_rental_policy = "You must return the instrument."
        self.site_settings.save()
        patcher_captcha = patch(
            "blowcomotion.member_views._validate_recaptcha", return_value=(True, None)
        )
        patcher_captcha.start()
        self.addCleanup(patcher_captcha.stop)

    def _post(self):
        from django.urls import reverse

        return self.client.post(reverse("member-instrument-rental"), {
            "instrument": self.instrument.pk,
            "policy_acknowledged": True,
        })

    @patch("blowcomotion.member_views.check_patreon_membership", return_value=_PATREON_ACTIVE)
    def test_active_patron_sets_patreon_validated_true(self, mock_check):
        self._post()
        sub = InstrumentRentalRequestSubmission.objects.first()
        self.assertTrue(sub.patreon_validated)
        mock_check.assert_called_once_with(self.member.email)

    @patch("blowcomotion.member_views.check_patreon_membership", return_value=_PATREON_INACTIVE)
    def test_inactive_patron_sets_patreon_validated_false(self, mock_check):
        self._post()
        sub = InstrumentRentalRequestSubmission.objects.first()
        self.assertFalse(sub.patreon_validated)
        self.assertIsNotNone(sub.patreon_validated)
        mock_check.assert_called_once_with(self.member.email)

    @patch("blowcomotion.member_views.check_patreon_membership", return_value=None)
    def test_unconfigured_patreon_sets_patreon_validated_none(self, mock_check):
        self._post()
        sub = InstrumentRentalRequestSubmission.objects.first()
        self.assertIsNone(sub.patreon_validated)
        mock_check.assert_called_once_with(self.member.email)

    @patch("blowcomotion.member_views._MemberEmail")
    @patch("blowcomotion.member_views.check_patreon_membership", return_value=_PATREON_INACTIVE)
    def test_inactive_patron_manager_email_mentions_patreon(self, mock_check, mock_email_cls):
        mock_email_cls.return_value.send.return_value = None
        self.site_settings.instrument_rental_notification_recipients = "mgr@example.com"
        self.site_settings.save()
        self._post()
        call_kwargs = mock_email_cls.call_args_list[0][1]
        self.assertIn("NOT FOUND or INACTIVE", call_kwargs["body"])

    @patch("blowcomotion.member_views._MemberEmail")
    @patch("blowcomotion.member_views.check_patreon_membership", return_value=_PATREON_ACTIVE)
    def test_active_patron_manager_email_confirms_active(self, mock_check, mock_email_cls):
        mock_email_cls.return_value.send.return_value = None
        self.site_settings.instrument_rental_notification_recipients = "mgr@example.com"
        self.site_settings.save()
        self._post()
        call_kwargs = mock_email_cls.call_args_list[0][1]
        self.assertIn("ACTIVE PATRON", call_kwargs["body"])

    @patch("blowcomotion.member_views._MemberEmail")
    @patch("blowcomotion.member_views.check_patreon_membership", return_value=None)
    def test_unconfigured_patreon_manager_email_says_not_checked(self, mock_check, mock_email_cls):
        mock_email_cls.return_value.send.return_value = None
        self.site_settings.instrument_rental_notification_recipients = "mgr@example.com"
        self.site_settings.save()
        self._post()
        call_kwargs = mock_email_cls.call_args_list[0][1]
        self.assertIn("not checked", call_kwargs["body"])

    @patch("blowcomotion.member_views.check_patreon_membership", return_value=_PATREON_ACTIVE)
    def test_submission_created_even_if_patreon_active(self, mock_check):
        self._post()
        self.assertEqual(InstrumentRentalRequestSubmission.objects.count(), 1)
