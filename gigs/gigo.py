"""
Gig-O-Matic API helper functions.
"""
import logging
from datetime import datetime
from zoneinfo import ZoneInfo

import requests

from django.conf import settings

logger = logging.getLogger(__name__)


def convert_utc_gig_to_central(gig):
    """
    Convert a gig's UTC date/time to US/Central timezone (handles CST/CDT automatically).
    
    For display purposes, we use the API's date field but convert the time to local timezone.
    This ensures that events are displayed on the date they're scheduled, even if timezone
    conversion would technically put them on a different day.
    
    Args:
        gig: Dictionary containing gig data with 'date', 'set_time', and/or 'call_time' fields
             Times are assumed to be in UTC.
        
    Returns:
        tuple: (date_str, local_datetime_obj) where:
               - date_str: Date string from API (YYYY-MM-DD format)
               - local_datetime_obj: timezone-aware datetime object in Central Time (or None if no time available)
    """
    gig_date = gig.get('date', '')
    if not gig_date:
        return gig_date, None
    
    # Prefer set_time; fallback to call_time
    set_time = gig.get('set_time', '').strip() if isinstance(gig.get('set_time'), str) else ''
    call_time = gig.get('call_time', '').strip() if isinstance(gig.get('call_time'), str) else ''
    time_str = set_time if set_time else call_time
    
    if time_str:
        try:
            # Combine UTC date and time into a full datetime
            utc_datetime = datetime.strptime(f"{gig_date} {time_str}", "%Y-%m-%d %H:%M")
            utc_datetime = utc_datetime.replace(tzinfo=ZoneInfo("UTC"))
            
            # Convert to US/Central timezone (auto-handles CST/CDT based on date)
            central_datetime = utc_datetime.astimezone(ZoneInfo("America/Chicago"))
            
            # Use the API's date field as-is (don't adjust based on timezone conversion)
            # This keeps events on their scheduled date regardless of timezone differences
            return gig_date, central_datetime
        except (ValueError, TypeError) as e:
            logger.warning(f"Failed to parse gig date/time: {gig_date} {time_str} - {e}")
            # If parsing fails, return original date with no time
            pass
    
    return gig_date, None


def make_gigo_api_request(endpoint, timeout=10, retries=0, method='GET', data=None):
    """
    Make requests to the Gig-O-Matic API with proper error handling.
    
    Args:
        endpoint (str): The API endpoint (e.g., '/gigs' or '/gigs/{id}')
        timeout (int): Request timeout in seconds (default: 10)
        retries (int): Number of retry attempts (default: 0)
        method (str): HTTP method - 'GET', 'POST', 'PATCH', 'PUT', 'DELETE' (default: 'GET')
        data (dict): JSON data to send with POST/PATCH/PUT requests (default: None)
        
    Returns:
        dict or None: Response JSON data if successful, None for responses with
                     no content (e.g., 204 No Content) or non-JSON responses, None if request failed
        
    Notes:
        This function uses the GIGO_API_URL and GIGO_API_KEY settings from Django
        settings. It will retry failed requests up to the specified number of times.
        Handles empty response bodies (common for DELETE operations) and non-JSON responses gracefully.
    """
    api_url = getattr(settings, "GIGO_API_URL", None)
    api_key = getattr(settings, "GIGO_API_KEY", None)

    if not api_url or not api_key:
        logger.warning(
            "GigoGig API settings are not configured (GIGO_API_URL or GIGO_API_KEY missing); "
            "skipping API request to endpoint %s",
            endpoint,
        )
        return None

    url = f"{api_url}{endpoint}"
    headers = {"X-API-KEY": api_key}
    
    for attempt in range(retries + 1):
        try:
            method_upper = method.upper()
            request_kwargs = {"headers": headers, "timeout": timeout}
            if data is not None and method_upper in {"POST", "PATCH", "PUT"}:
                request_kwargs["json"] = data

            if method_upper == 'GET':
                response = requests.get(url, headers=headers, timeout=timeout)
            elif method_upper == 'POST':
                response = requests.post(url, **request_kwargs)
            elif method_upper == 'PATCH':
                response = requests.patch(url, **request_kwargs)
            elif method_upper == 'PUT':
                response = requests.put(url, **request_kwargs)
            elif method_upper == 'DELETE':
                response = requests.delete(url, headers=headers, timeout=timeout)
            else:
                logger.error("Unsupported HTTP method: %s", method)
                return None
                
            response.raise_for_status()
            
            # Handle responses with no content (e.g., 204 No Content)
            if response.status_code == 204 or not response.content:
                return None
            
            # Try to parse JSON, return None for non-JSON responses
            try:
                return response.json()
            except ValueError:
                logger.warning("Non-JSON response from %s: %s", endpoint, response.text[:100])
                return None
                
        except requests.exceptions.RequestException as e:
            if attempt < retries:
                logger.info("API request attempt %d failed for %s, retrying: %s", attempt + 1, endpoint, e)
                continue
            else:
                logger.warning("All API request attempts failed for %s: %s", endpoint, e, exc_info=True)
                return None
        except Exception as e:
            logger.error("Unexpected error making API request to %s: %s", endpoint, e, exc_info=True)
            return None
