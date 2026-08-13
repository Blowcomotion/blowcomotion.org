from wagtail.images.formats import get_image_format

from django.test import TestCase

import blowcomotion.wagtail_hooks  # noqa: F401  ensures format overrides are registered


class RichTextImageFormatTests(TestCase):
    def test_default_image_formats_include_img_fluid(self):
        for name in ("fullwidth", "left", "right"):
            classname = get_image_format(name).classname
            self.assertIn("img-fluid", classname.split())
