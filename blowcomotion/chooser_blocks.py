from blowcomotion.chooser_viewsets import (event_chooser_viewset,
                                           gigo_gig_chooser_viewset)

EventChooserBlock = event_chooser_viewset.get_block_class(
    name="EventChooserBlock", module_path="blowcomotion.chooser_blocks"
)
GigoGigChooserBlock = gigo_gig_chooser_viewset.get_block_class(
    name="GigoGigChooserBlock", module_path="blowcomotion.chooser_blocks"
)
