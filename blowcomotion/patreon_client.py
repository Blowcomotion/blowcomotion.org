"""
Patreon API v2 client for validating member membership status.

Returns True if the email has an active Patreon pledge, False if the email
was found but the patron is inactive, or None if the API is not configured
or an unexpected error occurred.

Configuration (in local.py / production secrets):
    PATREON_ACCESS_TOKEN   — creator access token; must have campaigns.members
                             and campaigns.members[email] scopes
    PATREON_CAMPAIGN_ID    — numeric Patreon campaign ID for the organisation

If either setting is absent the function returns None (skip silently).
"""

import logging

import requests

from django.conf import settings

logger = logging.getLogger(__name__)

PATREON_MEMBERS_URL = "https://www.patreon.com/api/oauth2/v2/campaigns/{campaign_id}/members"
ACTIVE_PATRON_STATUS = "active_patron"
# Safety cap: stop paginating after this many pages to avoid hanging in-request.
MAX_PAGES = 20


def check_patreon_membership(email: str) -> bool | None:
    """
    Paginate through the campaign's member list and look up *email*.

    The Patreon API v2 does not support server-side email filtering; the full
    member list must be fetched page by page and matched client-side.

    Returns:
        True  — the address belongs to an active patron
        False — the address was found but is not an active patron, OR the
                address was not found anywhere in the campaign's member list
        None  — configuration is missing, or an API/network error occurred
                (callers should treat this as "unknown / not checked")
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
        "fields[member]": "patron_status,email",
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
                return is_active

        # Follow the next-page cursor if one exists.
        url = (data.get("links") or {}).get("next")

    if pages_fetched >= MAX_PAGES and url:
        logger.warning(
            "patreon_client: reached MAX_PAGES=%d without finding member; returning False",
            MAX_PAGES,
        )

    logger.info("patreon_client: member not found in campaign member list")
    return False
