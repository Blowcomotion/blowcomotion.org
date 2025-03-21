# Generated by Django 5.1.6 on 2025-03-21 04:02

import blowcomotion.blocks
import wagtail.fields
from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("blowcomotion", "0032_alter_blankcanvaspage_body"),
    ]

    operations = [
        migrations.AddField(
            model_name="sitesettings",
            name="header_menus",
            field=wagtail.fields.StreamField(
                [("menu_item", 3)],
                blank=True,
                block_lookup={
                    0: ("wagtail.blocks.PageChooserBlock", (), {}),
                    1: ("wagtail.blocks.CharBlock", (), {"required": False}),
                    2: (
                        "wagtail.blocks.ListBlock",
                        (blowcomotion.blocks.MenuItemBlock,),
                        {"required": False},
                    ),
                    3: (
                        "wagtail.blocks.StructBlock",
                        [[("page", 0), ("label", 1), ("children", 2)]],
                        {},
                    ),
                },
                null=True,
            ),
        ),
        migrations.AlterField(
            model_name="blankcanvaspage",
            name="body",
            field=wagtail.fields.StreamField(
                [("column_layout", 8), ("hero", 10), ("rich_text", 2), ("events", 18)],
                blank=True,
                block_lookup={
                    0: ("wagtail.blocks.RichTextBlock", (), {}),
                    1: (
                        "wagtail.blocks.ChoiceBlock",
                        [],
                        {
                            "choices": [
                                ("left", "Left"),
                                ("center", "Center"),
                                ("right", "Right"),
                            ]
                        },
                    ),
                    2: (
                        "wagtail.blocks.StructBlock",
                        [[("rich_text", 0), ("align", 1)]],
                        {},
                    ),
                    3: (
                        "wagtail.images.blocks.ImageChooserBlock",
                        (),
                        {"template": "blocks/image_block.html"},
                    ),
                    4: (
                        "wagtail.blocks.StreamBlock",
                        [[("rich_text", 2), ("image", 3)]],
                        {"required": False},
                    ),
                    5: (
                        "wagtail.blocks.StructBlock",
                        [[("left_column", 4), ("right_column", 4)]],
                        {},
                    ),
                    6: (
                        "wagtail.blocks.StructBlock",
                        [
                            [
                                ("left_column", 4),
                                ("middle_column", 4),
                                ("right_column", 4),
                            ]
                        ],
                        {},
                    ),
                    7: (
                        "wagtail.blocks.StructBlock",
                        [
                            [
                                ("left_column", 4),
                                ("middle_column", 4),
                                ("right_column", 4),
                                ("middle_left_column", 4),
                                ("middle_right_column", 4),
                            ]
                        ],
                        {},
                    ),
                    8: (
                        "wagtail.blocks.StreamBlock",
                        [[("two_column", 5), ("three_column", 6), ("four_column", 7)]],
                        {},
                    ),
                    9: ("wagtail.images.blocks.ImageChooserBlock", (), {}),
                    10: ("wagtail.blocks.StructBlock", [[("image", 9)]], {}),
                    11: ("wagtail.blocks.CharBlock", (), {}),
                    12: ("blowcomotion.chooser_blocks.GigoGigChooserBlock", (), {}),
                    13: (
                        "wagtail.images.blocks.ImageChooserBlock",
                        (),
                        {"required": False},
                    ),
                    14: (
                        "wagtail.blocks.StructBlock",
                        [[("details", 12), ("event_scroller_image", 13)]],
                        {},
                    ),
                    15: ("wagtail.blocks.ListBlock", (14,), {}),
                    16: ("blowcomotion.chooser_blocks.EventChooserBlock", (), {}),
                    17: (
                        "wagtail.blocks.ListBlock",
                        (16,),
                        {
                            "help_text": "Events that are not associated with Gig-o-Matic"
                        },
                    ),
                    18: (
                        "wagtail.blocks.StructBlock",
                        [[("scroller_title", 11), ("gigo_gigs", 15), ("events", 17)]],
                        {},
                    ),
                },
                null=True,
            ),
        ),
    ]
