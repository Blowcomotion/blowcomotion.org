"""
Patreon API v2 client for validating member membership status.

Returns a dict with membership details if the email is found, or None if the
API is not configured or an unexpected error occurred.

Configuration (in local.py / production secrets):
    PATREON_ACCESS_TOKEN   — creator access token; must have campaigns.members
                             and campaigns.members[email] scopes
    PATREON_CAMPAIGN_ID    — numeric Patreon campaign ID for the organisation

If either setting is absent the function returns None (skip silently).
"""

import logging

import requests

from django.conf import settings
from django.utils.dateparse import parse_datetime

logger = logging.getLogger(__name__)

PATREON_MEMBERS_URL = "https://www.patreon.com/api/oauth2/v2/campaigns/{campaign_id}/members"
ACTIVE_PATRON_STATUS = "active_patron"
# Safety cap: stop paginating after this many pages to avoid hanging in-request.
MAX_PAGES = 20

_MEMBER_FIELDS = ",".join([
    "patron_status",
    "email",
    "currently_entitled_amount_cents",
    "last_charge_date",
    "last_charge_status",
    "lifetime_support_cents",
    "pledge_relationship_start",
])


def check_patreon_membership(email: str) -> dict | None:
    """
    Paginate through the campaign's member list and look up *email*.

    The Patreon API v2 does not support server-side email filtering; the full
    member list must be fetched page by page and matched client-side.

    Returns a dict on success (member found or exhausted):
        {
            "is_active":           bool,
            "pledge_cents":        int | None,   # currently_entitled_amount_cents
            "last_charge_status":  str | None,   # e.g. "Paid", "Declined"
            "patron_since":        datetime | None,
            "lifetime_cents":      int | None,
        }

    Returns None if configuration is missing or an API/network error occurred
    (callers should treat this as "unknown / not checked").
    """
    access_token = getattr(settings, "PATREON_ACCESS_TOKEN", None)
    campaign_id = getattr(settings, "PATREON_CAMPAIGN_ID", None)

    if not access_token or not campaign_id:
        logger.debug(
            "patreon_client: PATREON_ACCESS_TOKEN or PATREON_CAMPAIGN_ID not configured; "
            "skipping validation"
        )
        return None

    headers = {"Authorization": f"Bearer {access_token}"}
    url = PATREON_MEMBERS_URL.format(campaign_id=campaign_id)
    params = {
        "fields[member]": _MEMBER_FIELDS,
        "page[count]": 100,
    }

    target = email.lower()
    pages_fetched = 0

    while url and pages_fetched < MAX_PAGES:
        try:
            response = requests.get(url, headers=headers, params=params, timeout=10)
            response.raise_for_status()
            data = response.json()
        except requests.exceptions.Timeout:
            logger.error("patreon_client: request timed out (page %d)", pages_fetched + 1)
            return None
        except requests.exceptions.ConnectionError as exc:
            logger.error("patreon_client: connection error (page %d): %s", pages_fetched + 1, exc)
            return None
        except requests.exceptions.HTTPError as exc:
            status_code = exc.response.status_code if exc.response is not None else "?"
            logger.error(
                "patreon_client: HTTP %s error (page %d): %s",
                status_code,
                pages_fetched + 1,
                exc,
            )
            return None
        except Exception as exc:  # noqa: BLE001
            logger.error("patreon_client: unexpected error (page %d): %s", pages_fetched + 1, exc)
            return None

        pages_fetched += 1
        # Clear params so they are not duplicated by the cursor URL on subsequent pages.
        params = {}

        for member in data.get("data", []):
            attrs = member.get("attributes", {})
            member_email = (attrs.get("email") or "").lower()
            if member_email == target:
                patron_status = attrs.get("patron_status")
                is_active = patron_status == ACTIVE_PATRON_STATUS
                logger.info(
                    "patreon_client: member found; patron_status=%s active=%s",
                    patron_status,
                    is_active,
                )
                return {
                    "is_active": is_active,
                    "pledge_cents": attrs.get("currently_entitled_amount_cents"),
                    "last_charge_date": parse_datetime(attrs.get("last_charge_date") or ""),
                    "last_charge_status": attrs.get("last_charge_status"),
                    "patron_since": parse_datetime(attrs.get("pledge_relationship_start") or ""),
                    "lifetime_cents": attrs.get("lifetime_support_cents"),
                }

        # Follow the next-page cursor if one exists.
        url = (data.get("links") or {}).get("next")

    if pages_fetched >= MAX_PAGES and url:
        logger.warning(
            "patreon_client: reached MAX_PAGES=%d without finding member; returning False",
            MAX_PAGES,
        )

    logger.info("patreon_client: member not found in campaign member list")
    return {"is_active": False, "pledge_cents": None, "last_charge_date": None, "last_charge_status": None, "patron_since": None, "lifetime_cents": None}
