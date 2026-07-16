"""
Settings for the Gig-O-Matic (GO3) integration workflow only.

Used by `.github/workflows/gigo-integration.yml`, which boots a real GO3
instance in the same CI job and points these settings at it, so that
`sync_gigs` makes a real (unmocked) HTTP call against a live server instead
of the placeholder `http://localhost:8000/api` in base.py. Not referenced by
manage.py, dev.py, production.py, or local.py — this is not part of the
normal dev/prod settings split.
"""
import os

from .dev import *

GIGO_API_URL = os.environ.get("GIGO_API_URL", "http://localhost:8001/api")
GIGO_API_KEY = os.environ.get("GIGO_API_KEY", "")
GIGO_BAND_NAME = os.environ.get("GIGO_BAND_NAME", "Blowcomotion")
