from wagtail.models import Page, Site

from django.test import TestCase

from blowcomotion.blocks import PageInfoBlock
from blowcomotion.models import BlankCanvasPage


class PageNavBlocksTests(TestCase):
    def setUp(self):
        root = Site.objects.get(is_default_site=True).root_page
        self.index = root.add_child(instance=BlankCanvasPage(
            title="Blowco Wiki", slug="wiki-test",
            body=[("child_pages", {"heading": "Wiki Index"})],
        ))
        self.child = self.index.add_child(instance=BlankCanvasPage(
            title="Trumpet 101", slug="trumpet-101",
            body=[
                ("breadcrumbs", {"start_page": self.index}),
                ("page_info", {"show_title": True, "show_dates": True, "authors": []}),
            ],
        ))
        self.child.save_revision().publish()
        self.draft = self.index.add_child(instance=BlankCanvasPage(title="Unpublished", slug="draft", live=False))

    def test_breadcrumbs_start_at_start_page(self):
        html = self.client.get(self.child.url).content.decode()
        self.assertIn(f'<a href="{self.index.url}">Blowco Wiki</a>', html)
        self.assertIn('aria-current="page">Trumpet 101</li>', html)
        home = Page.objects.get(pk=self.index.get_parent().pk)
        self.assertNotIn(f">{home.title}</a></li>", html)
        self.assertIn("<h1>Trumpet 101</h1>", html)
        self.assertIn("Published on:", html)

    def test_child_pages_lists_live_children_only(self):
        html = self.client.get(self.index.url).content.decode()
        self.assertIn("<h2>Wiki Index</h2>", html)
        self.assertIn(">Trumpet 101</a>", html)
        self.assertNotIn("Unpublished", html)

    def test_page_info_skips_deleted_authors(self):
        block = PageInfoBlock()
        value = block.to_python({"show_title": False, "show_dates": False, "authors": [999999]})
        html = block.render(value, context={"page": self.child})
        self.assertNotIn("None", html)
        self.assertNotIn("Page written by", html)
