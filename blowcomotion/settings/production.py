from .base import *

DEBUG = False
LIBSASS_OUTPUT_STYLE = 'compressed'
WAGTAILADMIN_BASE_URL = 'https://www.blowcomotion.org'

# GO3 Production Settings
# Band ID for Blowcomotion in GO3 production
# GIGO_BAND_ID = None  # Set this to the actual band ID for production
# API configuration should be set via environment variables or local.py
# GIGO_API_URL = "https://go3.example.com/api"  # Set in local.py or env vars
# GIGO_API_KEY = "your-production-api-key"  # Set in local.py or env vars

try:
    from .local import *
except ImportError:
    pass
