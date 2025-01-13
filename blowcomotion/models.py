from django.db import models
from wagtail.models import Page
from wagtail.admin.panels import FieldPanel
from wagtail.fields import RichTextField

class BasePage(Page):
    class Meta:
        abstract = True

class BlankCanvasPage(BasePage):
    template = 'pages/blank_canvas_page.html'
    body = RichTextField(blank=True)

    content_panels = Page.content_panels + [
        FieldPanel("body"),
    ]

