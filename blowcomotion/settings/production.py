from .base import *

DEBUG = False
COMPRESS_OFFLINE = True
LIBSASS_OUTPUT_STYLE = 'compressed'


try:
    from .local import *
except ImportError:
    pass
