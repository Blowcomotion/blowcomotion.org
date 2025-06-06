# Generated by Django 5.1.6 on 2025-05-26 19:48

import wagtail.fields
from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("blowcomotion", "0058_song_recording_alter_blankcanvaspage_body"),
    ]

    operations = [
        migrations.AlterField(
            model_name="blankcanvaspage",
            name="body",
            field=wagtail.fields.StreamField(
                [
                    ("accordion_list", 4),
                    ("button", 10),
                    ("column_layout", 29),
                    ("contact_form", 17),
                    ("countdown", 34),
                    ("events", 41),
                    ("full_width_image", 43),
                    ("hero", 45),
                    ("horizontal_rule", 13),
                    ("jukebox", 51),
                    ("multi_image_banner", 53),
                    ("paypal_donate_button", 19),
                    ("quoted_image", 55),
                    ("rich_text", 22),
                    ("adjustable_spacer", 12),
                    ("spacer", 23),
                    ("upcoming_events", 57),
                    ("venmo_donate_button", 24),
                ],
                blank=True,
                block_lookup={
                    0: ("wagtail.blocks.CharBlock", (), {"required": False}),
                    1: ("wagtail.blocks.RichTextBlock", (), {"required": False}),
                    2: (
                        "wagtail.blocks.StructBlock",
                        [[("title", 0), ("content", 1)]],
                        {},
                    ),
                    3: ("wagtail.blocks.ListBlock", (2,), {}),
                    4: (
                        "wagtail.blocks.StructBlock",
                        [[("title", 0), ("content", 3)]],
                        {},
                    ),
                    5: (
                        "wagtail.blocks.CharBlock",
                        (),
                        {
                            "help_text": "Enter the text for the button.",
                            "required": False,
                        },
                    ),
                    6: (
                        "wagtail.blocks.URLBlock",
                        (),
                        {
                            "help_text": "Enter the URL for the button.",
                            "required": False,
                        },
                    ),
                    7: (
                        "wagtail.blocks.ChoiceBlock",
                        [],
                        {
                            "choices": [("_self", "Same Tab"), ("_blank", "New Tab")],
                            "help_text": "Select the target for the button.",
                        },
                    ),
                    8: (
                        "wagtail.blocks.ChoiceBlock",
                        [],
                        {
                            "choices": [
                                ("left", "Left"),
                                ("center", "Center"),
                                ("right", "Right"),
                            ],
                            "help_text": "Select the alignment for the button.",
                        },
                    ),
                    9: (
                        "wagtail.blocks.ChoiceBlock",
                        [],
                        {
                            "choices": [("half", "Half"), ("full", "Full")],
                            "help_text": "Select the width for the button.",
                        },
                    ),
                    10: (
                        "wagtail.blocks.StructBlock",
                        [
                            [
                                ("button_text", 5),
                                ("button_url", 6),
                                ("button_target", 7),
                                ("button_alignment", 8),
                                ("button_width", 9),
                            ]
                        ],
                        {},
                    ),
                    11: (
                        "wagtail.blocks.IntegerBlock",
                        (),
                        {
                            "default": 20,
                            "help_text": "Enter the height of the spacer in pixels.",
                            "min_value": 1,
                        },
                    ),
                    12: ("wagtail.blocks.StructBlock", [[("height", 11)]], {}),
                    13: ("blowcomotion.blocks.HorizontalRuleBlock", (), {}),
                    14: (
                        "wagtail.blocks.CharBlock",
                        (),
                        {
                            "help_text": "Enter the title for the contact form.",
                            "required": False,
                        },
                    ),
                    15: (
                        "wagtail.blocks.RichTextBlock",
                        (),
                        {
                            "help_text": "Enter the description for the contact form.",
                            "required": False,
                        },
                    ),
                    16: (
                        "wagtail.blocks.BooleanBlock",
                        (),
                        {
                            "help_text": "Include an opt-in checkbox for the newsletter.",
                            "required": False,
                        },
                    ),
                    17: (
                        "wagtail.blocks.StructBlock",
                        [
                            [
                                ("title", 14),
                                ("description", 15),
                                ("button_text", 5),
                                ("newsletter_opt_in", 16),
                            ]
                        ],
                        {},
                    ),
                    18: (
                        "wagtail.images.blocks.ImageChooserBlock",
                        (),
                        {"template": "blocks/image_block.html"},
                    ),
                    19: ("wagtail.blocks.StructBlock", [[("alignment", 8)]], {}),
                    20: ("wagtail.blocks.RichTextBlock", (), {}),
                    21: (
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
                    22: (
                        "wagtail.blocks.StructBlock",
                        [[("rich_text", 20), ("align", 21)]],
                        {},
                    ),
                    23: ("blowcomotion.blocks.SpacerBlock", (), {}),
                    24: (
                        "wagtail.blocks.StructBlock",
                        [[("button_text", 5), ("alignment", 8)]],
                        {},
                    ),
                    25: (
                        "wagtail.blocks.StreamBlock",
                        [
                            [
                                ("accordion_list", 4),
                                ("button", 10),
                                ("contact_form", 17),
                                ("horizontal_rule", 13),
                                ("image", 18),
                                ("paypal_donate_button", 19),
                                ("rich_text", 22),
                                ("adjustable_spacer", 12),
                                ("spacer", 23),
                                ("venmo_donate_button", 24),
                            ]
                        ],
                        {"required": False},
                    ),
                    26: (
                        "wagtail.blocks.StructBlock",
                        [[("left_column", 25), ("right_column", 25)]],
                        {},
                    ),
                    27: (
                        "wagtail.blocks.StructBlock",
                        [
                            [
                                ("left_column", 25),
                                ("middle_column", 25),
                                ("right_column", 25),
                            ]
                        ],
                        {},
                    ),
                    28: (
                        "wagtail.blocks.StructBlock",
                        [
                            [
                                ("left_column", 25),
                                ("middle_column", 25),
                                ("right_column", 25),
                                ("middle_left_column", 25),
                                ("middle_right_column", 25),
                            ]
                        ],
                        {},
                    ),
                    29: (
                        "wagtail.blocks.StreamBlock",
                        [
                            [
                                ("spacer", 12),
                                ("horizontal_rule", 13),
                                ("two_column", 26),
                                ("three_column", 27),
                                ("four_column", 28),
                            ]
                        ],
                        {},
                    ),
                    30: (
                        "wagtail.images.blocks.ImageChooserBlock",
                        (),
                        {"required": False},
                    ),
                    31: (
                        "wagtail.blocks.DateBlock",
                        (),
                        {"help_text": "Enter the date for the countdown."},
                    ),
                    32: (
                        "wagtail.blocks.CharBlock",
                        (),
                        {
                            "help_text": "Enter the top line text for the countdown.",
                            "required": False,
                        },
                    ),
                    33: (
                        "wagtail.blocks.CharBlock",
                        (),
                        {
                            "help_text": "Enter the sub line text for the countdown.",
                            "required": False,
                        },
                    ),
                    34: (
                        "wagtail.blocks.StructBlock",
                        [
                            [
                                ("background_image", 30),
                                ("countdown_date", 31),
                                ("head_line", 32),
                                ("sub_line", 33),
                                ("button_text", 5),
                                ("button_url", 6),
                                ("button_target", 7),
                            ]
                        ],
                        {},
                    ),
                    35: ("wagtail.blocks.CharBlock", (), {}),
                    36: ("blowcomotion.chooser_blocks.GigoGigChooserBlock", (), {}),
                    37: (
                        "wagtail.blocks.StructBlock",
                        [[("details", 36), ("event_scroller_image", 30)]],
                        {},
                    ),
                    38: ("wagtail.blocks.ListBlock", (37,), {}),
                    39: ("blowcomotion.chooser_blocks.EventChooserBlock", (), {}),
                    40: (
                        "wagtail.blocks.ListBlock",
                        (39,),
                        {
                            "help_text": "Events that are not associated with Gig-o-Matic"
                        },
                    ),
                    41: (
                        "wagtail.blocks.StructBlock",
                        [[("scroller_title", 35), ("gigo_gigs", 38), ("events", 40)]],
                        {},
                    ),
                    42: ("wagtail.images.blocks.ImageChooserBlock", (), {}),
                    43: ("wagtail.blocks.StructBlock", [[("image", 42)]], {}),
                    44: ("wagtail.blocks.URLBlock", (), {"required": False}),
                    45: (
                        "wagtail.blocks.StructBlock",
                        [
                            [
                                ("image", 42),
                                ("top_line", 0),
                                ("middle_line", 0),
                                ("bottom_line", 0),
                                ("youtube_url", 44),
                            ]
                        ],
                        {},
                    ),
                    46: (
                        "wagtail.blocks.CharBlock",
                        (),
                        {
                            "help_text": "Enter the foreground title text for the jukebox.",
                            "required": False,
                        },
                    ),
                    47: (
                        "wagtail.blocks.CharBlock",
                        (),
                        {
                            "help_text": "Enter the background title text for the jukebox.",
                            "required": False,
                        },
                    ),
                    48: (
                        "wagtail.images.blocks.ImageChooserBlock",
                        (),
                        {
                            "help_text": "Select the image for the jukebox.",
                            "required": False,
                        },
                    ),
                    49: ("blowcomotion.chooser_blocks.SongChooserBlock", (), {}),
                    50: (
                        "wagtail.blocks.ListBlock",
                        (49,),
                        {
                            "help_text": "Select the songs for the jukebox. A song must have a recording for it to show up in the jukebox.",
                            "min_num": 1,
                        },
                    ),
                    51: (
                        "wagtail.blocks.StructBlock",
                        [
                            [
                                ("foreground_text", 46),
                                ("background_text", 47),
                                ("jukebox_image", 48),
                                ("tracks", 50),
                            ]
                        ],
                        {},
                    ),
                    52: (
                        "wagtail.blocks.ListBlock",
                        (42,),
                        {
                            "help_text": "Select images to display in the banner.",
                            "max_num": 7,
                            "min_num": 7,
                        },
                    ),
                    53: ("wagtail.blocks.StructBlock", [[("images", 52)]], {}),
                    54: ("wagtail.blocks.TextBlock", (), {"required": False}),
                    55: (
                        "wagtail.blocks.StructBlock",
                        [
                            [
                                ("image", 42),
                                ("header", 0),
                                ("subheader", 54),
                                ("author", 0),
                            ]
                        ],
                        {},
                    ),
                    56: (
                        "wagtail.blocks.CharBlock",
                        (),
                        {
                            "help_text": "Enter the headline for the upcoming public gigs.",
                            "required": False,
                        },
                    ),
                    57: ("wagtail.blocks.StructBlock", [[("headline", 56)]], {}),
                },
                null=True,
            ),
        ),
    ]
