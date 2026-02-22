"""
Utility functions for the Blowcomotion application.
"""
import logging
from datetime import datetime, timedelta

import requests

from django.conf import settings
from django.core.exceptions import ValidationError

logger = logging.getLogger(__name__)


def adjust_gig_date_for_early_morning(gig):
    """
    Adjust gig date if the time is very early morning (before 6 AM).
    This handles cases where events that happen late at night are stored with
    the next day's date and a post-midnight time.
    
    Args:
        gig: Dictionary containing gig data with 'date', 'set_time', and/or 'call_time' fields
        
    Returns:
        str: Adjusted date string in YYYY-MM-DD format
    """
    gig_date = gig.get('date', '')
    if not gig_date:
        return gig_date
    
    # Prefer set_time; fallback to call_time
    set_time = gig.get('set_time', '').strip() if isinstance(gig.get('set_time'), str) else ''
    call_time = gig.get('call_time', '').strip() if isinstance(gig.get('call_time'), str) else ''
    time_str = set_time if set_time else call_time
    
    if time_str:
        try:
            # Parse the time
            time_obj = datetime.strptime(time_str, "%H:%M")
            # If time is before 6 AM, subtract one day from the date
            if time_obj.hour < 6:
                date_obj = datetime.strptime(gig_date, "%Y-%m-%d")
                adjusted_date = date_obj - timedelta(days=1)
                return adjusted_date.strftime("%Y-%m-%d")
        except (ValueError, TypeError):
            # If parsing fails, return original date
            pass
    
    return gig_date


def validate_birthday(birth_day, birth_month):
    """
    Validate that a birth day is valid for the given birth month.
    
    Args:
        birth_day: Integer representing the day of the month (1-31)
        birth_month: Integer or string representing the month (1-12)
        
    Raises:
        ValidationError: If the day is invalid for the given month
    """
    if not birth_day:
        return  # No validation needed if birth_day is not provided
    
    # Validate day is in valid range
    if birth_day < 1 or birth_day > 31:
        raise ValidationError("Birth day must be between 1 and 31")
    
    # Check if day is valid for the given month
    if birth_month:
        # Convert to int if it's a string
        month_num = int(birth_month) if isinstance(birth_month, str) else birth_month
        
        # Days in each month (assuming leap year for February to allow Feb 29)
        days_in_month = [31, 29, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31]
        
        # Validate month is in valid range
        if month_num < 1 or month_num > 12:
            raise ValidationError("Birth month must be between 1 and 12")
        
        max_day = days_in_month[month_num - 1]
        
        if birth_day > max_day:
            month_names = [
                'January', 'February', 'March', 'April', 'May', 'June',
                'July', 'August', 'September', 'October', 'November', 'December'
            ]
            raise ValidationError(
                f"Day {birth_day} is not valid for {month_names[month_num - 1]}"
            )


def send_member_to_go3_band_invite(email, use_local_band=False):
    """
    Send a member invitation to the GO3 band invite API.
    
    This function invites a new member (identified by their email) to the Blowcomotion
    band in GO3. It can use either the local test band or the production band depending
    on the use_local_band parameter.
    
    Args:
        email: The email address of the member to invite
        use_local_band: If True, uses local GO3 instance; if False, uses production
        
    Returns:
        dict: A dictionary containing:
            - 'status': 'success' or 'error'
            - 'message': Human-readable status message
            - 'data': Response data from GO3 (if successful)
            - 'in_band': If True, member is already in the band
            - 'invalid': If True, email is invalid
            
    Notes:
        If GO3 settings are not properly configured, this function does not raise an
        exception. Instead, it returns a dict with ``status`` set to ``'error'`` and
        an explanatory ``message`` describing the misconfiguration.
    """
    # Determine which settings to use
    api_url = getattr(settings, 'GIGO_API_URL', None)
    api_key = getattr(settings, 'GIGO_API_KEY', None)
    
    if use_local_band:
        band_id = getattr(settings, 'GIGO_BAND_ID_LOCAL', None)
    else:
        band_id = getattr(settings, 'GIGO_BAND_ID', None)
    
    # Validate that all required settings are configured
    if not all([api_url, api_key, band_id]):
        logger.warning(
            f"GO3 band invite not sent: Missing configuration. "
            f"API URL: {bool(api_url)}, API Key: {bool(api_key)}, Band ID: {bool(band_id)}"
        )
        return {
            'status': 'error',
            'message': 'GO3 band invite not configured',
            'data': None
        }
    
    # Prepare the API request
    url = f"{api_url}/bands/{band_id}/invites"
    headers = {'X-API-KEY': api_key}
    payload = {'emails': [email]}
    
    try:
        logger.info(f"Sending band invite to GO3 for {email} to band {band_id}")
        response = requests.post(url, json=payload, headers=headers, timeout=10)
        response.raise_for_status()
        
        data = response.json()
        
        # Check if the member was already in the band
        if data.get('in_band') and email in data['in_band']:
            logger.info(f"Member {email} is already in the GO3 band")
            return {
                'status': 'success',
                'message': 'Member already in band',
                'data': data,
                'in_band': True,
                'invalid': False
            }
        
        # Check if the email was invalid
        if data.get('invalid') and email in data['invalid']:
            logger.warning(f"Invalid email {email} for GO3 band invite")
            return {
                'status': 'error',
                'message': 'Invalid email address',
                'data': data,
                'in_band': False,
                'invalid': True
            }
        
        # Check if the member was successfully invited
        if data.get('invited') and email in data['invited']:
            logger.info(f"Successfully sent GO3 band invite to {email}")
            return {
                'status': 'success',
                'message': 'Invitation sent successfully',
                'data': data,
                'in_band': False,
                'invalid': False
            }
        
        # Unexpected response
        logger.warning(f"Unexpected GO3 response for {email}: {data}")
        return {
            'status': 'error',
            'message': 'Unexpected response from GO3',
            'data': data,
            'in_band': False,
            'invalid': False
        }
        
    except requests.exceptions.Timeout:
        logger.warning(f"Timeout sending GO3 band invite for {email}")
        return {
            'status': 'error',
            'message': 'Timeout connecting to GO3',
            'data': None
        }
    except requests.exceptions.ConnectionError:
        logger.warning(f"Connection error sending GO3 band invite for {email}")
        return {
            'status': 'error',
            'message': 'Could not connect to GO3',
            'data': None
        }
    except requests.exceptions.HTTPError as e:
        logger.error(f"HTTP error sending GO3 band invite for {email}: {e}")
        status_code = getattr(e.response, 'status_code', 'unknown')
        return {
            'status': 'error',
            'message': f'HTTP error from GO3: {status_code}',
            'data': None
        }
    except Exception as e:
        logger.error(f"Unexpected error sending GO3 band invite for {email}: {e}", exc_info=True)
        return {
            'status': 'error',
            'message': f'Error sending invite: {str(e)}',
            'data': None
        }
