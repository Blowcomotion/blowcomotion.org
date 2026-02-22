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

try:
    from .local import *
except ImportError:
    pass
