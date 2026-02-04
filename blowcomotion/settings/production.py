from .base import *

DEBUG = False
LIBSASS_OUTPUT_STYLE = 'compressed'
WAGTAILADMIN_BASE_URL = 'https://www.blowcomotion.org'

try:
    from .local import *
except ImportError:
    pass
