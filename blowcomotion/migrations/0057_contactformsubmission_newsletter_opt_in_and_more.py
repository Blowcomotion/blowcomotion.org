# Generated by Django 5.1.6 on 2025-05-22 23:54

import wagtail.fields
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("blowcomotion", "0056_member_address_member_city_member_country_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="contactformsubmission",
            name="newsletter_opt_in",
            field=models.BooleanField(
                default=False, help_text="Whether the user signed up for the newsletter"
            ),
        ),
        migrations.AlterField(
            model_name="blankcanvaspage",
            name="body",
            field=wagtail.fields.StreamField(
                [
                    ("accordion_list", 4),
                    ("button", 10),
                    ("column_layout", 27),
                    ("contact_form", 14),
                    ("countdown", 32),
                    ("events", 39),
                    ("full_width_image", 41),
                    ("hero", 43),
                    ("horizontal_rule", 15),
                    ("multi_image_banner", 45),
                    ("paypal_donate_button", 17),
                    ("quoted_image", 47),
                    ("rich_text", 20),
                    ("spacer", 21),
                    ("upcoming_events", 49),
                    ("venmo_donate_button", 22),
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
                        "wagtail.blocks.CharBlock",
                        (),
                        {
                            "help_text": "Enter the title for the contact form.",
                            "required": False,
                        },
                    ),
                    12: (
                        "wagtail.blocks.RichTextBlock",
                        (),
                        {
                            "help_text": "Enter the description for the contact form.",
                            "required": False,
                        },
                    ),
                    13: (
                        "wagtail.blocks.BooleanBlock",
                        (),
                        {
                            "help_text": "Include an opt-in checkbox for the newsletter.",
                            "required": False,
                        },
                    ),
                    14: (
                        "wagtail.blocks.StructBlock",
                        [
                            [
                                ("title", 11),
                                ("description", 12),
                                ("button_text", 5),
                                ("newsletter_opt_in", 13),
                            ]
                        ],
                        {},
                    ),
                    15: ("blowcomotion.blocks.HorizontalRuleBlock", (), {}),
                    16: (
                        "wagtail.images.blocks.ImageChooserBlock",
                        (),
                        {"template": "blocks/image_block.html"},
                    ),
                    17: ("wagtail.blocks.StructBlock", [[("alignment", 8)]], {}),
                    18: ("wagtail.blocks.RichTextBlock", (), {}),
                    19: (
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
                    20: (
                        "wagtail.blocks.StructBlock",
                        [[("rich_text", 18), ("align", 19)]],
                        {},
                    ),
                    21: ("blowcomotion.blocks.SpacerBlock", (), {}),
                    22: (
                        "wagtail.blocks.StructBlock",
                        [[("button_text", 5), ("alignment", 8)]],
                        {},
                    ),
                    23: (
                        "wagtail.blocks.StreamBlock",
                        [
                            [
                                ("accordion_list", 4),
                                ("button", 10),
                                ("contact_form", 14),
                                ("horizontal_rule", 15),
                                ("image", 16),
                                ("paypal_donate_button", 17),
                                ("rich_text", 20),
                                ("spacer", 21),
                                ("venmo_donate_button", 22),
                            ]
                        ],
                        {"required": False},
                    ),
                    24: (
                        "wagtail.blocks.StructBlock",
                        [[("left_column", 23), ("right_column", 23)]],
                        {},
                    ),
                    25: (
                        "wagtail.blocks.StructBlock",
                        [
                            [
                                ("left_column", 23),
                                ("middle_column", 23),
                                ("right_column", 23),
                            ]
                        ],
                        {},
                    ),
                    26: (
                        "wagtail.blocks.StructBlock",
                        [
                            [
                                ("left_column", 23),
                                ("middle_column", 23),
                                ("right_column", 23),
                                ("middle_left_column", 23),
                                ("middle_right_column", 23),
                            ]
                        ],
                        {},
                    ),
                    27: (
                        "wagtail.blocks.StreamBlock",
                        [
                            [
                                ("two_column", 24),
                                ("three_column", 25),
                                ("four_column", 26),
                            ]
                        ],
                        {},
                    ),
                    28: (
                        "wagtail.images.blocks.ImageChooserBlock",
                        (),
                        {"required": False},
                    ),
                    29: (
                        "wagtail.blocks.DateBlock",
                        (),
                        {"help_text": "Enter the date for the countdown."},
                    ),
                    30: (
                        "wagtail.blocks.CharBlock",
                        (),
                        {
                            "help_text": "Enter the top line text for the countdown.",
                            "required": False,
                        },
                    ),
                    31: (
                        "wagtail.blocks.CharBlock",
                        (),
                        {
                            "help_text": "Enter the sub line text for the countdown.",
                            "required": False,
                        },
                    ),
                    32: (
                        "wagtail.blocks.StructBlock",
                        [
                            [
                                ("background_image", 28),
                                ("countdown_date", 29),
                                ("head_line", 30),
                                ("sub_line", 31),
                                ("button_text", 5),
                                ("button_url", 6),
                                ("button_target", 7),
                            ]
                        ],
                        {},
                    ),
                    33: ("wagtail.blocks.CharBlock", (), {}),
                    34: ("blowcomotion.chooser_blocks.GigoGigChooserBlock", (), {}),
                    35: (
                        "wagtail.blocks.StructBlock",
                        [[("details", 34), ("event_scroller_image", 28)]],
                        {},
                    ),
                    36: ("wagtail.blocks.ListBlock", (35,), {}),
                    37: ("blowcomotion.chooser_blocks.EventChooserBlock", (), {}),
                    38: (
                        "wagtail.blocks.ListBlock",
                        (37,),
                        {
                            "help_text": "Events that are not associated with Gig-o-Matic"
                        },
                    ),
                    39: (
                        "wagtail.blocks.StructBlock",
                        [[("scroller_title", 33), ("gigo_gigs", 36), ("events", 38)]],
                        {},
                    ),
                    40: ("wagtail.images.blocks.ImageChooserBlock", (), {}),
                    41: ("wagtail.blocks.StructBlock", [[("image", 40)]], {}),
                    42: ("wagtail.blocks.URLBlock", (), {"required": False}),
                    43: (
                        "wagtail.blocks.StructBlock",
                        [
                            [
                                ("image", 40),
                                ("top_line", 0),
                                ("middle_line", 0),
                                ("bottom_line", 0),
                                ("youtube_url", 42),
                            ]
                        ],
                        {},
                    ),
                    44: (
                        "wagtail.blocks.ListBlock",
                        (40,),
                        {
                            "help_text": "Select images to display in the banner.",
                            "max_num": 7,
                            "min_num": 7,
                        },
                    ),
                    45: ("wagtail.blocks.StructBlock", [[("images", 44)]], {}),
                    46: ("wagtail.blocks.TextBlock", (), {"required": False}),
                    47: (
                        "wagtail.blocks.StructBlock",
                        [
                            [
                                ("image", 40),
                                ("header", 0),
                                ("subheader", 46),
                                ("author", 0),
                            ]
                        ],
                        {},
                    ),
                    48: (
                        "wagtail.blocks.CharBlock",
                        (),
                        {
                            "help_text": "Enter the headline for the upcoming public gigs.",
                            "required": False,
                        },
                    ),
                    49: ("wagtail.blocks.StructBlock", [[("headline", 48)]], {}),
                },
                null=True,
            ),
        ),
    ]
