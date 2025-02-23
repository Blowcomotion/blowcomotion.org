from .base import *

DEBUG = False
LIBSASS_OUTPUT_STYLE = 'compressed'


try:
    from .local import *
except ImportError:
    pass
