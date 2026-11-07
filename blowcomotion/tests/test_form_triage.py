from datetime import date, time
from types import SimpleNamespace
from unittest.mock import patch

from wagtail.models import Site

from django.core import mail
from django.test import TestCase, override_settings
from django.urls import reverse

from blowcomotion.models import BlankCanvasPage, CachedGig, SiteSettings
from blowcomotion.triage import (
    Triage,
    _reference_pages,
    build_admin_email,
    send_admin_email,
)

ADMINS = ["admin@example.com"]


def _fake_response(**overrides):
    fields = dict(
        likely_spam=False, spam_reason="", summary="Wants a band for a wedding.",
        event_date=None, venue=None, budget=None, event_type=None,
        suggested_reply="Hi Pat, thanks for reaching out! - Blowcomotion",
    )
    fields.update(overrides)
    return SimpleNamespace(stop_reason="end_turn", parsed_output=Triage(**fields))


@override_settings(ANTHROPIC_API_KEY="test-key")
class BuildAdminEmailTests(TestCase):
    def _build(self, response, form_data):
        with patch("blowcomotion.triage.anthropic.Anthropic") as client_cls:
            client_cls.return_value.messages.parse.return_value = response
            return build_admin_email("Booking Form Submission", "Original body", ADMINS, "booking_form", form_data)

    def test_triage_appended_with_gig_conflict_and_draft_reply(self):
        CachedGig.objects.create(
            gig_id=1, title="Pride Parade", date=date(2026, 12, 5), time=time(14, 0),
            gig_status="confirmed", band="Blowcomotion",
        )
        CachedGig.objects.create(
            gig_id=2, title="Old Gig", date=date(2026, 12, 5), gig_status="cancelled", band="Blowcomotion",
        )
        # The form's date field wins over the model's guess.
        msg = self._build(
            _fake_response(event_date="2026-12-06", venue="Lake Merritt", budget="$800"),
            {"name": "Pat", "email": "pat@example.com", "event_date": "2026-12-05",
             "event_details": "Wedding Saturday at Lake Merritt"},
        )
        self.assertEqual(msg.to, ADMINS)
        self.assertEqual(msg.reply_to, ["pat@example.com"])
        self.assertEqual(msg.subject, "Booking Form Submission")
        self.assertTrue(msg.body.startswith("Original body\n\n----- AI triage"))
        self.assertIn("Event date: 2026-12-05", msg.body)
        self.assertIn("Gigs already on 2026-12-05:", msg.body)
        self.assertIn("Pride Parade (Blowcomotion, confirmed, 2:00 PM)", msg.body)
        self.assertNotIn("Old Gig", msg.body)
        self.assertIn("Venue: Lake Merritt", msg.body)
        self.assertIn("Suggested reply (edit before sending):\n\nHi Pat, thanks", msg.body)

    def test_spam_flagged_in_subject(self):
        msg = self._build(
            _fake_response(likely_spam=True, spam_reason="SEO pitch.", suggested_reply=""),
            {"name": "Bot", "event_details": "Rank #1 on Google"},
        )
        self.assertEqual(msg.subject, "[Likely spam] Booking Form Submission")
        self.assertIn("YES - SEO pitch.", msg.body)

    def test_email_still_built_on_refusal_or_api_error(self):
        refused = self._build(SimpleNamespace(stop_reason="refusal", parsed_output=None), {"name": "X"})
        with patch("blowcomotion.triage.anthropic.Anthropic", side_effect=RuntimeError("bad key")):
            errored = build_admin_email("Subj", "Original body", ADMINS, "contact_form", {"name": "X"})
        with patch("blowcomotion.triage._conflicting_gigs", side_effect=RuntimeError("db down")):
            gig_error = self._build(_fake_response(), {"name": "X"})
        for msg in (refused, errored, gig_error):
            self.assertEqual(msg.body, "Original body\n\n(AI triage was unavailable for this submission.)")

    def test_sends_plain_email_without_thread_under_test_backend(self):
        with patch("blowcomotion.triage.threading.Thread") as thread:
            send_admin_email("Subj", "Original body", ADMINS, "contact_form", {"name": "X"})
        thread.assert_not_called()
        self.assertEqual(mail.outbox[0].body, "Original body")


class ProcessFormEmailSplitTests(TestCase):
    @override_settings(DEBUG=True)
    def test_admins_and_submitter_get_separate_emails(self):
        site_settings = SiteSettings.for_site(Site.objects.get(is_default_site=True))
        site_settings.booking_form_email_recipients = "a@example.com, b@example.com"
        site_settings.save()
        self.client.post(reverse("process-form"), {
            "form_type": "booking_form", "name": "Pat", "email": "pat@example.com",
            "event_details": "Wedding",
        })
        recipients = sorted(tuple(m.to) for m in mail.outbox)
        self.assertEqual(recipients, [("a@example.com", "b@example.com"), ("pat@example.com",)])
        admin_copy = next(m for m in mail.outbox if m.to != ["pat@example.com"])
        self.assertEqual(admin_copy.reply_to, ["pat@example.com"])
        submitter_copy = next(m for m in mail.outbox if m.to == ["pat@example.com"])
        self.assertNotIn("AI triage", submitter_copy.body)


@override_settings(ANTHROPIC_API_KEY="test-key")
class ReferencePagesTests(TestCase):
    def test_join_triage_gets_faq_and_join_pages_only(self):
        root = Site.objects.get(is_default_site=True).root_page
        for slug, text in [("faqs", "Rehearsals are Tuesdays."), ("join", "Loaner horns available."),
                           ("booking", "Booking info.")]:
            # A form block exercises {% csrf_token %} rendering outside a request.
            body = [("rich_text", {"rich_text": f"<p>{text}</p>", "align": "left"}), ("join_band_form", {})]
            root.add_child(instance=BlankCanvasPage(title=slug, slug=slug, body=body))
        with patch("blowcomotion.triage.anthropic.Anthropic") as client_cls:
            client_cls.return_value.messages.parse.return_value = _fake_response()
            build_admin_email("Subj", "Body", ADMINS, "join_band_form", {"name": "Sam"})
        system = client_cls.return_value.messages.parse.call_args.kwargs["system"]
        self.assertIn("Rehearsals are Tuesdays.", system)
        self.assertIn("Loaner horns available.", system)
        self.assertNotIn("Booking info.", system)

    def test_page_that_fails_to_render_is_skipped(self):
        root = Site.objects.get(is_default_site=True).root_page
        root.add_child(instance=BlankCanvasPage(
            title="faqs", slug="faqs", body=[("rich_text", {"rich_text": "<p>FAQ text.</p>", "align": "left"})]))
        with patch("wagtail.fields.StreamValue.render_as_block", side_effect=RuntimeError("bad block")):
            self.assertEqual(_reference_pages("contact_form"), "<reference_pages>\n\n</reference_pages>")
