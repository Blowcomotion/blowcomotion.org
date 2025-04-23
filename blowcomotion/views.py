import json, logging
from io import StringIO

from django.contrib.auth import authenticate, login
from django.contrib.auth.forms import AuthenticationForm, UserCreationForm
from django.core.mail import send_mail
from django.core.management import call_command
from django.http import JsonResponse
from django.shortcuts import redirect, render

from blowcomotion.models import SiteSettings, ContactFormSubmission, FeedbackFormSubmission


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
    recipients = SiteSettings.for_request(request=request).contact_form_email_recipients
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
                )
                contact_form_submission.save()
                logger.info(f"Contact form submission saved successfully for user {request.user.username}")
                # Send the email
                send_mail(
                    subject='Contact Form Submission',
                    message=f'Name: {name}\nEmail: {email}\nMessage: {message}',
                    from_email='your_email@example.com',
                    recipient_list=recipients.split(','),
                    fail_silently=False,
                )
                logger.info(f"Email sent successfully for contact form submission by user {request.user.username}")
                context['message'] = "Contact form submitted successfully! We'll get back to you soon."
            except Exception as e:
                logger.error(f"Error sending email for contact form submission by user {request.user.username}: {str(e)}")
                context['error'] = f'Error sending email: {str(e)}'
                return render(request, 'forms/error.html', context)
        elif form_type == 'feedback_form':
            logger.info(f"Processing feedback form submission by user {request.user.username}")
            # Process the feedback form
            name = request.POST.get('name')
            email = request.POST.get('email')
            message = request.POST.get('message')
            # Validate the form data
            if not name or not email or not message:
                logger.warning(f"Validation failed for feedback form submission by user {request.user.username}. Missing fields.")
                context['error'] = 'All fields are required.'
                return render(request, 'forms/error.html', context)
            try:

                feedback_form_submission = FeedbackFormSubmission(
                    name=name,
                    email=email,
                    message=message,
                )
                feedback_form_submission.save()
                logger.info(f"Feedback form submission saved successfully for user {request.user.username}")
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