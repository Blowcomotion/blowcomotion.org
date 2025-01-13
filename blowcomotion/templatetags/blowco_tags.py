from django import template

register = template.Library()

@register.inclusion_tag("tags/logo.html")
def logo():
    return {}