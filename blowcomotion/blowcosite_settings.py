from django.db import models
from wagtail.contrib.settings.models import (
    BaseSiteSetting,
    register_setting,
)


@register_setting
class SiteSpecificSocialMediaSettings(BaseSiteSetting):
    facebook = models.URLField()