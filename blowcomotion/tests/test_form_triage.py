from datetime import date, time
from types import SimpleNamespace
from unittest.mock import patch

from django.core import mail
from django.test import TestCase, override_settings

from blowcomotion.models import CachedGig
from blowcomotion.triage import Triage, triage_and_email, triage_in_background


def _fake_response(**overrides):
    fields = dict(
        likely_spam=False, spam_reason="", summary="Wants a band for a wedding.",
        event_date=None, venue=None, budget=None, event_type=None,
        suggested_reply="Hi Pat, thanks for reaching out! - Blowcomotion",
    )
    fields.update(overrides)
    return SimpleNamespace(stop_reason="end_turn", parsed_output=Triage(**fields))


@override_settings(ANTHROPIC_API_KEY="test-key")
class FormTriageTests(TestCase):
    def _run(self, response, form_data):
        with patch("blowcomotion.triage.anthropic.Anthropic") as client_cls:
            client_cls.return_value.messages.parse.return_value = response
            triage_and_email("booking_form", form_data, ["admin@example.com"])

    def test_booking_lists_gig_conflict_and_goes_to_admins_only(self):
        CachedGig.objects.create(
            gig_id=1, title="Pride Parade", date=date(2026, 12, 5), time=time(14, 0),
            gig_status="confirmed", band="Blowcomotion",
        )
        CachedGig.objects.create(
            gig_id=2, title="Old Gig", date=date(2026, 12, 5), gig_status="cancelled", band="Blowcomotion",
        )
        # Form date field wins over the model's guess; crafted newline in name is collapsed.
        self._run(
            _fake_response(event_date="2026-12-06", venue="Lake Merritt", budget="$800"),
            {"name": "Pat\r\nBcc: x@y.com", "email": "pat@example.com", "event_date": "2026-12-05",
             "event_details": "Wedding Saturday at Lake Merritt"},
        )
        self.assertEqual(len(mail.outbox), 1)
        msg = mail.outbox[0]
        self.assertNotIn("pat@example.com", msg.to)
        self.assertIn("admin@example.com", msg.to)
        self.assertEqual(msg.subject, "Triage: Booking Form from Pat Bcc: x@y.com")
        self.assertIn("Event date: 2026-12-05", msg.body)
        self.assertIn("Gigs already on 2026-12-05:", msg.body)
        self.assertIn("Pride Parade (Blowcomotion, confirmed, 2:00 PM)", msg.body)
        self.assertNotIn("Old Gig", msg.body)
        self.assertIn("Venue: Lake Merritt", msg.body)
        self.assertIn("Hi Pat, thanks", msg.body)

    def test_spam_flagged_in_subject(self):
        self._run(
            _fake_response(likely_spam=True, spam_reason="SEO pitch.", suggested_reply=""),
            {"name": "Bot", "email": "bot@example.com", "event_details": "Rank #1 on Google"},
        )
        self.assertTrue(mail.outbox[0].subject.startswith("[Likely spam] "))
        self.assertIn("YES - SEO pitch.", mail.outbox[0].body)

    def test_refusal_or_api_error_sends_nothing(self):
        self._run(SimpleNamespace(stop_reason="refusal", parsed_output=None), {"name": "X"})
        with patch("blowcomotion.triage.anthropic.Anthropic", side_effect=RuntimeError("down")):
            triage_and_email("contact_form", {"name": "X"}, ["admin@example.com"])
        self.assertEqual(mail.outbox, [])

    def test_background_skipped_without_key_or_under_test_email_backend(self):
        with patch("blowcomotion.triage.threading.Thread") as thread:
            with override_settings(ANTHROPIC_API_KEY=None):
                triage_in_background("contact_form", {"name": "X"}, ["admin@example.com"])
            # Test runner uses the locmem backend; real API must never be called from tests.
            triage_in_background("contact_form", {"name": "X"}, ["admin@example.com"])
        thread.assert_not_called()
