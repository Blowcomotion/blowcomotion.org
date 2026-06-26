from wagtail.models import Site

from django.db.models import Count, Q
from django.test import TestCase

from blowcomotion.member_forms import InstrumentRentalRequestForm
from blowcomotion.models import (
    Instrument,
    InstrumentRentalRequestSubmission,
    LibraryInstrument,
    Member,
    SiteSettings,
)


def make_instrument(name="Trumpet"):
    return Instrument.objects.create(name=name)


def make_library_instrument(instrument, status=LibraryInstrument.STATUS_AVAILABLE, serial="SN001"):
    return LibraryInstrument.objects.create(
        instrument=instrument, serial_number=serial, status=status
    )


def make_member(**kwargs):
    defaults = dict(first_name="Sam", last_name="Player", email="sam@example.com",
                    phone="512-555-0100", address="123 Main St")
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


from unittest.mock import patch

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
