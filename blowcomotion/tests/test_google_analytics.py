"""
Unit tests for Google Analytics (GA4) integration.
"""

from django.template import Context, Template
from django.template.loader import render_to_string
from django.test import RequestFactory, TestCase, override_settings

from blowcomotion.templatetags.blowco_tags import get_google_analytics_id


class GetGoogleAnalyticsIdTagTests(TestCase):
    """Test cases for the get_google_analytics_id template tag."""

    @override_settings(GOOGLE_ANALYTICS_ID=None)
    def test_returns_empty_string_when_unset(self):
        self.assertEqual(get_google_analytics_id(), '')

    @override_settings(GOOGLE_ANALYTICS_ID='')
    def test_returns_empty_string_when_blank(self):
        self.assertEqual(get_google_analytics_id(), '')

    @override_settings(GOOGLE_ANALYTICS_ID='G-TESTID123')
    def test_returns_id_when_configured(self):
        self.assertEqual(get_google_analytics_id(), 'G-TESTID123')


class GoogleAnalyticsSnippetRenderingTests(TestCase):
    """Test cases for conditional rendering of the gtag.js snippet."""

    def _render(self):
        template = Template(
            "{% load blowco_tags %}"
            "{% get_google_analytics_id as google_analytics_id %}"
            "{% if google_analytics_id %}"
            "<script async src=\"https://www.googletagmanager.com/gtag/js?id={{ google_analytics_id|urlencode }}\"></script>"
            "gtag('config', '{{ google_analytics_id|escapejs }}');"
            "{% endif %}"
        )
        return template.render(Context({}))

    @override_settings(GOOGLE_ANALYTICS_ID=None)
    def test_snippet_omitted_when_unset(self):
        rendered = self._render()
        self.assertNotIn('googletagmanager.com', rendered)
        self.assertNotIn('gtag(', rendered)

    @override_settings(GOOGLE_ANALYTICS_ID='G-TESTID123')
    def test_snippet_included_when_configured(self):
        rendered = self._render()
        self.assertIn('googletagmanager.com/gtag/js?id=G-TESTID123', rendered)
        self.assertIn("gtag('config',", rendered)
        self.assertIn('TESTID123', rendered)


class HomePageRendersAnalyticsSnippetTests(TestCase):
    """Integration tests confirming the base template renders (or omits) the snippet."""

    @override_settings(GOOGLE_ANALYTICS_ID=None)
    def test_404_page_omits_snippet_when_unset(self):
        response = self.client.get('/this-page-does-not-exist/')
        self.assertNotContains(response, 'googletagmanager.com', status_code=404)

    @override_settings(GOOGLE_ANALYTICS_ID='G-TESTID123')
    def test_404_page_includes_snippet_when_configured(self):
        response = self.client.get('/this-page-does-not-exist/')
        self.assertContains(response, 'googletagmanager.com/gtag/js?id=G-TESTID123', status_code=404)


class GoogleAnalyticsPreviewSuppressionTests(TestCase):
    """
    Wagtail previews (split-panel and full-tab) are served through
    PreviewableMixin.make_preview_request, which sets request.is_preview = True
    on an otherwise front-end request. The snippet must not fire in that case,
    since the rendered HTML is loaded in a real browser and would otherwise
    send analytics events for editor previews.
    """

    def _render_head(self, is_preview):
        request = RequestFactory().get('/')
        request.is_preview = is_preview
        return render_to_string('head.html', {'request': request}, request=request)

    @override_settings(GOOGLE_ANALYTICS_ID='G-TESTID123')
    def test_snippet_omitted_during_preview(self):
        rendered = self._render_head(is_preview=True)
        self.assertNotIn('googletagmanager.com', rendered)

    @override_settings(GOOGLE_ANALYTICS_ID='G-TESTID123')
    def test_snippet_included_outside_preview(self):
        rendered = self._render_head(is_preview=False)
        self.assertIn('googletagmanager.com/gtag/js?id=G-TESTID123', rendered)
