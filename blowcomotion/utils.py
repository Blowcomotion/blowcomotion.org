"""
Utility functions for the Blowcomotion application.
"""
from datetime import datetime, timedelta

from django.core.exceptions import ValidationError


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
