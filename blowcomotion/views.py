from django.shortcuts import render, redirect
from django.contrib.auth import login, authenticate
from django.contrib.auth.forms import AuthenticationForm, UserCreationForm
from django.core.management import call_command
from io import StringIO
import json

from django.http import JsonResponse


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
    # check if the user is superuser
    if not request.user.is_superuser:
        return JsonResponse({'error': 'You must be a superuser to access this feature'}, status=403)

    try:
        # Use call_command to execute `dumpdata` and capture the output in the StringIO buffer
        call_command('dumpdata', *args, stdout=output)

        # Get the content of the buffer and parse it as JSON
        output_content = output.getvalue()
        data = json.loads(output_content)

        # Return the data as a JSON response with pretty formatting
        return JsonResponse(data, safe=False, json_dumps_params={'indent': 2})

    except Exception as e:
        # If something goes wrong, return an error message
        return JsonResponse({'error': str(e)}, status=500)