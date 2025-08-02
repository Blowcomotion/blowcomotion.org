import json, logging, base64
from io import StringIO
from datetime import date, timedelta
from collections import defaultdict
from functools import wraps

from django.contrib.auth import authenticate, login
from django.contrib.auth.forms import AuthenticationForm, UserCreationForm
from django.core.mail import send_mail
from django.core.management import call_command
from django.db.models import Count, Q
from django.http import JsonResponse, HttpResponse
from django.shortcuts import redirect, render, get_object_or_404
from django.views.decorators.http import require_http_methods

from blowcomotion.models import (
    SiteSettings, ContactFormSubmission, FeedbackFormSubmission, 
    JoinBandFormSubmission, BookingFormSubmission, DonateFormSubmission,
    Member, Section, AttendanceRecord, MemberInstrument, Instrument
)
from blowcomotion.forms import SectionAttendanceForm, AttendanceReportFilterForm


logger = logging.getLogger(__name__)


def http_basic_auth(username=None, password='purplepassword'):
    """
    Decorator for HTTP Basic Authentication
    If username is None, any username will be accepted (only password is checked)
    """
    def decorator(func):
        @wraps(func)
        def wrapper(request, *args, **kwargs):
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
                if provided_password == password:
                    return func(request, *args, **kwargs)
            else:
                # Check both username and password
                if provided_username == username and provided_password == password:
                    return func(request, *args, **kwargs)
            
            response = HttpResponse('Unauthorized', status=401)
            response['WWW-Authenticate'] = 'Basic realm="Attendance Area"'
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
            'closing': 'We will review your application and get back to you soon.\n\n',
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
        # Get members who don't have any instrument assignments
        members_with_instruments = MemberInstrument.objects.values_list('member_id', flat=True).distinct()
        section_members = Member.objects.filter(
            is_active=True
        ).exclude(id__in=members_with_instruments).order_by('first_name', 'last_name')
    elif section:
        # Get instruments that belong to this section
        section_instruments = Instrument.objects.filter(section=section).order_by('name')
        
        # Group members by instrument
        for instrument in section_instruments:
            members_for_instrument = Member.objects.filter(
                instruments__instrument=instrument,
                is_active=True
            ).distinct().order_by('first_name', 'last_name')
            
            if members_for_instrument.exists():
                members_by_instrument[instrument] = members_for_instrument
        
        # Also get all section members for backward compatibility
        member_ids = MemberInstrument.objects.filter(
            instrument__in=section_instruments
        ).values_list('member_id', flat=True).distinct()
        
        section_members = Member.objects.filter(
            id__in=member_ids,
            is_active=True
        ).distinct().order_by('first_name', 'last_name')
    
    if request.method == 'POST':
        attendance_date_str = request.POST.get('attendance_date', date.today().strftime('%Y-%m-%d'))
        event_type = request.POST.get('event_type', 'rehearsal')
        event_name = request.POST.get('event_name', '').strip()
        
        # Convert string to date object for consistent handling
        if isinstance(attendance_date_str, str):
            from datetime import datetime
            attendance_date = datetime.strptime(attendance_date_str, '%Y-%m-%d').date()
        else:
            attendance_date = attendance_date_str
        
        # Create notes based on event type and name
        if event_type == 'performance' and event_name:
            event_notes = f"Performance: {event_name}"
        else:
            event_notes = event_type.capitalize()
        
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
                        defaults={'notes': event_notes}
                    )
                    if created:
                        success_count += 1
                    else:
                        # Update existing record to append event type in notes if not already present
                        if not attendance_record.notes:
                            attendance_record.notes = event_notes
                            attendance_record.save()
                        else:
                            # Only append event_notes if it's not already present as a full entry
                            notes_entries = [entry.strip() for entry in attendance_record.notes.split(';') if entry.strip()]
                            if event_notes not in notes_entries:
                                notes_entries.append(event_notes)
                                attendance_record.notes = '; '.join(notes_entries)
                                attendance_record.save()
                    
                    # Update member's last_seen field
                    member.last_seen = attendance_date
                    member.save(update_fields=['last_seen'])
                except Exception as e:
                    errors.append(f"Error recording attendance for {member}: {str(e)}")
        
        # Process guest attendance
        if section or is_no_section:
            # For no-section, use a special guest field name
            guest_field = f'guest_{section.id}' if section else 'guest_no_section'
            if guest_field in request.POST and request.POST[guest_field].strip():
                guest_names = [name.strip() for name in request.POST[guest_field].split('\n') if name.strip()]
                for guest_name in guest_names:
                    try:
                        guest_notes = f"Guest - {event_notes}"
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
            ).select_related('member').prefetch_related('member__instruments__instrument').order_by('member__first_name', 'member__last_name', 'guest_name')
        elif is_no_section:
            # Get all records for this date and no-section members
            todays_records = AttendanceRecord.objects.filter(
                date=attendance_date
            ).filter(
                Q(member__in=section_members) | Q(member__isnull=True)
            ).select_related('member').prefetch_related('member__instruments__instrument').order_by('member__first_name', 'member__last_name', 'guest_name')
        else:
            todays_records = AttendanceRecord.objects.filter(date=attendance_date).select_related('member').prefetch_related('member__instruments__instrument')
        
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
    
    context = {
        'section': section,
        'section_members': section_members,
        'members_by_instrument': members_by_instrument,
        'sections': sections,
        'is_no_section': is_no_section,
        'today': date.today()
    }
    
    # For HTMX section switching, return the main content including navigation
    if request.headers.get('HX-Request'):
        return render(request, 'attendance/partials/capture_content.html', context)
    
    return render(request, 'attendance/capture.html', context)


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
        member_instruments = Instrument.objects.filter(section=section)
        section_member_ids = list(set(member_instruments))
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
        'attendance_records': attendance_records.select_related('member').prefetch_related('member__instruments__instrument').order_by('-date', 'member__first_name', 'member__last_name')[:100],  # Limit for performance
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
    
    # Get members in this section
    # Get instruments that belong to this section
    section_instruments = Instrument.objects.filter(section=section)
    # Get member IDs who have instruments in this section
    section_member_ids = list(MemberInstrument.objects.filter(
        instrument__in=section_instruments
    ).values_list('member_id', flat=True).distinct())
    section_members = Member.objects.filter(
        id__in=section_member_ids, 
        is_active=True
    ).order_by('first_name', 'last_name').prefetch_related('instruments__instrument')
    
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
        'attendance_records': attendance_records.select_related('member').prefetch_related('member__instruments__instrument'),
        'member_attendance': member_attendance,
        'attendance_by_date': attendance_by_date,
        'start_date': start_date,
        'end_date': end_date
    }
    
    # For HTMX requests, return just the content
    if request.headers.get('HX-Request'):
        return render(request, 'attendance/partials/section_report_content.html', context)
    
    return render(request, 'attendance/section_report.html', context)