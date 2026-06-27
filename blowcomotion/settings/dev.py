from .base import *

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = True

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = "django-insecure-gpnmtm+eot&u_ki#&#sj7=^6*x0o!zlpf^qfnpq(&=qnx1etdz"

# SECURITY WARNING: define the correct hosts in production!
ALLOWED_HOSTS = ["*"]

EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"

# GO3 Local Development Settings
GIGO_API_URL = None
# Set a test API key (you'll need to generate this in GO3)
GIGO_API_KEY = "test-api-key-local"
# Use a test band ID locally (set up a test band in local GO3)
GIGO_BAND_ID_LOCAL = None

# reCAPTCHA: In development, keys are typically not set, so server-side reCAPTCHA
# validation is skipped by default.
# To test with real keys locally, set them in local.py:
# RECAPTCHA_PUBLIC_KEY = 'your-site-key'
# RECAPTCHA_PRIVATE_KEY = 'your-secret-key'

try:
    from .local import *
except ImportError:
    pass

# Must come after local.py import — local.py re-imports base.py which resets MEDIA_URL
MEDIA_URL = "https://www.blowcomotion.org/media/"
