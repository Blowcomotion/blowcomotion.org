import json, logging
from io import StringIO

from django.contrib.auth import authenticate, login
from django.contrib.auth.forms import AuthenticationForm, UserCreationForm
from django.core.mail import send_mail
from django.core.management import call_command
from django.http import JsonResponse
from django.shortcuts import redirect, render

from blowcomotion.models import SiteSettings, ContactFormSubmission, FeedbackFormSubmission, JoinBandFormSubmission, BookingFormSubmission, DonateFormSubmission


logger = logging.getLogger(__name__)


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


def _send_form_email(subject, message, recipients, submitter_email=None):
    """Send email for form submission."""
    recipient_list = recipients.split(',')
    if submitter_email:
        recipient_list.append(submitter_email)
    
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
            'greeting': f'Hello {name},\n\n' if email else f'Feedback received from {name}:\n\n',
            'intro': 'Thank you for your feedback! We have received your message:\n\n' if email else '',
            'fields': f'Name: {name}\n' + (f'Email: {email}\n' if email else '') + f'Message: {kwargs.get("message", "")}\n' + (f'Page URL: {kwargs.get("page_url", "")}\n' if kwargs.get("page_url") else ''),
            'closing': '\nThank you for your feedback!\n\n' if email else '',
        }
    }
    
    msg_parts = messages.get(form_type, {})
    email_message = f'{form_type.replace("_", " ").title()} {"Received" if form_type == "feedback_form" else "Received"}\n\n'
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
            
            recipient_list = []
            if recipients:
                recipient_list = recipients.split(',')
            if form_data.get('email'):
                recipient_list.append(form_data['email'])
            
            if recipient_list:
                _send_form_email(subject, email_message, ','.join(recipient_list[:-1]) if len(recipient_list) > 1 else '', recipient_list[-1] if form_data.get('email') else None)
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