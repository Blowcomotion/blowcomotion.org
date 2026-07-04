import logging
import os
import tempfile
from io import StringIO

from django.core.management import call_command
from django.http import HttpResponse, JsonResponse
from django.utils import timezone

logger = logging.getLogger(__name__)


def export_charts_csv(request):
    if not request.user.has_perm('blowcomotion.access_real_data_exports'):
        logger.warning("Unauthorized access attempt to export charts by user %s", request.user.username)
        return JsonResponse({'error': 'You do not have permission to access this feature'}, status=403)

    temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.csv')
    temp_path = temp_file.name
    temp_file.close()

    try:
        logger.info("Starting chart export by user %s", request.user.username)
        call_command(
            'export_charts_to_csv',
            output_path=temp_path,
            stdout=StringIO(),
        )

    except Exception:
        logger.exception("Error during chart export by user %s", request.user.username)
        return JsonResponse({'error': 'An internal error occurred while exporting charts.'}, status=500)
    else:
        with open(temp_path, 'rb') as csv_file:
            csv_data = csv_file.read()

        timestamp = timezone.now().strftime('%Y%m%d-%H%M%S')
        filename = f'charts_export_{timestamp}.csv'
        response = HttpResponse(csv_data, content_type='text/csv')
        response['Content-Disposition'] = f'attachment; filename="{filename}"'
        logger.info("Chart export completed successfully by user %s", request.user.username)
        return response
    finally:
        try:
            os.remove(temp_path)
        except OSError:
            logger.warning("Temporary file %s could not be removed after chart export", temp_path)
