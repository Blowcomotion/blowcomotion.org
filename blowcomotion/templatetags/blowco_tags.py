from django import template
from datetime import datetime

register = template.Library()


@register.filter
def datestring_format(value):
    try:
        return datetime.strptime(value, "%Y-%m-%d").strftime("%B %-d, %Y")
    except ValueError:
        return value
