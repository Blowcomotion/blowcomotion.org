from datetime import date, timedelta

from django.contrib.auth.decorators import login_required, permission_required
from django.shortcuts import render

from blowcomotion.models import Member

# Constants
BIRTHDAY_RANGE_DAYS = 30


def get_birthday(year, month, day):
    """
    Helper function to get a birthday date for a given year, handling leap year edge cases.
    
    Args:
        year: The year for the birthday
        month: The birth month
        day: The birth day
        
    Returns:
        date object if valid, None if invalid date
    """
    try:
        return date(year, month, day)
    except ValueError:
        # Handle leap year edge case (Feb 29)
        if month == 2 and day == 29:
            return date(year, 2, 28)
        else:
            return None  # Skip invalid dates


def get_next_year_birthday_info(member, today, future_date):
    """
    Helper function to check if a member's next year birthday falls within the upcoming range.
    
    Args:
        member: Member object with birth_month, birth_day, and birth_year
        today: Current date
        future_date: End date for the upcoming range
        
    Returns:
        dict with next year birthday info if within range, None otherwise
    """
    next_year = today.year + 1
    
    try:
        next_year_birthday = date(next_year, member.birth_month, member.birth_day)
        if today < next_year_birthday <= future_date:
            birthday_info = {
                'birthday': next_year_birthday,
                'days_until': (next_year_birthday - today).days
            }
            
            # Calculate age for next year if birth year is available
            if member.birth_year:
                birthday_info['age'] = next_year - member.birth_year
                
            return birthday_info
    except ValueError:
        # Handle invalid dates (e.g., Feb 29 in non-leap years)
        pass
    
    return None


@login_required
@permission_required('blowcomotion.view_attendancerecord', raise_exception=True)
def birthdays(request):
    """
    View to display recent and upcoming member birthdays.
    Shows birthdays from the past BIRTHDAY_RANGE_DAYS and the upcoming BIRTHDAY_RANGE_DAYS.
    """
    today = date.today()
    past_date = today - timedelta(days=BIRTHDAY_RANGE_DAYS)
    future_date = today + timedelta(days=BIRTHDAY_RANGE_DAYS)
    
    # Calculate relevant birth months to reduce database queries
    # We need to consider months that could have birthdays in our date range
    relevant_months = set()
    
    # Add months for the date range - iterate through each day and collect months
    current_date = past_date
    while current_date <= future_date:
        relevant_months.add(current_date.month)
        current_date += timedelta(days=1)
    
    # Also add next year's months for future_date if we're near year end
    if future_date.month <= 2:  # If future date is in Jan/Feb, include Dec from previous year
        relevant_months.add(12)
    if past_date.month >= 11:  # If past date is in Nov/Dec, include Jan from next year  
        relevant_months.add(1)
    
    # Get all active members with birthday information, filtered by relevant months
    members_with_birthdays = Member.objects.filter(
        is_active=True,
        birth_month__isnull=False,
        birth_day__isnull=False,
        birth_month__in=relevant_months
    ).select_related('primary_instrument').order_by('first_name', 'last_name')
    
    recent_birthdays = []
    upcoming_birthdays = []
    today_birthdays = []
    
    for member in members_with_birthdays:
        # Create a date object for this year's birthday
        birthday_this_year = get_birthday(today.year, member.birth_month, member.birth_day)
        if birthday_this_year is None:
            continue  # Skip invalid dates
        
        # Calculate age (if birth year is available)
        age = None
        if member.birth_year:
            age = today.year - member.birth_year
            if today < birthday_this_year:
                age -= 1
        
        member_info = {
            'member': member,
            'birthday': birthday_this_year,
            'age': age,
            'display_name': f'"{member.preferred_name}" {member.first_name}' if member.preferred_name else f'{member.first_name}',
        }
        
        # Check if birthday is today
        if birthday_this_year == today:
            today_birthdays.append(member_info)
        # Check if birthday was in the past BIRTHDAY_RANGE_DAYS days
        elif past_date <= birthday_this_year < today:
            member_info['days_ago'] = (today - birthday_this_year).days
            recent_birthdays.append(member_info)
        # Check if birthday is in the upcoming BIRTHDAY_RANGE_DAYS days
        elif today < birthday_this_year <= future_date:
            member_info['days_until'] = (birthday_this_year - today).days
            upcoming_birthdays.append(member_info)
        # Check if birthday already passed this year; consider next year's birthday if it's within range
        elif birthday_this_year < today:
            next_year_info = get_next_year_birthday_info(member, today, future_date)
            if next_year_info:
                member_info.update(next_year_info)
                upcoming_birthdays.append(member_info)
    
    # Sort lists efficiently - recent birthdays by date (most recent first)
    recent_birthdays.sort(key=lambda x: x['birthday'], reverse=True)
    # Upcoming birthdays by date (soonest first) 
    upcoming_birthdays.sort(key=lambda x: x['birthday'])
    # Today's birthdays are already ordered by name due to database ordering
    
    context = {
        'today_birthdays': today_birthdays,
        'recent_birthdays': recent_birthdays,
        'upcoming_birthdays': upcoming_birthdays,
        'today': today,
    }
    
    return render(request, 'birthdays.html', context)
