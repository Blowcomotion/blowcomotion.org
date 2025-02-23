from django.db import models
from wagtail.contrib.settings.models import BaseSiteSetting, register_setting
from wagtail import blocks
from wagtail.fields import StreamField
from wagtail.images.models import AbstractImage, AbstractRendition, Image
from wagtail.models import Page

from blowcomotion import blocks as blowcomotion_blocks


@register_setting
class SiteSettings(BaseSiteSetting):
    logo = models.ForeignKey(
        "blowcomotion.CustomImage",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
    )
    facebook = models.URLField(blank=True, null=True)


class CustomImage(AbstractImage):
    # Add any extra fields to image here

    # To add a caption field:
    caption = models.CharField(max_length=255, blank=True)

    admin_form_fields = Image.admin_form_fields + (
        # Then add the field names here to make them appear in the form:
        'caption',
    )

    @property
    def default_alt_text(self):
        # Force editors to add specific alt text if description is empty.
        # Do not use image title which is typically derived from file name.
        return getattr(self, "description", None)
    

class CustomRendition(AbstractRendition):
    image = models.ForeignKey(CustomImage, on_delete=models.CASCADE, related_name='renditions')

    class Meta:
        unique_together = (
            ('image', 'filter_spec', 'focal_point_key'),
        )


class BasePage(Page):
    class Meta:
        abstract = True

class BlankCanvasPage(BasePage):
    template = 'pages/blank_canvas_page.html'
    body = StreamField([
        ("hero", blowcomotion_blocks.HeroBlock()),
        ("rich_text", blocks.RichTextBlock()),
    ], block_counts={
        "hero": {"max_num": 1},
    }, blank=True, null=True)

    content_panels = Page.content_panels + [
        "body",
    ]

    def get_context(self, request):
        context = super().get_context(request)
        context["hero_header"] = any(
            block.block_type == "hero" for block in self.body
        )
        return context

