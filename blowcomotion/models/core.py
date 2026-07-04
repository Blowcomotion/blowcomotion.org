import datetime

from wagtail.admin.panels import FieldPanel, MultiFieldPanel
from wagtail.contrib.settings.models import BaseSiteSetting, register_setting
from wagtail.fields import RichTextField, StreamField
from wagtail.images.models import AbstractImage, AbstractRendition, Image

from django.db import models

from blowcomotion import blocks as blowcomotion_blocks


def get_default_expiration_date():
    return datetime.date.today() + datetime.timedelta(days=1)

@register_setting
class NotificationBanner(BaseSiteSetting):
    message = RichTextField(blank=True, null=True)
    expiration_date = models.DateField(
        blank=True,
        null=True,
        default=get_default_expiration_date,
        help_text="Date when the banner will no longer be displayed. Leave blank for no expiration.",
    )


@register_setting
class SiteSettings(BaseSiteSetting):
    logo = models.ForeignKey(
        "blowcomotion.CustomImage",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
    )
    favicon = models.ForeignKey(
        "blowcomotion.CustomImage",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
        help_text="Image used for the browser favicon. Upload a square image for best results.",
    )
    footer_text = models.CharField(
        max_length=255,
        blank=True,
        null=True,
        help_text="Text to display in the footer",
    )
    email = models.EmailField(blank=True, null=True)
    instagram = models.URLField(blank=True, null=True)
    facebook = models.URLField(blank=True, null=True)
    header_menus = StreamField(
        [
            ("menu_item", blowcomotion_blocks.MenuItem()),
        ],
        blank=True,
        null=True,
    )
    contact_form_email_recipients = models.CharField(
        max_length=1024,
        blank=True,
        null=True,
        help_text="Comma-separated list of email addresses to receive contact form submissions",
    )
    join_band_form_email_recipients = models.CharField(
        max_length=1024,
        blank=True,
        null=True,
        help_text="Comma-separated list of email addresses to receive join band form submissions",
    )
    booking_form_email_recipients = models.CharField(
        max_length=1024,
        blank=True,
        null=True,
        help_text="Comma-separated list of email addresses to receive booking form submissions",
    )
    feedback_form_email_recipients = models.CharField(
        max_length=1024,
        blank=True,
        null=True,
        help_text="Comma-separated list of email addresses to receive feedback form submissions",
    )
    donate_form_email_recipients = models.CharField(
        max_length=1024,
        blank=True,
        null=True,
        help_text="Comma-separated list of email addresses to receive donate form submissions",
    )
    birthday_summary_email_recipients = models.CharField(
        max_length=1024,
        blank=True,
        null=True,
        help_text="Comma-separated list of email addresses to receive monthly birthday summary emails",
    )
    instrument_rental_notification_recipients = models.CharField(
        max_length=1024,
        blank=True,
        null=True,
        help_text="Comma-separated list of email addresses to receive instrument rental notifications",
    )
    instrument_rental_policy = RichTextField(
        blank=True,
        help_text="Lending policy text displayed on the instrument rental request form.",
    )
    venmo_donate_url = models.URLField(
        blank=True,
        null=True,
        help_text="URL to Venmo donation page",
    )
    square_donate_url = models.URLField(
        blank=True,
        null=True,
        help_text="URL to Square donation page",
    )
    patreon_url = models.URLField(
        blank=True,
        null=True,
        help_text="URL to Patreon page",
    )

    attendance_cleanup_days = models.IntegerField(
        default=90,
        help_text=(
            "Number of days since last seeing a member before they are marked inactive "
            "(attendance cleanup) and before instrument renters receive a nag email."
        ),
    )
    nag_cooldown_days = models.IntegerField(
        default=7,
        help_text="Days to wait before sending another nag email to the same renter.",
    )
    attendance_report_notification_recipients = models.CharField(
        max_length=1024,
        blank=True,
        null=True,
        help_text="Comma-separated list of email addresses to receive attendance report notifications",
    )
    member_signup_notification_recipients = models.CharField(
        max_length=1024,
        blank=True,
        null=True,
        help_text="Comma-separated list of email addresses to receive member signup notifications",
    )

    panels = [
        MultiFieldPanel([
            FieldPanel('logo'),
            FieldPanel('favicon'),
            FieldPanel('footer_text'),
            FieldPanel('email'),
        ], heading="Site Branding"),

        MultiFieldPanel([
            FieldPanel('instagram'),
            FieldPanel('facebook'),
        ], heading="Social Media"),

        FieldPanel('header_menus'),

        MultiFieldPanel([
            FieldPanel('contact_form_email_recipients'),
            FieldPanel('join_band_form_email_recipients'),
            FieldPanel('booking_form_email_recipients'),
            FieldPanel('feedback_form_email_recipients'),
            FieldPanel('donate_form_email_recipients'),
            FieldPanel('birthday_summary_email_recipients'),
            FieldPanel('instrument_rental_notification_recipients'),
            FieldPanel('attendance_report_notification_recipients'),
            FieldPanel('member_signup_notification_recipients'),
        ], heading="Form Email Recipients"),

        MultiFieldPanel([
            FieldPanel('instrument_rental_policy'),
        ], heading="Instrument Rental Policy"),

        MultiFieldPanel([
            FieldPanel('venmo_donate_url'),
            FieldPanel('square_donate_url'),
            FieldPanel('patreon_url'),
        ], heading="Donation Links"),

        MultiFieldPanel([
            FieldPanel('attendance_cleanup_days'),
            FieldPanel('nag_cooldown_days'),
        ], heading="Attendance Cleanup Notifications", help_text="Configure attendance cleanup settings."),
    ]

    class Meta:
        permissions = [
            ("access_dev_tools", "Can access developer data dump tools"),
            ("access_real_data_exports", "Can access real member data dumps and CSV exports"),
        ]


class CustomImage(AbstractImage):
    # Add any extra fields to image here

    # To add a caption field:
    caption = models.CharField(max_length=255, blank=True)

    admin_form_fields = Image.admin_form_fields + (
        # Then add the field names here to make them appear in the form:
        "caption",
    )

    @property
    def default_alt_text(self):
        # Force editors to add specific alt text if description is empty.
        # Do not use image title which is typically derived from file name.
        return getattr(self, "description", None)


class CustomRendition(AbstractRendition):
    image = models.ForeignKey(
        CustomImage, on_delete=models.CASCADE, related_name="renditions"
    )

    class Meta:
        unique_together = (("image", "filter_spec", "focal_point_key"),)
