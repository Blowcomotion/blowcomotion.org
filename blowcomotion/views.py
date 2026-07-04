import json
import logging
import os
import tempfile
from collections import defaultdict
from datetime import date, datetime, timedelta
from io import StringIO

import requests

from django.conf import settings
from django.contrib.auth.decorators import login_required, permission_required
from django.contrib.auth.forms import AuthenticationForm, UserCreationForm
from django.core.management import call_command
from django.http import HttpResponse, JsonResponse
from django.shortcuts import render
from django.utils import timezone
from django.views.decorators.http import require_http_methods

from blowcomotion.forms import MemberSignupForm
from blowcomotion.member_auth import (
    _MemberEmail,
    create_member_user,
    send_member_signup_welcome_email,
)
from blowcomotion.member_forms import _yesno_to_bool
from blowcomotion.models import (
    BookingFormSubmission,
    ContactFormSubmission,
    DonateFormSubmission,
    FeedbackFormSubmission,
    JoinBandFormSubmission,
    Member,
    SiteSettings,
)
from blowcomotion.utils import send_member_to_go3_band_invite

logger = logging.getLogger(__name__)

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


def _get_form_recipients(site_settings, form_type):
    """Get recipients for a specific form type."""
    recipient_mapping = {
        'contact_form': site_settings.contact_form_email_recipients,
        'join_band_form': site_settings.join_band_form_email_recipients,
        'booking_form': site_settings.booking_form_email_recipients,
        'feedback_form': site_settings.feedback_form_email_recipients,
        'donate_form': site_settings.donate_form_email_recipients,
        'member_signup_form': site_settings.member_signup_notification_recipients,
    }
    return recipient_mapping.get(form_type)


def _validate_recaptcha(request):
    """
    Validate reCAPTCHA v3 token from the request.
    
    Returns:
        tuple: (is_valid: bool, error_message: str or None)
    """
    # If reCAPTCHA is not configured (no keys), skip validation in dev, fail in production
    if not getattr(settings, 'RECAPTCHA_PUBLIC_KEY', None) or not getattr(settings, 'RECAPTCHA_PRIVATE_KEY', None):
        if settings.DEBUG:
            logger.debug("reCAPTCHA validation skipped - no keys configured")
            return True, None
        else:
            logger.error("reCAPTCHA keys not configured in production - rejecting form submission")
            return False, "reCAPTCHA verification failed. Please try again."
    
    recaptcha_token = request.POST.get('g-recaptcha-response')
    
    if not recaptcha_token:
        logger.warning("reCAPTCHA token missing from form submission")
        return False, "reCAPTCHA verification failed. Please try again."
    
    # Verify the token with Google's reCAPTCHA API
    try:
        response = requests.post(
            'https://www.google.com/recaptcha/api/siteverify',
            data={
                'secret': settings.RECAPTCHA_PRIVATE_KEY,
                'response': recaptcha_token,
                'remoteip': request.META.get('REMOTE_ADDR'),
            },
            timeout=10,
        )
        response.raise_for_status()
        
        try:
            result = response.json()
        except ValueError:
            logger.warning("reCAPTCHA verification returned a non-JSON response")
            return False, "reCAPTCHA verification failed. Please try again."
        
        if not result.get('success'):
            error_codes = result.get('error-codes', [])
            logger.warning(f"reCAPTCHA verification failed: {error_codes}")
            return False, "reCAPTCHA verification failed. Please try again."
        
        # Validate action matches what we expect (prevents token reuse across contexts)
        action = result.get('action')
        if action != 'submit':
            logger.warning(f"reCAPTCHA action mismatch: {action!r} (expected: 'submit')")
            return False, "reCAPTCHA verification failed. Please try again."
        
        # Check score for v3 - fail closed if score is missing (unexpected for v3 keys)
        score = result.get('score')
        required_score = getattr(settings, 'RECAPTCHA_REQUIRED_SCORE', 0.5)
        
        if score is None:
            logger.warning("reCAPTCHA v3 score missing from response - possible key mismatch")
            return False, "reCAPTCHA verification failed. Please try again."
        
        if score < required_score:
            logger.warning(f"reCAPTCHA score too low: {score} (required: {required_score})")
            return False, "reCAPTCHA verification failed. Please try again."
        
        logger.debug(f"reCAPTCHA validation successful (score: {score})")
        return True, None
        
    except requests.RequestException as e:
        logger.error(f"reCAPTCHA API request failed: {e}")
        # On API failure, fail closed for security
        return False, "reCAPTCHA verification failed. Please try again."


def _send_form_email(subject, message, recipient_list):
    """Send email for form submission."""
    _MemberEmail(
        subject=subject, body=message, from_email=settings.FROM_EMAIL, to=recipient_list
    ).send(fail_silently=False)


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
            'fields': (
                f'Name: {name}\n'
                f'Email: {email}\n'
                + (f'Event Date: {kwargs.get("event_date", "Not provided")}\n' if kwargs.get("event_date") else '')
                + (f'Event Time: {kwargs.get("event_time", "Not provided")}\n' if kwargs.get("event_time") else '')
                + (f'Event Location: {kwargs.get("event_location", "Not provided")}\n' if kwargs.get("event_location") else '')
                + (f'Duration: {kwargs.get("duration", "Not provided")}\n' if kwargs.get("duration") else '')
                + (f'Expected Guests: {kwargs.get("expected_guests", "Not provided")}\n' if kwargs.get("expected_guests") else '')
                + (f'Budget: {kwargs.get("budget", "Not provided")}\n' if kwargs.get("budget") else '')
                + (f'\nEvent Details:\n{kwargs.get("event_details", "Not provided")}\n' if kwargs.get("event_details") else '')
                + (f'\nAdditional Comments:\n{kwargs.get("message", "")}\n' if kwargs.get("message") else '')
                + '\n'
            ),
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


def _process_member_signup(request, form_data):
    """
    Process member signup submission with member creation and GO3 integration.
    
    Args:
        request: The HTTP request object
        form_data: Dictionary containing form submission data
        
    Returns:
        Dictionary with 'message' and 'template' on success, or 'error' and 'template' on failure
    """
    site_settings = SiteSettings.for_request(request=request)
    recipients = site_settings.member_signup_notification_recipients
    
    logger.info(f"Processing member signup submission by user {request.user.username}")
    
    try:
        primary_instrument = form_data.get('primary_instrument')  # Already an Instrument object from MemberSignupForm

        # Check for duplicate email before attempting to create a member.
        # Email is the login identifier, so a match means the person already has an account.
        email = form_data.get('email')
        if email and Member.objects.filter(email__iexact=email).exists():
            logger.info(f"Member signup rejected: email already registered ({email})")
            return {
                'template': 'forms/signup_duplicate_email.html',
            }

        # Create new member from form data
        member = Member(
            first_name=form_data['first_name'],
            last_name=form_data['last_name'],
            preferred_name=form_data.get('preferred_name') or None,
            primary_instrument=primary_instrument,
            birth_month=int(form_data['birth_month']) if form_data.get('birth_month') else None,
            birth_day=int(form_data['birth_day']) if form_data.get('birth_day') else None,
            birth_year=int(form_data['birth_year']) if form_data.get('birth_year') else None,
            email=form_data.get('email') or None,
            phone=form_data.get('phone') or None,
            address=form_data.get('address') or None,
            city=form_data.get('city') or None,
            state=form_data.get('state') or None,
            zip_code=form_data.get('zip_code') or None,
            country=form_data.get('country') or None,
            emergency_contact=form_data.get('emergency_contact') or None,
            inspired_by=form_data.get('inspired_by') or None,
            shirt_size=form_data.get('shirt_size') or '',
            dietary_preferences=form_data.get('dietary_preferences') or [],
            dietary_other=form_data.get('dietary_other') or '',
            has_allergies=_yesno_to_bool(form_data.get('has_allergies')),
            allergens=form_data.get('allergens') or [],
            allergens_other=form_data.get('allergens_other') or '',
            has_epipen=_yesno_to_bool(form_data.get('has_epipen')),
            allergy_details=form_data.get('allergy_details') or '',
            medical_notes=form_data.get('medical_notes') or '',
            is_active=True,
            instructor=False,
            board_member=False,
            join_date=date.today()
        )
        try:
            member.full_clean()
        except Exception as e:
            logger.error(f"Validation error creating member: {str(e)}")
            return {
                'error': f'Error validating member data: {str(e)}',
                'template': 'forms/error.html'
            }
        member.save()
        logger.info(f"New member signup: {member.first_name} {member.last_name}")
        
        # Send invitation to GO3 band if email is provided
        if member.email:
            try:
                go3_result = send_member_to_go3_band_invite(
                    member.email,
                    use_local_band=settings.DEBUG  # Use local band in dev, production band in production
                )
                
                if go3_result['status'] == 'success':
                    logger.info(f"GO3 band invite result: {go3_result['message']}")
                else:
                    # Log the error but don't fail the signup
                    logger.warning(f"GO3 band invite failed: {go3_result['message']}")
            except Exception as e:
                # Log the error but don't fail the signup
                logger.warning(f"Error sending GO3 band invite: {str(e)}")

        # Create a User account and send welcome email with set-password link and next steps
        if member.email:
            try:
                create_member_user(member)
                send_member_signup_welcome_email(member, f"{request.scheme}://{request.get_host()}")
                logger.info(f"Sent signup welcome email to new member {member.pk}")
            except Exception as e:
                logger.warning(f"Could not send welcome email to new member {member.pk}: {e}")

        # Send email notification to admin
        if recipients:
            try:
                recipient_list = [email.strip() for email in recipients.split(',')]
                
                # Build email message
                email_message = f"""New Member Signup

A new member has signed up through the website:

Name: {member.first_name} {member.last_name}"""
                
                if member.preferred_name:
                    email_message += f"\nPreferred Name: {member.preferred_name}"
                
                if primary_instrument:
                    email_message += f"\nInstrument: {primary_instrument.name}"
                
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

                if member.shirt_size:
                    email_message += f"\n\nShirt Size: {member.shirt_size}"

                if member.dietary_preferences:
                    prefs = ', '.join(member.dietary_preferences)
                    email_message += f"\nDietary Preferences: {prefs}"
                    if member.dietary_other:
                        email_message += f"\nDietary Other: {member.dietary_other}"

                if member.has_allergies is not None:
                    email_message += f"\nHas Allergies: {'Yes' if member.has_allergies else 'No'}"
                    if member.has_allergies and member.allergens:
                        allergens_list = ', '.join(member.allergens)
                        email_message += f"\nAllergens: {allergens_list}"
                        if member.allergens_other:
                            email_message += f"\nAllergens Other: {member.allergens_other}"

                if member.has_epipen is not None:
                    email_message += f"\nCarries Epi-Pen: {'Yes' if member.has_epipen else 'No'}"

                if member.allergy_details:
                    email_message += f"\nAllergy Details: {member.allergy_details}"

                email_message += "\n\nStart Wearing Purple,\nBlowcomotion Website"
                
                _send_form_email(
                    subject='New Member Signup',
                    message=email_message,
                    recipient_list=recipient_list
                )
                logger.info(f"Member signup notification email sent for {member.first_name} {member.last_name}")
            except Exception as e:
                logger.error(f"Error sending admin notification email: {str(e)}")
        else:
            logger.warning("No member signup notification recipients configured in site settings.")
        
        return {
            'message': 'Thank you for signing up! We have received your information and will be in touch soon. Please check your email for next steps.',
            'template': 'forms/post_process.html'
        }
        
    except Exception as e:
        logger.error(f"Error processing member signup: {str(e)}", exc_info=True)
        return {
            'error': f'Error processing signup: {str(e)}',
            'template': 'forms/error.html'
        }


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
        try:
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
        except Exception as e:
            logger.error(f"Error sending email for {form_type} submission by user {request.user.username}: {str(e)}")
        
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
    
    # Base arguments for `dumpdata`
    # Always exclude auth users and site settings (may contain credentials and other sensitive data)
    base_args = [
        '--natural-foreign', '--indent', '2',
        '-e', 'contenttypes', '-e', 'auth.permission',
        '-e', 'wagtailcore.groupcollectionpermission', '-e', 'wagtailcore.grouppagepermission', '-e', 'wagtailcore.referenceindex',
        '-e', 'sessions', '-e', 'wagtailsearch', '-e', 'wagtailcore.pagelogentry', '-e', 'wagtailcore.revision', '-e', 'wagtailcore.taskstate', '-e', 'wagtailcore.workflowstate', '-e', 'wagtailcore.comment',
        '-e', 'auth.user',
        '-e', 'admin.logentry', '-e', 'axes.accesslog',
        '-e', 'wagtailcore.modellogentry', '-e', 'wagtailcore.pagesubscription',
        '-e', 'wagtailadmin.editingsession', '-e', 'wagtailadmin.formstate',
        '-e', 'wagtailusers.userprofile',
    ]
    
    args = base_args

    has_dev_access = request.user.has_perm('blowcomotion.access_dev_tools')
    has_analyst_access = request.user.has_perm('blowcomotion.access_real_data_exports')

    if not (has_dev_access or has_analyst_access):
        logger.warning(f"Unauthorized access attempt to dump_data by user {request.user.username}")
        return JsonResponse({'error': 'You do not have permission to access this feature'}, status=403)

    # Real member data is scrubbed by default, except for analysts who get it
    # by default since they're already permitted to request it explicitly.
    # Pass ?include_real_data=false to force scrubbed output instead.
    include_real_data_param = request.GET.get('include_real_data')
    if include_real_data_param is None:
        include_real_data = has_analyst_access
    else:
        include_real_data = include_real_data_param.lower() == 'true'

    if include_real_data and not has_analyst_access:
        logger.warning(f"Unauthorized include_real_data access attempt to dump_data by user {request.user.username}")
        return JsonResponse({'error': 'You do not have permission to access real member data'}, status=403)

    try:
        logger.info(f"Starting data dump by user {request.user.username} (include_real_data={include_real_data})")
        # Use call_command to execute `dumpdata` and capture the output in the StringIO buffer
        call_command('dumpdata', *args, stdout=output)

        # Get the content of the buffer and parse it as JSON
        output_content = output.getvalue()
        data = json.loads(output_content)

        # Replace all latest_revision and live_revision fields with null to avoid issues when loading data into a different database
        for item in data:
            if 'fields' in item:
                if 'latest_revision' in item['fields']:
                    item['fields']['latest_revision'] = None
                if 'live_revision' in item['fields']:
                    item['fields']['live_revision'] = None

        # Clear user FKs that would otherwise reference excluded `auth.user` records
        # (e.g. wagtailimages.Image.uploaded_by_user, LibraryInstrument.locked_by, InstrumentHistoryLog.user)
        user_fk_field_names = {'uploaded_by_user', 'user', 'locked_by', 'owner'}
        # Optional FileFields serialized as "" instead of null cause DeserializationError on load
        empty_string_file_fields = {'thumbnail', 'avatar'}
        for item in data:
            fields = item.get('fields')
            if not fields:
                continue
            for field_name in user_fk_field_names:
                if field_name in fields:
                    fields[field_name] = None
            for field_name in empty_string_file_fields:
                if fields.get(field_name) == '':
                    fields[field_name] = None

        # Scrub member data in-place if not including real data
        # This preserves Django's dependency ordering while scrubbing sensitive information
        if not include_real_data:
            # Build a mapping of member PKs to sequential indices for consistent fake data
            member_pks = sorted([item['pk'] for item in data if item.get('model') == 'blowcomotion.member'])
            member_pk_to_index = {pk: idx + 1 for idx, pk in enumerate(member_pks)}
            
            scrubbed_count = 0
            # Scrub member records in-place
            for item in data:
                if item.get('model') == 'blowcomotion.member':
                    member_pk = item['pk']
                    idx = member_pk_to_index[member_pk]
                    fields = item['fields']
                    
                    # Scrub sensitive fields while preserving structure and non-sensitive data
                    fields['first_name'] = f'FirstName{idx}'
                    fields['last_name'] = f'LastName{idx}'
                    fields['preferred_name'] = f'Preferred{idx}' if fields.get('preferred_name') else None
                    fields['email'] = f'member{idx}@example.com' if fields.get('email') else None
                    fields['phone'] = f'555-{idx:04d}' if fields.get('phone') else None
                    fields['address'] = f'{idx} Main Street' if fields.get('address') else None
                    fields['city'] = 'Austin' if fields.get('city') else None
                    fields['state'] = 'TX' if fields.get('state') else None
                    fields['zip_code'] = f'{idx:05d}' if fields.get('zip_code') else None
                    fields['country'] = 'USA' if fields.get('country') else None
                    fields['emergency_contact'] = f'Emergency Contact {idx}' if fields.get('emergency_contact') else None
                    fields['inspired_by'] = 'Scrubbed for privacy' if fields.get('inspired_by') else None
                    fields['bio'] = 'Scrubbed for privacy' if fields.get('bio') else None
                    fields['notes'] = 'Scrubbed for privacy' if fields.get('notes') else None
                    # Scrub GigoGig integration identifiers and member photos
                    fields['gigomatic_username'] = None
                    fields['gigomatic_id'] = None
                    fields['image'] = None
                    
                    scrubbed_count += 1
            
            logger.info(f'Scrubbed {scrubbed_count} member records in data dump')

        # Always scrub SiteSettings sensitive fields regardless of include_real_data
        sitesettings_recipients = {
            'contact_form_email_recipients', 'join_band_form_email_recipients',
            'booking_form_email_recipients', 'feedback_form_email_recipients',
            'donate_form_email_recipients', 'birthday_summary_email_recipients',
            'instrument_rental_notification_recipients',
            'attendance_report_notification_recipients',
            'member_signup_notification_recipients',
        }
        for item in data:
            if item.get('model') == 'blowcomotion.sitesettings':
                fields = item.get('fields', {})
                for field in sitesettings_recipients:
                    if field in fields:
                        fields[field] = 'local@example.com'

        logger.info(f"Data dump completed successfully by user {request.user.username}")
        # Return the data as a JSON response with pretty formatting
        # Mark as non-cacheable to prevent sensitive data from being stored by browsers/proxies
        response = JsonResponse(data, safe=False, json_dumps_params={'indent': 2})
        response['Cache-Control'] = 'no-store'
        return response

    except Exception as e:
        logger.error(f"Error during data dump by user {request.user.username}: {str(e)}")
        # If something goes wrong, return an error message
        return JsonResponse({'error': str(e)}, status=500)
    

def export_members_csv(request):
    if not request.user.has_perm('blowcomotion.access_real_data_exports'):
        logger.warning("Unauthorized access attempt to export members by user %s", request.user.username)
        return JsonResponse({'error': 'You do not have permission to access this feature'}, status=403)

    include_extra = True
    temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.csv')
    temp_path = temp_file.name
    temp_file.close()

    try:
        logger.info(
            "Starting member export by user %s (include_extra=%s)",
            request.user.username,
            include_extra,
        )
        call_command(
            'export_members_to_csv',
            output=temp_path,
            include_extra=include_extra,
            stdout=StringIO(),
        )

    except Exception as e:
        logger.error("Error during member export by user %s: %s", request.user.username, str(e))
        return JsonResponse({'error': str(e)}, status=500)
    else:
        with open(temp_path, 'rb') as csv_file:
            csv_data = csv_file.read()

        timestamp = timezone.now().strftime('%Y%m%d-%H%M%S')
        filename = f'members_export_{timestamp}.csv'
        response = HttpResponse(csv_data, content_type='text/csv')
        response['Content-Disposition'] = f'attachment; filename="{filename}"'
        logger.info("Member export completed successfully by user %s", request.user.username)
        return response
    finally:
        try:
            os.remove(temp_path)
        except OSError:
            logger.warning("Temporary file %s could not be removed after member export", temp_path)


def process_form(request):
    """
    Process the form submission.
    """
    context = {}

    if request.method == 'POST':
        # Validate reCAPTCHA
        recaptcha_valid, recaptcha_error = _validate_recaptcha(request)
        if not recaptcha_valid:
            logger.warning(f"reCAPTCHA validation failed for user {request.user.username}")
            context['error'] = recaptcha_error
            return render(request, 'forms/error.html', context)
        
        form_type = request.POST.get('form_type')

        # Member signup uses MemberSignupForm directly for validation
        if form_type == 'member_signup_form':
            form = MemberSignupForm(request.POST)
            if not form.is_valid():
                required_missing = [
                    field for field in form.errors
                    if any(e.code == 'required' for e in form.errors[field].as_data())
                ]
                other_errors = [
                    ', '.join(errs)
                    for field, errs in form.errors.items()
                    if field not in required_missing
                ]
                error_parts = []
                if required_missing:
                    error_parts.append(f'Required fields are missing: {", ".join(required_missing)}')
                error_parts.extend(other_errors)
                context['error'] = '. '.join(error_parts)
                logger.warning(f"Validation failed for member_signup_form by user {request.user.username}: {context['error']}")
                return render(request, 'forms/error.html', context)
            result = _process_member_signup(request, form.cleaned_data)
            context.update({k: v for k, v in result.items() if k in ['message', 'error']})
            return render(request, result['template'], context)

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
                'required_fields': ['name', 'email', 'event_details'],
                'model': BookingFormSubmission,
                'field_mapping': lambda req: {
                    'name': req.POST.get('name'),
                    'email': req.POST.get('email'),
                    'event_date': req.POST.get('event_date') or None,
                    'event_time': req.POST.get('event_time') or None,
                    'event_location': req.POST.get('event_location'),
                    'duration': req.POST.get('duration'),
                    'expected_guests': req.POST.get('expected_guests'),
                    'event_details': req.POST.get('event_details'),
                    'budget': req.POST.get('budget'),
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
            },
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

            # Process the form using standard submission model
            result = _process_form_submission(request, form_type, form_data, config['model'])
            context.update({k: v for k, v in result.items() if k in ['message', 'error']})
            return render(request, result['template'], context)
        
        else:
            # Handle unknown form types
            logger.info(f"Processing unknown form type submission by user {request.user.username}")
            context['message'] = 'Form submitted successfully!'
    
    else:
        logger.info(f"Form submission accessed with GET method by user {request.user.username}")

    return render(request, 'forms/post_process.html', context)


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


@require_http_methods(["POST"])
def fetch_embed_data(request):
    """API endpoint to fetch embed data (title, thumbnail) for a video URL"""
    from urllib.parse import urlparse

    from wagtail.embeds.embeds import get_embed
    from wagtail.embeds.exceptions import EmbedException

    # Require Wagtail admin access to prevent unauthorized SSRF attempts
    if not request.user.is_authenticated or not request.user.has_perm('wagtailadmin.access_admin'):
        logger.warning(f"Unauthorized access attempt to fetch_embed_data by user {request.user}")
        return JsonResponse({'error': 'Authentication required'}, status=403)
    
    url = request.POST.get('url', '').strip()
    if not url:
        return JsonResponse({'error': 'URL parameter is required'}, status=400)
    
    # Validate URL scheme and hostname to prevent SSRF
    try:
        parsed = urlparse(url)
        if parsed.scheme not in ('http', 'https'):
            return JsonResponse({'error': 'Only HTTP/HTTPS URLs are allowed'}, status=400)
        
        # Validate hostname (handles None case and ports correctly)
        hostname = parsed.hostname
        if not hostname:
            return JsonResponse({'error': 'Invalid URL: missing hostname'}, status=400)
        
        hostname = hostname.lower()
        
        # Allowlist known video providers to reduce SSRF risk
        # Use exact match or subdomain match to prevent bypasses like "evilyoutube.com"
        allowed_hosts = [
            'youtube.com', 'www.youtube.com', 'youtu.be', 'm.youtube.com',
            'vimeo.com', 'www.vimeo.com', 'player.vimeo.com'
        ]
        is_allowed = any(
            hostname == host or hostname.endswith('.' + host)
            for host in allowed_hosts
        )
        if not is_allowed:
            return JsonResponse({'error': 'Only YouTube and Vimeo URLs are supported'}, status=400)
    except Exception as e:
        logger.warning(f"Invalid URL format in fetch_embed_data: {url}")
        return JsonResponse({'error': 'Invalid URL format'}, status=400)
    
    try:
        # Use Wagtail's embed system to fetch metadata
        embed = get_embed(url)
        return JsonResponse({
            'title': embed.title,
            'thumbnail_url': embed.thumbnail_url,
            'author_name': embed.author_name,
            'provider_name': embed.provider_name,
        })
    except EmbedException as e:
        logger.warning(f"Failed to fetch embed data for URL {url}: {e}")
        return JsonResponse({'error': f'Unable to fetch embed data: {str(e)}'}, status=400)
    except Exception as e:
        logger.error(f"Unexpected error fetching embed data for URL {url}: {e}", exc_info=True)
        return JsonResponse({'error': 'An unexpected error occurred'}, status=500)
