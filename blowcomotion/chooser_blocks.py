from blowcomotion.wagtail_hooks import event_chooser_viewset

EventChooserBlock = event_chooser_viewset.get_block_class(name="EventChooserBlock", module_path="blowcomotion.chooser_blocks")