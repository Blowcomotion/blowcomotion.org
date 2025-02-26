from wagtail import hooks
from wagtail.snippets.models import register_snippet

from .chooser_viewsets import (event_chooser_viewset,
                               instrument_chooser_viewset,
                               member_chooser_viewset, section_chooser_viewset,
                               song_chooser_viewset)
from .snippet_viewsets import BandViewSetGroup

register_snippet(BandViewSetGroup)

@hooks.register('register_admin_viewset')
def register_viewset():
    return member_chooser_viewset, instrument_chooser_viewset, section_chooser_viewset, song_chooser_viewset, event_chooser_viewset