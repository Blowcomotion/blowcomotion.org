import logging
from datetime import datetime
from io import StringIO

from django.contrib.auth.decorators import login_required, permission_required
from django.core.cache import cache
from django.core.management import call_command
from django.http import JsonResponse
from django.shortcuts import render
from django.views.decorators.http import require_http_methods

from blowcomotion.models import CachedGig

logger = logging.getLogger(__name__)


@require_http_methods(["GET", "POST"])
def sync_gigs_admin(request):
    """
    Admin view to manually trigger gig sync from the Gig-O-Matic API.
    
    This provides a web interface to run the sync_gigs management command
    for cases when immediate sync is needed (e.g., after adding new gigs).
    """
    if not request.user.has_perm('blowcomotion.change_cachedgig'):
        logger.warning(f"Unauthorized access attempt to sync_gigs_admin by user {request.user.username}")
        return JsonResponse({'error': 'You do not have permission to access this feature'}, status=403)
    
    if request.method == 'POST':
        # Run the sync
        output = StringIO()
        try:
            call_command('sync_gigs', stdout=output, verbosity=2)
            sync_output = output.getvalue()
            # Strip ANSI color codes for HTML display
            import re
            sync_output = re.sub(r'\x1b\[[0-9;]*m', '', sync_output)
            logger.info(f"Manual gig sync triggered by {request.user.username}")
            
            # Get sync stats
            gig_count = CachedGig.objects.count()
            upcoming_count = CachedGig.get_upcoming_gigs().count()

            cache.clear()  # Clear cache to ensure updated gig data is shown on the site
            
            return render(request, 'admin/sync_gigs_result.html', {
                'success': True,
                'output': sync_output,
                'gig_count': gig_count,
                'upcoming_count': upcoming_count,
            })
        except Exception as e:
            logger.error(f"Error during manual gig sync by {request.user.username}: {e}")
            return render(request, 'admin/sync_gigs_result.html', {
                'success': False,
                'error': str(e),
            })
    
    # GET request - show the sync form with current status
    gig_count = CachedGig.objects.count()
    upcoming_count = CachedGig.get_upcoming_gigs().count()
    last_sync = CachedGig.objects.order_by('-last_synced').first()
    last_sync_time = last_sync.last_synced if last_sync else None
    
    return render(request, 'admin/sync_gigs.html', {
        'gig_count': gig_count,
        'upcoming_count': upcoming_count,
        'last_sync_time': last_sync_time,
    })


@login_required
@permission_required('blowcomotion.view_attendancerecord', raise_exception=True)
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
            logger.info(f"Returning cached gigs for {date_str}: {len(cached_result.get('gigs', []))} gig(s)")
            return JsonResponse(cached_result)
        
        # Fetch from database cache (synced from API via management command)
        logger.info(f"Fetching gigs from database cache for date {date_str}")
        cached_gigs = CachedGig.get_gigs_for_date(date_str)
        filtered_gigs = []
        
        for gig in cached_gigs:
            logger.info(f"Found matching gig: {gig.title} (ID: {gig.gig_id}) for {date_str}")
            filtered_gigs.append({
                'id': gig.gig_id,
                'title': gig.title,
                'date': gig.date.isoformat(),
                'address': gig.address
            })
        
        result = {'gigs': filtered_gigs}
        logger.info(f"Returning {len(filtered_gigs)} gig(s) for {date_str}, caching for 10 minutes")
        
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

