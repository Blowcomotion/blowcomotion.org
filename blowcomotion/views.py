import base64
import json
import logging
from collections import defaultdict
from datetime import date, datetime, timedelta
from functools import wraps
from io import StringIO

import requests

from django.conf import settings
from django.contrib.auth import authenticate, login
from django.contrib.auth.forms import AuthenticationForm, UserCreationForm
from django.core.cache import cache
from django.core.mail import send_mail
from django.core.management import call_command
from django.db.models import Count, Q
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_http_methods

from blowcomotion.forms import (
    AttendanceReportFilterForm,
    MemberSignupForm,
    SectionAttendanceForm,
)
from blowcomotion.models import (
    AttendanceRecord,
    BookingFormSubmission,
    ContactFormSubmission,
    DonateFormSubmission,
    FeedbackFormSubmission,
    Instrument,
    JoinBandFormSubmission,
    Member,
    MemberInstrument,
    Section,
    SiteSettings,
)

logger = logging.getLogger(__name__)

# Constants
BIRTHDAY_RANGE_DAYS = 30


def make_gigo_api_request(endpoint, timeout=10, retries=2):
    """
    Helper function to make requests to the Gig-O-Matic API with proper error handling.
    
    Args:
        endpoint: The API endpoint (e.g., '/gigs' or '/gigs/{id}')
        timeout: Request timeout in seconds (default: 10)
        retries: Number of retry attempts (default: 2)
        
    Returns:
        dict: Response JSON data if successful, None if failed
    """
    url = f"{settings.GIGO_API_URL}{endpoint}"
    headers = {"X-API-KEY": settings.GIGO_API_KEY}
    
    for attempt in range(retries + 1):
        try:
            response = requests.get(url, headers=headers, timeout=timeout)
            response.raise_for_status()
            return response.json()
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


def http_basic_auth_generic(password_setting_or_value, realm_name, username=None, direct_password=None):
    """
    Generic decorator for HTTP Basic Authentication
    
    Args:
        password_setting_or_value: The settings key to get the password from, or the password value if direct_password is True
        realm_name: The authentication realm name
        username: If provided, both username and password must match. If None, only password is checked.
        direct_password: If True, password_setting_or_value is used as the password directly
    """
    def decorator(func):
        @wraps(func)
        def wrapper(request, *args, **kwargs):
            # Get password
            if direct_password:
                password = password_setting_or_value
            else:
                # Get password from settings each time (allows for test overrides)
                password = getattr(settings, password_setting_or_value, None)
            
            # If password is None, skip authentication
            if password is None:
                return func(request, *args, **kwargs)
            
            # Check if Authorization header exists
            if 'HTTP_AUTHORIZATION' not in request.META:
                response = HttpResponse('Unauthorized', status=401)
                response['WWW-Authenticate'] = f'Basic realm="{realm_name}"'
                return response
            
            # Parse the Authorization header
            auth_header = request.META['HTTP_AUTHORIZATION']
            if not auth_header.startswith('Basic '):
                response = HttpResponse('Unauthorized', status=401)
                response['WWW-Authenticate'] = f'Basic realm="{realm_name}"'
                return response
            
            # Decode credentials
            try:
                encoded_credentials = auth_header[6:]  # Remove 'Basic '
                decoded_credentials = base64.b64decode(encoded_credentials).decode('utf-8')
                provided_username, provided_password = decoded_credentials.split(':', 1)
            except (ValueError, UnicodeDecodeError):
                response = HttpResponse('Unauthorized', status=401)
                response['WWW-Authenticate'] = f'Basic realm="{realm_name}"'
                return response
            
            # Check credentials
            if username is None:
                # Only check password if username is None
                if provided_password == password:
                    return func(request, *args, **kwargs)
            else:
                # Check both username and password
                if provided_username == username and provided_password == password:
                    return func(request, *args, **kwargs)
            
            response = HttpResponse('Unauthorized', status=401)
            response['WWW-Authenticate'] = f'Basic realm="{realm_name}"'
            return response
        
        return wrapper
    return decorator


def http_basic_auth(username=None, password=None):
    """
    Decorator for HTTP Basic Authentication
    If username is None, any username will be accepted (only password is checked)
    If password is provided directly, uses that password for authentication.
    If password is None, uses attendance_password from SiteSettings.
    If attendance_password is None or empty, authentication is skipped.
    """
    def decorator(func):
        @wraps(func)
        def wrapper(request, *args, **kwargs):
            if password is not None:
                # Use the provided password directly
                auth_password = password
            else:
                # Get password from SiteSettings
                try:
                    site_settings = SiteSettings.for_request(request)
                    auth_password = site_settings.attendance_password
                except:
                    auth_password = None
            
            # If password is None or empty, skip authentication
            if not auth_password:
                return func(request, *args, **kwargs)
            
            # Check if Authorization header exists
            if 'HTTP_AUTHORIZATION' not in request.META:
                response = HttpResponse('Unauthorized', status=401)
                response['WWW-Authenticate'] = 'Basic realm="Attendance Area"'
                return response
            
            # Parse the Authorization header
            auth_header = request.META['HTTP_AUTHORIZATION']
            if not auth_header.startswith('Basic '):
                response = HttpResponse('Unauthorized', status=401)
                response['WWW-Authenticate'] = 'Basic realm="Attendance Area"'
                return response
            
            # Decode credentials
            try:
                encoded_credentials = auth_header[6:]  # Remove 'Basic '
                decoded_credentials = base64.b64decode(encoded_credentials).decode('utf-8')
                provided_username, provided_password = decoded_credentials.split(':', 1)
            except (ValueError, UnicodeDecodeError):
                response = HttpResponse('Unauthorized', status=401)
                response['WWW-Authenticate'] = 'Basic realm="Attendance Area"'
                return response
            
            # Check credentials
            if username is None:
                # Only check password if username is None
                if provided_password == auth_password:
                    return func(request, *args, **kwargs)
            else:
                # Check both username and password
                if provided_username == username and provided_password == auth_password:
                    return func(request, *args, **kwargs)
            
            response = HttpResponse('Unauthorized', status=401)
            response['WWW-Authenticate'] = 'Basic realm="Attendance Area"'
            return response
        
        return wrapper
    return decorator


def http_basic_auth_birthdays():
    """
    Decorator for HTTP Basic Authentication for birthdays view
    Uses birthdays_password from SiteSettings
    If birthdays_password is None or empty, authentication is skipped
    """
    def decorator(func):
        @wraps(func)
        def wrapper(request, *args, **kwargs):
            # Get password from SiteSettings
            try:
                site_settings = SiteSettings.for_request(request)
                password = site_settings.birthdays_password
            except:
                password = None
            
            # If password is None or empty, skip authentication
            if not password:
                return func(request, *args, **kwargs)
            
            # Check if Authorization header exists
            if 'HTTP_AUTHORIZATION' not in request.META:
                response = HttpResponse('Unauthorized', status=401)
                response['WWW-Authenticate'] = 'Basic realm="Birthdays Area"'
                return response
            
            # Parse the Authorization header
            auth_header = request.META['HTTP_AUTHORIZATION']
            if not auth_header.startswith('Basic '):
                response = HttpResponse('Unauthorized', status=401)
                response['WWW-Authenticate'] = 'Basic realm="Birthdays Area"'
                return response
            
            # Decode credentials
            try:
                encoded_credentials = auth_header[6:]  # Remove 'Basic '
                decoded_credentials = base64.b64decode(encoded_credentials).decode('utf-8')
                provided_username, provided_password = decoded_credentials.split(':', 1)
            except (ValueError, UnicodeDecodeError):
                response = HttpResponse('Unauthorized', status=401)
                response['WWW-Authenticate'] = 'Basic realm="Birthdays Area"'
                return response
            
            # Only check password (any username is accepted)
            if provided_password == password:
                return func(request, *args, **kwargs)
            
            response = HttpResponse('Unauthorized', status=401)
            response['WWW-Authenticate'] = 'Basic realm="Birthdays Area"'
            return response
        
        return wrapper
    return decorator


def _get_form_recipients(site_settings, form_type):
    """Get recipients for a specific form type."""
    recipient_mapping = {
        'contact_form': site_settings.contact_form_email_recipients,
        'join_band_form': site_settings.join_band_form_email_recipients,
        'booking_form': site_settings.booking_form_email_recipients,
        'feedback_form': site_settings.feedback_form_email_recipients,
        'donate_form': site_settings.donate_form_email_recipients,
    }
    return recipient_mapping.get(form_type)


def _validate_honeypot(request):
    """Validate honeypot field."""
    honeypot = request.POST.get('best_color')
    return honeypot == 'purple'


def _send_form_email(subject, message, recipient_list):
    """Send email for form submission."""
    send_mail(
        subject=subject,
        message=message,
        from_email='info@blowcomotion.org',
        recipient_list=recipient_list,
        fail_silently=False,
    )


def _create_email_message(form_type, name, email, **kwargs):
    """Create email message based on form type."""
    messages = {
        'contact_form': {
            'greeting': f'Hello {name},\n\n',
            'intro': 'Thank you for contacting us! We have received your message:\n\n',
            'fields': f'Name: {name}\nEmail: {email}\nMessage: {kwargs.get("message", "")}\n\n',
            'closing': 'We will get back to you soon.\n\n',
        },
        'join_band_form': {
            'greeting': f'Hello {name},\n\n',
            'intro': 'Thank you for your interest in joining our band! We have received your application with the following details:\n\n',
            'fields': f'Name: {name}\nEmail: {email}\nInstrument: {kwargs.get("instrument", "")}\nInstrument Rental: {kwargs.get("instrument_rental", "")}\n' + (f'Message: {kwargs.get("message", "")}\n' if kwargs.get("message") else ''),
            'closing': '\nWe will review your application and get back to you soon.\n\n',
        },
        'booking_form': {
            'greeting': f'Hello {name},\n\n',
            'intro': 'Thank you for your interest in booking Blowcomotion! We have received your booking request with the following details:\n\n',
            'fields': f'Name: {name}\nEmail: {email}\nEvent Details: {kwargs.get("message", "")}\n\n',
            'closing': 'We will review your request and get back to you soon with availability and pricing information.\n\n',
        },
        'donate_form': {
            'greeting': f'Hello {name},\n\n',
            'intro': 'Thank you for your interest in supporting Blowcomotion! We have received your donation information:\n\n',
            'fields': f'Name: {name}\nEmail: {email}\n' + (f'Message: {kwargs.get("message", "")}\n' if kwargs.get("message") else ''),
            'closing': 'We will get back to you soon with information about donation options and how your support helps our band.\n\n',
        },
        'feedback_form': {
            'greeting': f'Hello {name},\n\n',
            'intro': 'Thank you for your feedback! We have received your message:\n\n',
            'fields': f'Name: {name}\n' + (f'Email: {email}\n' if email else '') + f'Message: {kwargs.get("message", "")}\n' + (f'Page URL: {kwargs.get("page_url", "")}\n' if kwargs.get("page_url") else ''),
            'closing': 'We will get back to you soon.\n\n',
        }
    }
    
    msg_parts = messages.get(form_type, {})
    email_message = f'{form_type.replace("_", " ").title()} Received\n\n'
    email_message += msg_parts.get('greeting', '')
    email_message += msg_parts.get('intro', '')
    email_message += msg_parts.get('fields', '')
    email_message += msg_parts.get('closing', '')
    email_message += 'Start Wearing Purple,\nBlowcomotion'
    
    return email_message


def _get_success_message(form_type):
    """Get success message based on form type."""
    messages = {
        'contact_form': "Contact form submitted successfully! We'll get back to you soon.",
        'join_band_form': "Join band application submitted successfully! We'll review your application and get back to you soon.",
        'booking_form': "Booking request submitted successfully! We'll review your request and get back to you soon with availability and pricing.",
        'donate_form': "Donation information submitted successfully! We'll get back to you soon with details about how you can support our band.",
        'feedback_form': "Feedback form submitted successfully! Thank you for your feedback.",
    }
    return messages.get(form_type, "Form submitted successfully!")


def _process_form_submission(request, form_type, form_data, submission_model):
    """Process form submission with common logic."""
    site_settings = SiteSettings.for_request(request=request)
    recipients = _get_form_recipients(site_settings, form_type)
    
    # Check recipients
    if not recipients and form_type != 'feedback_form':  # Feedback form can work without recipients
        logger.error(f"No recipients specified for the {form_type}. Submission by user {request.user.username} failed.")
        return {
            'error': f'No recipients specified for the {form_type.replace("_", " ")}. Add them in the admin settings.',
            'template': 'forms/error.html'
        }
    
    logger.info(f"Processing {form_type} submission by user {request.user.username}")
    
    try:
        # Save submission to database
        submission = submission_model(**form_data)
        submission.save()
        logger.info(f"{form_type} submission saved successfully for user {request.user.username}")
        
        # Send email if recipients are configured
        if recipients or (form_type == 'feedback_form' and form_data.get('email')):
            email_message = _create_email_message(form_type, **form_data)
            subject = f'{form_type.replace("_", " ").title()} Submission'
            
            # Build complete recipient list
            recipient_list = []
            if recipients:
                recipient_list.extend([email.strip() for email in recipients.split(',')])
            if form_data.get('email'):
                recipient_list.append(form_data['email'])
            
            if recipient_list:
                _send_form_email(subject, email_message, recipient_list)
                logger.info(f"Email sent successfully for {form_type} submission by user {request.user.username}")
        
        return {
            'message': _get_success_message(form_type),
            'template': 'forms/post_process.html'
        }
        
    except Exception as e:
        logger.error(f"Error processing {form_type} submission by user {request.user.username}: {str(e)}")
        return {
            'error': f'Error processing form: {str(e)}',
            'template': 'forms/error.html'
        }


def dump_data(request):
    # Create an in-memory string buffer to capture the output
    output = StringIO()

    # Arguments for `dumpdata`
    args = [
        '--natural-primary', '--natural-foreign', '--indent', '2',
        '-e', 'contenttypes', '-e', 'auth.permission', 
        '-e', 'wagtailcore.groupcollectionpermission', '-e', 'wagtailcore.grouppagepermission', '-e', 'wagtailcore.referenceindex', 
        '-e', 'wagtailimages.rendition', '-e', 'sessions', '-e', 'wagtailsearch', '-e', 'wagtailcore.pagelogentry', '-e', 'wagtailcore.revision', '-e', 'wagtailcore.taskstate', '-e', 'wagtailcore.workflowstate'
    ]
    # Check if the user is superuser
    if not request.user.is_superuser:
        logger.warning(f"Unauthorized access attempt to dump_data by user {request.user.username}")
        return JsonResponse({'error': 'You must be a superuser to access this feature'}, status=403)

    try:
        logger.info(f"Starting data dump by user {request.user.username}")
        # Use call_command to execute `dumpdata` and capture the output in the StringIO buffer
        call_command('dumpdata', *args, stdout=output)

        # Get the content of the buffer and parse it as JSON
        output_content = output.getvalue()
        data = json.loads(output_content)

        logger.info(f"Data dump completed successfully by user {request.user.username}")
        # Return the data as a JSON response with pretty formatting
        return JsonResponse(data, safe=False, json_dumps_params={'indent': 2})

    except Exception as e:
        logger.error(f"Error during data dump by user {request.user.username}: {str(e)}")
        # If something goes wrong, return an error message
        return JsonResponse({'error': str(e)}, status=500)
    

def process_form(request):
    """
    Process the form submission.
    """
    context = {}
    honeypot_message = 'Honeypot triggered. Form submission failed. Is your javascript enabled?'
    
    if request.method == 'POST':
        # Validate honeypot field
        if not _validate_honeypot(request):
            logger.warning(f"Honeypot triggered by user {request.user.username}")
            context['error'] = honeypot_message
            return render(request, 'forms/error.html', context)
        
        form_type = request.POST.get('form_type')
        
        # Define form configurations
        form_configs = {
            'contact_form': {
                'required_fields': ['name', 'email', 'message'],
                'model': ContactFormSubmission,
                'field_mapping': lambda req: {
                    'name': req.POST.get('name'),
                    'email': req.POST.get('email'),
                    'message': req.POST.get('message'),
                    'newsletter_opt_in': req.POST.get('newsletter', False) == 'yes',
                }
            },
            'join_band_form': {
                'required_fields': ['name', 'email', 'instrument', 'instrument_rental'],
                'model': JoinBandFormSubmission,
                'field_mapping': lambda req: {
                    'name': req.POST.get('name'),
                    'email': req.POST.get('email'),
                    'instrument': req.POST.get('instrument'),
                    'instrument_rental': req.POST.get('instrument_rental'),
                    'message': req.POST.get('message'),
                    'newsletter_opt_in': req.POST.get('newsletter', False) == 'yes',
                }
            },
            'booking_form': {
                'required_fields': ['name', 'email', 'message'],
                'model': BookingFormSubmission,
                'field_mapping': lambda req: {
                    'name': req.POST.get('name'),
                    'email': req.POST.get('email'),
                    'message': req.POST.get('message'),
                    'newsletter_opt_in': req.POST.get('newsletter', False) == 'yes',
                }
            },
            'donate_form': {
                'required_fields': ['name', 'email'],
                'model': DonateFormSubmission,
                'field_mapping': lambda req: {
                    'name': req.POST.get('name'),
                    'email': req.POST.get('email'),
                    'message': req.POST.get('message'),
                    'newsletter_opt_in': req.POST.get('newsletter', False) == 'yes',
                }
            },
            'feedback_form': {
                'required_fields': ['name', 'message'],
                'model': FeedbackFormSubmission,
                'field_mapping': lambda req: {
                    'name': req.POST.get('name'),
                    'email': req.POST.get('email'),
                    'message': req.POST.get('message'),
                    'submitted_from_page': req.POST.get('page_url'),
                }
            }
        }
        
        # Process known form types
        if form_type in form_configs:
            config = form_configs[form_type]
            form_data = config['field_mapping'](request)
            
            # Validate required fields
            missing_fields = [field for field in config['required_fields'] if not form_data.get(field)]
            if missing_fields:
                logger.warning(f"Validation failed for {form_type} submission by user {request.user.username}. Missing fields: {missing_fields}")
                context['error'] = f'Required fields are missing: {", ".join(missing_fields)}.'
                return render(request, 'forms/error.html', context)
            
            # Process the form
            result = _process_form_submission(request, form_type, form_data, config['model'])
            context.update({k: v for k, v in result.items() if k in ['message', 'error']})
            return render(request, result['template'], context)
        
        else:
            # Handle unknown form types
            logger.info(f"Processing unknown form type submission by user {request.user.username}")
            if not _validate_honeypot(request):
                logger.warning(f"Honeypot triggered by user {request.user.username}")
                context['error'] = honeypot_message
                return render(request, 'forms/error.html', context)
            context['message'] = 'Form submitted successfully!'
    
    else:
        logger.info(f"Form submission accessed with GET method by user {request.user.username}")

    return render(request, 'forms/post_process.html', context)


# Attendance Views


@http_basic_auth()
def attendance_capture(request, section_slug=None):
    """View for capturing attendance for a specific section"""
    sections = Section.objects.all().order_by('name')
    section = None
    is_no_section = False
    
    if section_slug:
        if section_slug == 'no-section':
            is_no_section = True
        else:
            section = get_object_or_404(Section, name__iexact=section_slug.replace('-', ' '))
    
    # Get section members for display grouped by instrument
    section_members = []
    members_by_instrument = {}
    
    if is_no_section:
        # Get members who don't have a primary instrument
        section_members = Member.objects.filter(
            is_active=True,
            primary_instrument__isnull=True
        ).order_by('first_name', 'last_name')
    elif section:
        # Get instruments that belong to this section
        section_instruments = Instrument.objects.filter(section=section).order_by('name')
        
        # Group members by their primary instrument only
        for instrument in section_instruments:
            members_for_instrument = Member.objects.filter(
                primary_instrument=instrument,
                is_active=True
            ).order_by('first_name', 'last_name')
            
            if members_for_instrument.exists():
                members_by_instrument[instrument] = members_for_instrument
        
        # Also get all section members (those with primary instrument in this section)
        section_members = Member.objects.filter(
            primary_instrument__in=section_instruments,
            is_active=True
        ).distinct().order_by('first_name', 'last_name')
    
    if request.method == 'POST':
        attendance_date_str = request.POST.get('attendance_date', date.today().strftime('%Y-%m-%d'))
        event_type = request.POST.get('event_type', 'rehearsal')
        gig_id = request.POST.get('gig', '').strip()
        event_notes = request.POST.get('event_notes', '').strip()
        
        # Get gig information if a gig is selected
        gig_title = None
        if gig_id:
            gig_data = make_gigo_api_request(f"/gigs/{gig_id}")
            if gig_data:
                gig_title = gig_data.get('title', 'Unknown Gig')
        
        # Store form data in session for persistence
        request.session['attendance_form_data'] = {
            'attendance_date': attendance_date_str,
            'event_type': event_type,
            'gig': gig_id,
            'event_notes': event_notes
        }
        
        # Convert string to date object for consistent handling
        if isinstance(attendance_date_str, str):
            attendance_date = datetime.strptime(attendance_date_str, '%Y-%m-%d').date()
        else:
            attendance_date = attendance_date_str
        
        # Create notes based on event type, gig, and custom notes
        if event_type == 'performance' and gig_title:
            event_notes_for_record = f"Performance: {gig_title}"
        elif event_type == 'performance' and event_notes:
            event_notes_for_record = f"Performance: {event_notes}"
        elif event_type == 'rehearsal' and event_notes:
            event_notes_for_record = f"Rehearsal: {event_notes}"
        elif event_notes:
            event_notes_for_record = event_notes
        else:
            event_notes_for_record = event_type.capitalize()
        
        success_count = 0
        errors = []
        
        # Process member attendance
        for member in section_members:
            checkbox_name = f'member_{member.id}'
            if checkbox_name in request.POST:
                try:
                    # Create or update attendance record
                    attendance_record, created = AttendanceRecord.objects.get_or_create(
                        date=attendance_date,
                        member=member,
                        defaults={'notes': event_notes_for_record}
                    )
                    if created:
                        success_count += 1
                    else:
                        # Update existing record to append event type in notes if not already present
                        if not attendance_record.notes:
                            attendance_record.notes = event_notes_for_record
                            attendance_record.save()
                        else:
                            # Only append event_notes_for_record if it's not already present as a full entry
                            notes_entries = [entry.strip() for entry in attendance_record.notes.split(';') if entry.strip()]
                            if event_notes_for_record not in notes_entries:
                                notes_entries.append(event_notes_for_record)
                                attendance_record.notes = '; '.join(notes_entries)
                                attendance_record.save()
                    
                    # Update member's last_seen field
                    member.last_seen = attendance_date
                    
                    # Update member's join_date if it hasn't been set yet and set is_active to True if it's False
                    fields_to_update = ['last_seen']
                    if not member.join_date:
                        member.join_date = attendance_date
                        fields_to_update.append('join_date')
                    if not member.is_active:
                        member.is_active = True
                        fields_to_update.append('is_active')
                    
                    member.save(update_fields=fields_to_update)
                except Exception as e:
                    errors.append(f"Error recording attendance for {member}: {str(e)}")
        
        # Also process any additional member IDs that might not be in section_members (e.g., inactive members)
        processed_member_ids = {member.id for member in section_members}
        for field_name, field_value in request.POST.items():
            if field_name.startswith('member_') and field_value == 'on':
                try:
                    member_id = int(field_name.split('_')[1])
                    if member_id not in processed_member_ids:
                        # This is a member not in section_members (probably inactive)
                        member = Member.objects.get(id=member_id)
                        
                        # Create or update attendance record
                        attendance_record, created = AttendanceRecord.objects.get_or_create(
                            date=attendance_date,
                            member=member,
                            defaults={'notes': event_notes_for_record}
                        )
                        if created:
                            success_count += 1
                        else:
                            # Update existing record to append event type in notes if not already present
                            if not attendance_record.notes:
                                attendance_record.notes = event_notes_for_record
                                attendance_record.save()
                            else:
                                # Only append event_notes_for_record if it's not already present as a full entry
                                notes_entries = [entry.strip() for entry in attendance_record.notes.split(';') if entry.strip()]
                                if event_notes_for_record not in notes_entries:
                                    notes_entries.append(event_notes_for_record)
                                    attendance_record.notes = '; '.join(notes_entries)
                                    attendance_record.save()
                        
                        # Update member's last_seen field
                        member.last_seen = attendance_date
                        
                        # Update member's join_date if it hasn't been set yet and set is_active to True if it's False
                        fields_to_update = ['last_seen']
                        if not member.join_date:
                            member.join_date = attendance_date
                            fields_to_update.append('join_date')
                        if not member.is_active:
                            member.is_active = True
                            fields_to_update.append('is_active')
                        
                        member.save(update_fields=fields_to_update)
                except (ValueError, Member.DoesNotExist, Exception) as e:
                    errors.append(f"Error processing member ID {field_name}: {str(e)}")
        
        # Process guest attendance
        if section or is_no_section:
            # For no-section, use a special guest field name
            guest_field = f'guest_{section.id}' if section else 'guest_no_section'
            if guest_field in request.POST and request.POST[guest_field].strip():
                guest_names = [name.strip() for name in request.POST[guest_field].split('\n') if name.strip()]
                for guest_name in guest_names:
                    try:
                        guest_notes = f"Guest - {event_notes_for_record}"
                        AttendanceRecord.objects.get_or_create(
                            date=attendance_date,
                            guest_name=guest_name,
                            defaults={'notes': guest_notes}
                        )
                        success_count += 1
                    except Exception as e:
                        errors.append(f"Error recording guest attendance for {guest_name}: {str(e)}")
        
        # Return success message for HTMX requests
        # Get all records for this date to show in success message
        if section:
            # Get all records for this date and section
            todays_records = AttendanceRecord.objects.filter(
                date=attendance_date
            ).filter(
                Q(member__in=section_members) | Q(member__isnull=True)
            ).select_related('member', 'member__primary_instrument').order_by('member__first_name', 'member__last_name', 'guest_name')
        elif is_no_section:
            # Get all records for this date and no-section members
            todays_records = AttendanceRecord.objects.filter(
                date=attendance_date
            ).filter(
                Q(member__in=section_members) | Q(member__isnull=True)
            ).select_related('member', 'member__primary_instrument').order_by('member__first_name', 'member__last_name', 'guest_name')
        else:
            todays_records = AttendanceRecord.objects.filter(date=attendance_date).select_related('member', 'member__primary_instrument')
        
        context = {
            'success_count': success_count,
            'errors': errors,
            'attendance_date': attendance_date,
            'section': section,
            'is_no_section': is_no_section,
            'today': date.today(),
            'todays_records': todays_records
        }
        
        if request.headers.get('HX-Request'):
            return render(request, 'attendance/partials/capture_success.html', context)
        else:
            return render(request, 'attendance/capture_success.html', context)
    
    # Get persisted form values from session or query parameters
    form_data = request.session.get('attendance_form_data', {})
    
    # Check if date is being passed as a query parameter (for dynamic updates)
    query_date = request.GET.get('attendance_date')
    if query_date:
        attendance_date = query_date
        # Update session with the new date
        form_data['attendance_date'] = attendance_date
        request.session['attendance_form_data'] = form_data
    else:
        attendance_date = form_data.get('attendance_date', date.today().strftime('%Y-%m-%d'))
    
    event_type = form_data.get('event_type', 'rehearsal')
    gig = form_data.get('gig', '')
    event_notes = form_data.get('event_notes', '')
    
    # Get attendance records for the selected date to show checkmarks
    if isinstance(attendance_date, str):
        attendance_date_obj = datetime.strptime(attendance_date, '%Y-%m-%d').date()
    else:
        attendance_date_obj = attendance_date
    
    recorded_member_ids = set()
    if section_members:
        recorded_member_ids = set(
            AttendanceRecord.objects.filter(
                date=attendance_date_obj,
                member__in=section_members
            ).values_list('member_id', flat=True)
        )

    # Get gig choices for the current date using cached endpoint
    gig_choices = []
    date_str = None
    
    try:
        if isinstance(attendance_date, str):
            selected_date = datetime.strptime(attendance_date, '%Y-%m-%d').date()
            date_str = attendance_date
        else:
            selected_date = attendance_date
            date_str = attendance_date.strftime('%Y-%m-%d')
    except (ValueError, TypeError) as e:
        logger.warning("Invalid attendance_date format: %s, error: %s", attendance_date, e)
        # Use today's date as fallback
        selected_date = date.today()
        date_str = selected_date.strftime('%Y-%m-%d')
        
    # Create cache key for this date
    cache_key = f"gigs_for_date_{date_str}"
    
    # Check cache first
    cached_result = cache.get(cache_key)
    if cached_result is not None:
        gig_choices = cached_result.get('gigs', [])
    else:
        # If not cached, fetch from API and cache the result
        gigs_data = make_gigo_api_request("/gigs")
        if gigs_data and gigs_data.get("gigs"):
            # Filter gigs for the specific date
            for gig_item in gigs_data["gigs"]:
                if (gig_item.get("date") == date_str and 
                    gig_item.get("gig_status", "").lower() == "confirmed" and 
                    gig_item.get("band", "").lower() == "blowcomotion"):
                    gig_choices.append({
                        'id': gig_item.get('id'),
                        'title': gig_item.get('title', 'Untitled Gig'),
                        'date': gig_item.get('date'),
                    })
        
        # Cache the result for 10 minutes
        result = {'gigs': gig_choices}
        cache.set(cache_key, result, 600)
    
    context = {
        'section': section,
        'section_members': section_members,
        'members_by_instrument': members_by_instrument,
        'sections': sections,
        'is_no_section': is_no_section,
        'today': date.today(),
        'attendance_date': attendance_date,
        'event_type': event_type,
        'gig': gig,
        'event_notes': event_notes,
        'gig_choices': gig_choices,
        'recorded_member_ids': recorded_member_ids
    }
    
    # For HTMX section switching, return the main content including navigation
    if request.headers.get('HX-Request'):
        # Check if this is a date change request (has attendance_date parameter)
        if query_date and (section or is_no_section):
            # For date changes when a section is selected, return just the members section to update checkmarks
            return render(request, 'attendance/partials/members_section.html', context)
        else:
            # For section navigation or when no section is selected, return the full capture content
            return render(request, 'attendance/partials/capture_content.html', context)
    
    return render(request, 'attendance/capture.html', context)


@http_basic_auth()
@require_http_methods(["GET", "POST"])
def inactive_members(request):
    """View for managing inactive members - display list with reactivation buttons"""
    
    # Get all inactive members
    inactive_members_list = Member.objects.filter(is_active=False).order_by('first_name', 'last_name')
    
    # Handle POST requests for member reactivation
    if request.method == 'POST':
        member_id = request.POST.get('member_id')
        if member_id:
            try:
                member = Member.objects.get(id=member_id, is_active=False)
                member.is_active = True
                member.save(update_fields=['is_active'])
                
                # Return success message for HTMX requests
                context = {
                    'message': f'Successfully reactivated {member.first_name} {member.last_name}',
                    'reactivated_member': member,
                    'sections': Section.objects.all().order_by('name')  # Add sections for navigation
                }
                
                if request.headers.get('HX-Request'):
                    # Refresh the inactive members list after reactivation
                    inactive_members_list = Member.objects.filter(is_active=False).order_by('first_name', 'last_name')
                    context['inactive_members'] = inactive_members_list
                    return render(request, 'attendance/partials/inactive_members_content.html', context)
                else:
                    context['inactive_members'] = inactive_members_list
                    return render(request, 'attendance/inactive_members.html', context)
                    
            except Member.DoesNotExist:
                context = {
                    'error': 'Member not found or already active',
                    'inactive_members': inactive_members_list,
                    'sections': Section.objects.all().order_by('name')  # Add sections for navigation
                }
                
                if request.headers.get('HX-Request'):
                    return render(request, 'attendance/partials/inactive_members_content.html', context)
                else:
                    return render(request, 'attendance/inactive_members.html', context)
            except Exception as e:
                context = {
                    'error': f'Error reactivating member: {str(e)}',
                    'inactive_members': inactive_members_list,
                    'sections': Section.objects.all().order_by('name')  # Add sections for navigation
                }
                
                if request.headers.get('HX-Request'):
                    return render(request, 'attendance/partials/inactive_members_content.html', context)
                else:
                    return render(request, 'attendance/inactive_members.html', context)
    
    # GET request - display inactive members list
    context = {
        'inactive_members': inactive_members_list,
        'sections': Section.objects.all().order_by('name')  # For navigation
    }
    
    # For HTMX requests, return just the content
    if request.headers.get('HX-Request'):
        return render(request, 'attendance/partials/inactive_members_content.html', context)
    
    return render(request, 'attendance/inactive_members.html', context)


@http_basic_auth()
def attendance_reports(request):
    """View for attendance reports - overall summary"""
    filter_form = AttendanceReportFilterForm(request.GET or None)
    
    # Get filter parameters
    start_date = request.GET.get('start_date')
    end_date = request.GET.get('end_date')
    section_id = request.GET.get('section')
    member_id = request.GET.get('member')
    
    # Build query
    attendance_records = AttendanceRecord.objects.all()
    
    if start_date:
        attendance_records = attendance_records.filter(date__gte=start_date)
    if end_date:
        attendance_records = attendance_records.filter(date__lte=end_date)
    
    if member_id:
        attendance_records = attendance_records.filter(member_id=member_id)
    
    if section_id:
        section = Section.objects.get(id=section_id)
        # Get members whose primary instrument is in this section
        section_member_ids = Member.objects.filter(
            primary_instrument__section=section
        ).values_list('id', flat=True)
        attendance_records = attendance_records.filter(
            Q(member_id__in=section_member_ids) | Q(member__isnull=True)
        )
    
    # Get summary statistics
    total_records = attendance_records.count()
    member_records = attendance_records.filter(member__isnull=False).count()
    guest_records = attendance_records.filter(guest_name__isnull=False).count()
    
    # Group by date
    attendance_by_date = attendance_records.values('date').annotate(
        member_count=Count('member', filter=Q(member__isnull=False)),
        guest_count=Count('guest_name', filter=Q(guest_name__isnull=False)),
        total_count=Count('id')
    ).order_by('-date')
    
    # Get sections for navigation
    sections = Section.objects.all().order_by('name')
    
    context = {
        'filter_form': filter_form,
        'attendance_records': attendance_records.select_related('member', 'member__primary_instrument').order_by('-date', 'member__first_name', 'member__last_name')[:100],  # Limit for performance
        'attendance_by_date': attendance_by_date,
        'total_records': total_records,
        'member_records': member_records,
        'guest_records': guest_records,
        'sections': sections
    }
    
    # For HTMX filter requests, return just the filtered content
    if request.headers.get('HX-Request'):
        # Check if this is a filter request vs navigation request
        if any(param in request.GET for param in ['start_date', 'end_date', 'section', 'member']):
            return render(request, 'attendance/partials/reports_content.html', context)
        else:
            return render(request, 'attendance/partials/all_reports_content.html', context)
    
    return render(request, 'attendance/reports.html', context)

@http_basic_auth()
def attendance_section_report_new(request, section_slug):
    """View for attendance reports for a specific section"""
    section = get_object_or_404(Section, name__iexact=section_slug.replace('-', ' '))
    
    # Get date range (default to last 12 weeks)
    end_date = date.today()
    start_date = end_date - timedelta(weeks=12)
    
    if request.GET.get('start_date'):
        start_date = date.fromisoformat(request.GET.get('start_date'))
    if request.GET.get('end_date'):
        end_date = date.fromisoformat(request.GET.get('end_date'))
    
    # Get members in this section (those with primary instrument in this section)
    section_members = Member.objects.filter(
        primary_instrument__section=section,
        is_active=True
    ).order_by('first_name', 'last_name')
    
    section_member_ids = list(section_members.values_list('id', flat=True))
    
    # Get attendance records for this section (filter by members in this section)
    attendance_records = AttendanceRecord.objects.filter(
        date__gte=start_date,
        date__lte=end_date
    ).filter(
        Q(member_id__in=section_member_ids) | Q(member__isnull=True)
    ).order_by('-date')
    
    # Calculate member attendance percentages
    member_attendance = {}
    for member in section_members:
        member_records = attendance_records.filter(member=member)
        
        # Calculate Tuesdays in the period for this member
        member_tuesdays = 0
        current_date = max(start_date, member.join_date) if member.join_date else start_date
        while current_date <= end_date:
            if current_date.weekday() == 1:  # Tuesday
                member_tuesdays += 1
            current_date += timedelta(days=1)
        
        attendance_percentage = (member_records.count() / member_tuesdays * 100) if member_tuesdays > 0 else 0
        member_attendance[member] = {
            'count': member_records.count(),
            'total_tuesdays': member_tuesdays,
            'percentage': round(attendance_percentage, 1)
        }
    
    # Group attendance by date
    attendance_by_date = attendance_records.values('date').annotate(
        member_count=Count('member', filter=Q(member__isnull=False)),
        guest_count=Count('guest_name', filter=Q(guest_name__isnull=False)),
        total_count=Count('id')
    ).order_by('-date')
    
    context = {
        'section': section,
        'section_members': section_members,
        'attendance_records': attendance_records.select_related('member', 'member__primary_instrument'),
        'member_attendance': member_attendance,
        'attendance_by_date': attendance_by_date,
        'start_date': start_date,
        'end_date': end_date
    }
    
    # For HTMX requests, return just the content
    if request.headers.get('HX-Request'):
        return render(request, 'attendance/partials/section_report_content.html', context)
    
    return render(request, 'attendance/section_report.html', context)


@http_basic_auth_birthdays()
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


@http_basic_auth()
def gigs_for_date(request):
    """API endpoint to get gigs for a specific date"""
    date_str = request.GET.get('date')
    if not date_str:
        return JsonResponse({'error': 'Date parameter is required'}, status=400)
    
    try:
        # Validate date format
        selected_date = datetime.strptime(date_str, '%Y-%m-%d').date()
        
        # Create cache key for this date
        cache_key = f"gigs_for_date_{date_str}"
        
        # Check cache first
        cached_result = cache.get(cache_key)
        if cached_result is not None:
            return JsonResponse(cached_result)
        
        # Fetch gigs from API
        gigs_data = make_gigo_api_request("/gigs")
        filtered_gigs = []
        
        if gigs_data and gigs_data.get("gigs"):
            # Filter gigs for the specific date and other criteria
            for gig in gigs_data["gigs"]:
                if (gig.get("date") == date_str and 
                    gig.get("gig_status", "").lower() == "confirmed" and 
                    gig.get("band", "").lower() == "blowcomotion"):
                    filtered_gigs.append({
                        'id': gig.get('id'),
                        'title': gig.get('title', 'Untitled Gig'),
                        'date': gig.get('date'),
                        'address': gig.get('address', '')
                    })
        
        result = {'gigs': filtered_gigs}
        
        # Cache the result for 10 minutes
        cache.set(cache_key, result, 600)
        
        return JsonResponse(result)
        
    except ValueError:
        return JsonResponse({'error': 'Invalid date format'}, status=400)
    except Exception as e:
        # Use the original date parameter from request if available, otherwise 'unknown'
        date_param = request.GET.get('date', 'unknown')
        logger.error("Unexpected error in gigs_for_date for date %s: %s", date_param, e, exc_info=True)
        return JsonResponse({'error': f'Error fetching gigs: {str(e)}'}, status=500)


def member_signup(request):
    """
    Handles new member signups by processing the MemberSignupForm, creating a Member instance,
    and sending notification emails to administrators.

    Parameters:
        request (HttpRequest): The HTTP request object, expected to be a GET or POST.

    Returns:
        HttpResponse: Renders the signup form on GET or after successful signup.
        JsonResponse: May return error details in case of form validation or other errors.

    Exceptions:
        Handles form validation errors, database errors, and email sending errors internally.
        Unexpected exceptions are logged and may result in a 500 error response.
    """
    context = {}
    
    if request.method == 'POST':
        form = MemberSignupForm(request.POST)
        
        if form.is_valid():
            try:
                # Create new member from form data
                member = Member(
                    first_name=form.cleaned_data['first_name'],
                    last_name=form.cleaned_data['last_name'],
                    preferred_name=form.cleaned_data.get('preferred_name') or None,
                    primary_instrument=form.cleaned_data.get('primary_instrument'),
                    birth_month=int(form.cleaned_data['birth_month']) if form.cleaned_data.get('birth_month') else None,
                    birth_day=form.cleaned_data.get('birth_day'),
                    birth_year=form.cleaned_data.get('birth_year'),
                    email=form.cleaned_data.get('email') or None,
                    phone=form.cleaned_data.get('phone') or None,
                    address=form.cleaned_data.get('address') or None,
                    city=form.cleaned_data.get('city') or None,
                    state=form.cleaned_data.get('state') or None,
                    zip_code=form.cleaned_data.get('zip_code') or None,
                    country=form.cleaned_data.get('country') or None,
                    emergency_contact=form.cleaned_data.get('emergency_contact') or None,
                    inspired_by=form.cleaned_data.get('inspired_by') or None,
                    is_active=False,  # New signups are inactive until approved by admin
                    instructor=False,
                    board_member=False,
                )
                
                member.save()
                logger.info(f"New member signup: {member.first_name} {member.last_name}")
                
                # Send email notification to admin
                site_settings = SiteSettings.for_request(request=request)
                recipients = site_settings.join_band_form_email_recipients
                
                if recipients:
                    recipient_list = [email.strip() for email in recipients.split(',')]
                    
                    # Build email message
                    email_message = f"""New Member Signup

A new member has signed up through the website:

Name: {member.first_name} {member.last_name}"""
                    
                    if member.preferred_name:
                        email_message += f"\nPreferred Name: {member.preferred_name}"
                    
                    # Show selected instrument
                    if form.cleaned_data.get('primary_instrument'):
                        email_message += f"\nInstrument: {form.cleaned_data['primary_instrument']}"
                    
                    if member.birthday_display:
                        email_message += f"\nBirthday: {member.birthday_display}"
                    
                    if member.email:
                        email_message += f"\nEmail: {member.email}"
                    
                    if member.phone:
                        email_message += f"\nPhone: {member.phone}"
                    
                    if member.address:
                        address_parts = [member.address]
                        if member.city:
                            address_parts.append(member.city)
                        if member.state:
                            address_parts.append(member.state)
                        if member.zip_code:
                            address_parts.append(member.zip_code)
                        if member.country:
                            address_parts.append(member.country)
                        email_message += f"\nAddress: {', '.join(address_parts)}"
                    
                    if member.emergency_contact:
                        email_message += f"\nEmergency Contact: {member.emergency_contact}"
                    
                    if member.inspired_by:
                        email_message += f"\n\nWhat inspired them to join:\n{member.inspired_by}"
                    
                    email_message += f"\n\nThe member has been created with inactive status. Please review and activate in the admin panel."
                    email_message += "\n\nStart Wearing Purple,\nBlowcomotion Website"
                    
                    _send_form_email(
                        subject='New Member Signup',
                        message=email_message,
                        recipient_list=recipient_list
                    )
                    logger.info(f"Member signup notification email sent for {member.first_name} {member.last_name}")
                
                # Send confirmation email to new member if they provided an email
                if member.email:
                    confirmation_message = f"""Hello {member.first_name},

Thank you for signing up with Blowcomotion! We've received your information and will review your application soon.

We'll be in touch with next steps about joining the band.

Start Wearing Purple,
Blowcomotion"""
                    
                    _send_form_email(
                        subject='Welcome to Blowcomotion - Application Received',
                        message=confirmation_message,
                        recipient_list=[member.email]
                    )
                
                context['message'] = 'Thank you for signing up! We have received your information and will be in touch soon.'
                return render(request, 'member_signup_success.html', context)
                
            except Exception as e:
                logger.error(f"Error processing member signup: {str(e)}", exc_info=True)
                context['error'] = f'Error processing signup: {str(e)}'
                context['form'] = form
                return render(request, 'member_signup.html', context)
        else:
            # Form validation errors
            context['form'] = form
            context['error'] = 'Please correct the errors below.'
            return render(request, 'member_signup.html', context)
    
    else:
        # GET request - display empty form
        form = MemberSignupForm()
        context['form'] = form
        return render(request, 'member_signup.html', context)