# Generated by Django 5.1.6 on 2025-02-26 05:06

import wagtail.fields
from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('blowcomotion', '0027_rename_eventsetlist_eventsetlistsong_event_time_and_more'),
    ]

    operations = [
        migrations.AlterField(
            model_name='blankcanvaspage',
            name='body',
            field=wagtail.fields.StreamField([('hero', 1), ('rich_text', 2), ('events', 5)], blank=True, block_lookup={0: ('wagtail.images.blocks.ImageChooserBlock', (), {}), 1: ('wagtail.blocks.StructBlock', [[('image', 0)]], {}), 2: ('wagtail.blocks.RichTextBlock', (), {}), 3: ('blowcomotion.chooser_blocks.EventChooserBlock', (), {}), 4: ('wagtail.blocks.ListBlock', (3,), {}), 5: ('wagtail.blocks.StructBlock', [[('events', 4)]], {})}, null=True),
        ),
    ]
