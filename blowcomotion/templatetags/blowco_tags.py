from datetime import datetime

from django import template
from django.conf import settings as django_settings
from django.core.exceptions import ValidationError
from django.core.validators import URLValidator

register = template.Library()


@register.filter
def datestring_format(value):
    try:
        return datetime.strptime(value, "%Y-%m-%d").strftime("%B %-d, %Y")
    except ValueError:
        return value
    
@register.simple_tag
def is_url(string):
    validate = URLValidator()
    try:
        validate(string)
        return True
    except ValidationError:
        return False


@register.simple_tag
def get_recaptcha_site_key():
    """
    Return the reCAPTCHA public (site) key if both keys are configured.
    Returns empty string if either key is missing to keep frontend/backend behavior consistent.
    """
    public_key = getattr(django_settings, 'RECAPTCHA_PUBLIC_KEY', None)
    private_key = getattr(django_settings, 'RECAPTCHA_PRIVATE_KEY', None)
    return public_key if (public_key and private_key) else ''
