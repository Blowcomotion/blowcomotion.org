# Generated by Django 5.1.6 on 2025-04-07 00:34

import wagtail.fields
from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("blowcomotion", "0044_alter_blankcanvaspage_body"),
    ]

    operations = [
        migrations.AlterField(
            model_name="blankcanvaspage",
            name="body",
            field=wagtail.fields.StreamField(
                [
                    ("column_layout", 8),
                    ("countdown", 16),
                    ("events", 23),
                    ("full_width_image", 25),
                    ("hero", 28),
                    ("multi_image_banner", 30),
                    ("quoted_image", 32),
                    ("rich_text", 2),
                    ("spacer", 33),
                    ("upcoming_events", 35),
                ],
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
                    9: (
                        "wagtail.images.blocks.ImageChooserBlock",
                        (),
                        {"required": False},
                    ),
                    10: (
                        "wagtail.blocks.DateBlock",
                        (),
                        {"help_text": "Enter the date for the countdown."},
                    ),
                    11: (
                        "wagtail.blocks.CharBlock",
                        (),
                        {
                            "help_text": "Enter the top line text for the countdown.",
                            "required": False,
                        },
                    ),
                    12: (
                        "wagtail.blocks.CharBlock",
                        (),
                        {
                            "help_text": "Enter the sub line text for the countdown.",
                            "required": False,
                        },
                    ),
                    13: (
                        "wagtail.blocks.CharBlock",
                        (),
                        {
                            "help_text": "Enter the text for the button.",
                            "required": False,
                        },
                    ),
                    14: (
                        "wagtail.blocks.URLBlock",
                        (),
                        {
                            "help_text": "Enter the URL for the button.",
                            "required": False,
                        },
                    ),
                    15: (
                        "wagtail.blocks.ChoiceBlock",
                        [],
                        {
                            "choices": [("_self", "Same Tab"), ("_blank", "New Tab")],
                            "help_text": "Select the target for the button.",
                        },
                    ),
                    16: (
                        "wagtail.blocks.StructBlock",
                        [
                            [
                                ("background_image", 9),
                                ("countdown_date", 10),
                                ("head_line", 11),
                                ("sub_line", 12),
                                ("button_text", 13),
                                ("button_url", 14),
                                ("button_target", 15),
                            ]
                        ],
                        {},
                    ),
                    17: ("wagtail.blocks.CharBlock", (), {}),
                    18: ("blowcomotion.chooser_blocks.GigoGigChooserBlock", (), {}),
                    19: (
                        "wagtail.blocks.StructBlock",
                        [[("details", 18), ("event_scroller_image", 9)]],
                        {},
                    ),
                    20: ("wagtail.blocks.ListBlock", (19,), {}),
                    21: ("blowcomotion.chooser_blocks.EventChooserBlock", (), {}),
                    22: (
                        "wagtail.blocks.ListBlock",
                        (21,),
                        {
                            "help_text": "Events that are not associated with Gig-o-Matic"
                        },
                    ),
                    23: (
                        "wagtail.blocks.StructBlock",
                        [[("scroller_title", 17), ("gigo_gigs", 20), ("events", 22)]],
                        {},
                    ),
                    24: ("wagtail.images.blocks.ImageChooserBlock", (), {}),
                    25: ("wagtail.blocks.StructBlock", [[("image", 24)]], {}),
                    26: ("wagtail.blocks.CharBlock", (), {"required": False}),
                    27: ("wagtail.blocks.URLBlock", (), {"required": False}),
                    28: (
                        "wagtail.blocks.StructBlock",
                        [
                            [
                                ("image", 24),
                                ("top_line", 26),
                                ("middle_line", 26),
                                ("bottom_line", 26),
                                ("youtube_url", 27),
                            ]
                        ],
                        {},
                    ),
                    29: (
                        "wagtail.blocks.ListBlock",
                        (24,),
                        {
                            "help_text": "Select images to display in the banner.",
                            "max_num": 7,
                            "min_num": 7,
                        },
                    ),
                    30: ("wagtail.blocks.StructBlock", [[("images", 29)]], {}),
                    31: ("wagtail.blocks.TextBlock", (), {"required": False}),
                    32: (
                        "wagtail.blocks.StructBlock",
                        [
                            [
                                ("image", 24),
                                ("header", 26),
                                ("subheader", 31),
                                ("author", 26),
                            ]
                        ],
                        {},
                    ),
                    33: ("blowcomotion.blocks.SpacerBlock", (), {}),
                    34: (
                        "wagtail.blocks.CharBlock",
                        (),
                        {
                            "help_text": "Enter the headline for the upcoming public gigs.",
                            "required": False,
                        },
                    ),
                    35: ("wagtail.blocks.StructBlock", [[("headline", 34)]], {}),
                },
                null=True,
            ),
        ),
    ]
