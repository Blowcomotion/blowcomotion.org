from wagtail.models import Site

from django.core import mail
from django.test import TestCase, override_settings
from django.urls import reverse

from blowcomotion.models import Member, SiteSettings, TShirtRequestSubmission
from members.auth import create_member_user


@override_settings(DEBUG=True, RECAPTCHA_PUBLIC_KEY=None, RECAPTCHA_PRIVATE_KEY=None)
class TShirtRequestFormTests(TestCase):
    def setUp(self):
        site_settings = SiteSettings.for_site(Site.objects.get(is_default_site=True))
        site_settings.tshirt_request_email_recipients = "merch@example.com"
        site_settings.save()
        self.member = Member.objects.create(first_name="Robin", last_name="Player", email="robin@example.com")
        self.user = create_member_user(self.member)

    def post(self, **data):
        return self.client.post(reverse("process-form"), {"form_type": "tshirt_request_form", **data})

    def test_anonymous_is_rejected(self):
        response = self.post(shirt_size="M")
        self.assertContains(response, "log in")
        self.assertFalse(TShirtRequestSubmission.objects.exists())

    def test_member_request_uses_member_identity_not_post(self):
        self.client.force_login(self.user)
        response = self.post(shirt_size="L", name="Mallory", email="mallory@example.com")
        self.assertContains(response, "T-shirt request submitted")
        req = TShirtRequestSubmission.objects.get()
        self.assertEqual((req.member, req.name, req.email), (self.member, self.member.full_name, "robin@example.com"))
        self.assertFalse(req.paid or req.picked_up)
        self.assertEqual(sorted(m.to[0] for m in mail.outbox), ["merch@example.com", "robin@example.com"])

    def test_invalid_size_is_rejected(self):
        self.client.force_login(self.user)
        self.post(shirt_size="XXXXL")
        self.assertFalse(TShirtRequestSubmission.objects.exists())

    def test_saved_without_recipients(self):
        SiteSettings.objects.update(tshirt_request_email_recipients="")
        self.client.force_login(self.user)
        self.post(shirt_size="S")
        self.assertTrue(TShirtRequestSubmission.objects.filter(shirt_size="S").exists())
        self.assertEqual([m.to[0] for m in mail.outbox], ["robin@example.com"])
