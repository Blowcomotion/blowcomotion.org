from datetime import datetime

from django import template
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
