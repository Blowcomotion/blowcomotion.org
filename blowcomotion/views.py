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
    site_settings = SiteSettings.for_request(request=request)
    if request.method == 'POST':
        # Handle honeypot field
        honeypot = request.POST.get('best_color')
        if honeypot != 'purple':
            logger.warning(f"Honeypot triggered by user {request.user.username}")
            # Honeypot triggered, do not process the form
            context['error'] = honeypot_message
            return render(request, 'forms/error.html', context)
        form_type = request.POST.get('form_type')
        if form_type == 'contact_form':
            recipients = site_settings.contact_form_email_recipients
            if not recipients:
                logger.error(f"No recipients specified for the contact form. Submission by user {request.user.username} failed.")
                # No recipients specified, do not process the form
                context['error'] = 'No recipients specified for the contact form. Add them in the admin settings.'
                return render(request, 'forms/error.html', context)
            logger.info(f"Processing contact form submission by user {request.user.username}")
            # Process the contact form
            name = request.POST.get('name')
            email = request.POST.get('email')
            message = request.POST.get('message')
            newsletter_opt_in = request.POST.get('newsletter', False) == 'yes'
            # Validate the form data
            if not name or not email or not message:
                logger.warning(f"Validation failed for contact form submission by user {request.user.username}. Missing fields.")
                context['error'] = 'All fields are required.'
                return render(request, 'forms/error.html', context)
            try:
                # Save the contact form submission to the database
                contact_form_submission = ContactFormSubmission(
                    name=name,
                    email=email,
                    message=message,
                    newsletter_opt_in=newsletter_opt_in,
                )
                contact_form_submission.save()
                logger.info(f"Contact form submission saved successfully for user {request.user.username}")
                # Send the email
                email_message = f'Contact Form Message Received\n\n'
                email_message += f'Hello {name},\n\n'
                email_message += f'Thank you for contacting us! We have received your message:\n\n'
                email_message += f'Name: {name}\n'
                email_message += f'Email: {email}\n'
                email_message += f'Message: {message}\n\n'
                email_message += f'We will get back to you soon.\n\n'
                email_message += f'Start Wearing Purple,\nBlowcomotion'
                
                # Include the submitter in the recipient list
                recipient_list = recipients.split(',') + [email]
                
                send_mail(
                    subject='Contact Form Submission',
                    message=email_message,
                    from_email='info@blowcomotion.org',
                    recipient_list=recipient_list,
                    fail_silently=False,
                )
                logger.info(f"Email sent successfully for contact form submission by user {request.user.username}")
                context['message'] = "Contact form submitted successfully! We'll get back to you soon."
            except Exception as e:
                logger.error(f"Error sending email for contact form submission by user {request.user.username}: {str(e)}")
                context['error'] = f'Error sending email: {str(e)}'
                return render(request, 'forms/error.html', context)
        elif form_type == 'join_band_form':
            recipients = site_settings.join_band_form_email_recipients
            if not recipients:
                logger.error(f"No recipients specified for the join band form. Submission by user {request.user.username} failed.")
                # No recipients specified, do not process the form
                context['error'] = 'No recipients specified for the join band form. Add them in the admin settings.'
                return render(request, 'forms/error.html', context)
            logger.info(f"Processing join band form submission by user {request.user.username}")
            # Process the join band form
            name = request.POST.get('name')
            email = request.POST.get('email')
            instrument = request.POST.get('instrument')
            instrument_rental = request.POST.get('instrument_rental')
            message = request.POST.get('message')
            newsletter_opt_in = request.POST.get('newsletter', False) == 'yes'
            # Validate the form data
            if not name or not email or not instrument or not instrument_rental:
                logger.warning(f"Validation failed for join band form submission by user {request.user.username}. Missing fields.")
                context['error'] = 'Name, email, instrument, and instrument rental preference are required.'
                return render(request, 'forms/error.html', context)
            try:
                # Save the join band form submission to the database
                join_band_form_submission = JoinBandFormSubmission(
                    name=name,
                    email=email,
                    instrument=instrument,
                    instrument_rental=instrument_rental,
                    message=message,
                    newsletter_opt_in=newsletter_opt_in,
                )
                join_band_form_submission.save()
                logger.info(f"Join band form submission saved successfully for user {request.user.username}")
                # Send the email
                email_message = f'Join Band Application Received\n\n'
                email_message += f'Hello {name},\n\n'
                email_message += f'Thank you for your interest in joining our band! We have received your application with the following details:\n\n'
                email_message += f'Name: {name}\n'
                email_message += f'Email: {email}\n'
                email_message += f'Instrument: {instrument}\n'
                email_message += f'Instrument Rental: {instrument_rental}\n'
                if message:
                    email_message += f'Message: {message}\n'
                email_message += f'\nWe will review your application and get back to you soon.\n\n'
                email_message += f'Start Wearing Purple,\nBlowcomotion'

                # Include the submitter in the recipient list
                recipient_list = recipients.split(',') + [email]
                
                send_mail(
                    subject='Join Band Form Submission',
                    message=email_message,
                    from_email='info@blowcomotion.org',
                    recipient_list=recipient_list,
                    fail_silently=False,
                )
                logger.info(f"Email sent successfully for join band form submission by user {request.user.username}")
                context['message'] = "Join band application submitted successfully! We'll review your application and get back to you soon."
            except Exception as e:
                logger.error(f"Error sending email for join band form submission by user {request.user.username}: {str(e)}")
                context['error'] = f'Error sending email: {str(e)}'
                return render(request, 'forms/error.html', context)
        elif form_type == 'booking_form':
            recipients = site_settings.booking_form_email_recipients
            if not recipients:
                logger.error(f"No recipients specified for the booking form. Submission by user {request.user.username} failed.")
                # No recipients specified, do not process the form
                context['error'] = 'No recipients specified for the booking form. Add them in the admin settings.'
                return render(request, 'forms/error.html', context)
            logger.info(f"Processing booking form submission by user {request.user.username}")
            # Process the booking form
            name = request.POST.get('name')
            email = request.POST.get('email')
            message = request.POST.get('message')
            newsletter_opt_in = request.POST.get('newsletter', False) == 'yes'
            # Validate the form data
            if not name or not email or not message:
                logger.warning(f"Validation failed for booking form submission by user {request.user.username}. Missing fields.")
                context['error'] = 'All fields are required.'
                return render(request, 'forms/error.html', context)
            try:
                # Save the booking form submission to the database
                booking_form_submission = BookingFormSubmission(
                    name=name,
                    email=email,
                    message=message,
                    newsletter_opt_in=newsletter_opt_in,
                )
                booking_form_submission.save()
                logger.info(f"Booking form submission saved successfully for user {request.user.username}")
                # Send the email
                email_message = f'Booking Request Received\n\n'
                email_message += f'Hello {name},\n\n'
                email_message += f'Thank you for your interest in booking Blowcomotion! We have received your booking request with the following details:\n\n'
                email_message += f'Name: {name}\n'
                email_message += f'Email: {email}\n'
                email_message += f'Event Details: {message}\n\n'
                email_message += f'We will review your request and get back to you soon with availability and pricing information.\n\n'
                email_message += f'Start Wearing Purple,\nBlowcomotion'

                # Include the submitter in the recipient list
                recipient_list = recipients.split(',') + [email]
                
                send_mail(
                    subject='Booking Form Submission',
                    message=email_message,
                    from_email='info@blowcomotion.org',
                    recipient_list=recipient_list,
                    fail_silently=False,
                )
                logger.info(f"Email sent successfully for booking form submission by user {request.user.username}")
                context['message'] = "Booking request submitted successfully! We'll review your request and get back to you soon with availability and pricing."
            except Exception as e:
                logger.error(f"Error sending email for booking form submission by user {request.user.username}: {str(e)}")
                context['error'] = f'Error sending email: {str(e)}'
                return render(request, 'forms/error.html', context)
        elif form_type == 'donate_form':
            recipients = site_settings.donate_form_email_recipients
            if not recipients:
                logger.error(f"No recipients specified for the donate form. Submission by user {request.user.username} failed.")
                # No recipients specified, do not process the form
                context['error'] = 'No recipients specified for the donate form. Add them in the admin settings.'
                return render(request, 'forms/error.html', context)
            logger.info(f"Processing donate form submission by user {request.user.username}")
            # Process the donate form
            name = request.POST.get('name')
            email = request.POST.get('email')
            message = request.POST.get('message')
            newsletter_opt_in = request.POST.get('newsletter', False) == 'yes'
            # Validate the form data
            if not name or not email:
                logger.warning(f"Validation failed for donate form submission by user {request.user.username}. Missing fields.")
                context['error'] = 'Name and email are required.'
                return render(request, 'forms/error.html', context)
            try:
                # Save the donate form submission to the database
                donate_form_submission = DonateFormSubmission(
                    name=name,
                    email=email,
                    message=message,
                    newsletter_opt_in=newsletter_opt_in,
                )
                donate_form_submission.save()
                logger.info(f"Donate form submission saved successfully for user {request.user.username}")
                # Send the email
                email_message = f'Donation Information Received\n\n'
                email_message += f'Hello {name},\n\n'
                email_message += f'Thank you for your interest in supporting Blowcomotion! We have received your donation information:\n\n'
                email_message += f'Name: {name}\n'
                email_message += f'Email: {email}\n'
                if message:
                    email_message += f'Message: {message}\n'
                email_message += f'\nWe will get back to you soon with information about donation options and how your support helps our band.\n\n'
                email_message += f'Start Wearing Purple,\nBlowcomotion'

                # Include the submitter in the recipient list
                recipient_list = recipients.split(',') + [email]
                
                send_mail(
                    subject='Donate Form Submission',
                    message=email_message,
                    from_email='info@blowcomotion.org',
                    recipient_list=recipient_list,
                    fail_silently=False,
                )
                logger.info(f"Email sent successfully for donate form submission by user {request.user.username}")
                context['message'] = "Donation information submitted successfully! We'll get back to you soon with details about how you can support our band."
            except Exception as e:
                logger.error(f"Error sending email for donate form submission by user {request.user.username}: {str(e)}")
                context['error'] = f'Error sending email: {str(e)}'
                return render(request, 'forms/error.html', context)
        elif form_type == 'feedback_form':
            recipients = site_settings.feedback_form_email_recipients
            logger.info(f"Processing feedback form submission by user {request.user.username}")
            # Process the feedback form
            name = request.POST.get('name')
            email = request.POST.get('email')
            message = request.POST.get('message')
            page_url = request.POST.get('page_url')
            # Validate the form data
            if not message or not name:
                logger.warning(f"Validation failed for feedback form submission by user {request.user.username}. Missing fields.")
                context['error'] = 'Message and name are required.'
                return render(request, 'forms/error.html', context)
            try:
                feedback_form_submission = FeedbackFormSubmission(
                    name=name,
                    email=email,
                    message=message,
                    submitted_from_page=page_url,
                )
                feedback_form_submission.save()
                logger.info(f"Feedback form submission saved successfully for user {request.user.username}")

                # Send the email
                email_message = f'Feedback Received\n\n'
                if email:
                    email_message += f'Hello {name},\n\n'
                    email_message += f'Thank you for your feedback! We have received your message:\n\n'
                else:
                    email_message += f'Feedback received from {name}:\n\n'
                email_message += f'Name: {name}\n'
                if email:
                    email_message += f'Email: {email}\n'
                email_message += f'Message: {message}\n'
                if page_url:
                    email_message += f'Page URL: {page_url}\n'
                if email:
                    email_message += f'\nThank you for your feedback!\n\n'
                    email_message += f'Best regards,\nBlowcomotion Team'
                
                # Include the submitter in the recipient list if email is provided
                recipient_list = []
                if recipients:
                    recipient_list = recipients.split(',')
                if email:
                    recipient_list.append(email)
                
                if recipient_list:
                    send_mail(
                        subject='Feedback Form Submission',
                        message=email_message,
                        from_email='info@blowcomotion.org',
                        recipient_list=recipient_list,
                        fail_silently=False,
                    )
                    logger.info(f"Email sent successfully for feedback form submission by user {request.user.username}")
                else:
                    logger.warning(f"No recipients configured for feedback form submission by user {request.user.username}")
                
                context['message'] = "Feedback form submitted successfully! Thank you for your feedback."
            except Exception as e:
                logger.error(f"Error saving feedback form submission by user {request.user.username}: {str(e)}")
                context['error'] = f'Error saving feedback: {str(e)}'
                return render(request, 'forms/error.html', context)
        else:
            logger.info(f"Processing other form type submission by user {request.user.username}")
            honeypot = request.POST.get('best_color')
            if honeypot != 'purple':
                logger.warning(f"Honeypot triggered by user {request.user.username}")
                # Honeypot triggered, do not process the form
                context['error'] = honeypot_message
                return render(request, 'forms/error.html', context)
            # Handle other forms
            context['message'] = 'Form submitted successfully!'
    else:
        logger.info(f"Form submission accessed with GET method by user {request.user.username}")

    return render(request, 'forms/post_process.html', context)