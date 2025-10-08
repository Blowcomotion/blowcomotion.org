"""
Utility functions for the Blowcomotion application.
"""
from django.core.exceptions import ValidationError


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
