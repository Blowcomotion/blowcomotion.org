"""
Management command to sync gigs from the Gig-O-Matic API.

This command fetches all gigs from the Gig-O-Matic API and stores them
in the CachedGig model for faster page rendering. It should be scheduled
to run periodically (e.g., hourly) via cron.

Usage:
    python manage.py sync_gigs
    python manage.py sync_gigs --verbosity 2  # For detailed output
    python manage.py sync_gigs --dry-run      # Preview without saving

Cron example (run every hour):
    0 * * * * cd /path/to/project && /path/to/venv/bin/python manage.py sync_gigs >> /var/log/sync_gigs.log 2>&1
"""
import logging
from datetime import datetime

from django.conf import settings
from django.core.management.base import BaseCommand

from blowcomotion.models import CachedGig
from blowcomotion.utils import convert_utc_gig_to_central, make_gigo_api_request

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Sync gigs from the Gig-O-Matic API to the local database cache'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Preview sync without saving to database',
        )

    def handle(self, *args, **options):
        verbosity = options.get('verbosity', 1)
        dry_run = options.get('dry_run', False)
        
        # Check API configuration
        api_url = getattr(settings, 'GIGO_API_URL', None)
        api_key = getattr(settings, 'GIGO_API_KEY', None)
        
        if not api_url or not api_key:
            self.stdout.write(
                self.style.ERROR('GIGO_API_URL or GIGO_API_KEY not configured in settings')
            )
            return
        
        if dry_run:
            self.stdout.write(self.style.WARNING('DRY RUN - No changes will be saved'))
        
        self.stdout.write('Fetching gigs from Gig-O-Matic API...')
        
        # Fetch all gigs from the API
        gigs_data = make_gigo_api_request('/gigs', timeout=30, retries=2)
        
        if gigs_data is None:
            self.stdout.write(self.style.ERROR('Failed to fetch gigs from API'))
            logger.error('sync_gigs: Failed to fetch gigs from API')
            return
        
        gigs_list = gigs_data.get('gigs', [])
        if not gigs_list:
            self.stdout.write(self.style.WARNING('No gigs returned from API'))
            return
        
        self.stdout.write(f'Retrieved {len(gigs_list)} gigs from API')
        
        # Filter by band name if configured
        band_name = getattr(settings, 'GIGO_BAND_NAME', None)
        if band_name:
            original_count = len(gigs_list)
            gigs_list = [
                gig for gig in gigs_list 
                if gig.get('band', '').lower() == band_name.lower()
            ]
            filtered_count = original_count - len(gigs_list)
            if filtered_count > 0:
                self.stdout.write(f'Filtered to {len(gigs_list)} gigs for band "{band_name}" (excluded {filtered_count})')
        
        created_count = 0
        updated_count = 0
        error_count = 0
        
        for gig in gigs_list:
            try:
                gig_id = gig.get('id')
                if not gig_id:
                    if verbosity >= 2:
                        self.stdout.write(self.style.WARNING(f'Skipping gig without ID: {gig}'))
                    error_count += 1
                    continue
                
                # Parse date and time from the API response
                # The API may return date as ISO format string (YYYY-MM-DD) or datetime object
                date_value = gig.get('date', '')
                gig_date = None
                gig_time = None
                
                if date_value:
                    # Handle datetime objects directly (local GO3 returns these)
                    if hasattr(date_value, 'date') and callable(getattr(date_value, 'date', None)):
                        # It's a datetime object - convert to Central timezone first
                        from zoneinfo import ZoneInfo
                        dt = date_value
                        # If naive datetime, assume UTC (GO3 stores times in UTC)
                        if dt.tzinfo is None:
                            dt = dt.replace(tzinfo=ZoneInfo("UTC"))
                        # Convert to Central timezone
                        central_dt = dt.astimezone(ZoneInfo("America/Chicago"))
                        gig_date = central_dt.date()
                        gig_time = central_dt.time()
                    elif hasattr(date_value, 'year'):
                        # It's a date object (no time component, use as-is)
                        gig_date = date_value
                    else:
                        # It's a string, try to parse it
                        try:
                            # Convert UTC to Central timezone for display
                            central_date_str, central_time_obj = convert_utc_gig_to_central(gig)
                            gig_date = datetime.strptime(central_date_str, '%Y-%m-%d').date()
                            if central_time_obj and hasattr(central_time_obj, 'time'):
                                gig_time = central_time_obj.time()
                        except (ValueError, TypeError) as e:
                            if verbosity >= 2:
                                self.stdout.write(
                                    self.style.WARNING(f'Could not parse date for gig {gig_id}: {e}')
                                )
                            # Fall back to just parsing the date string
                            try:
                                gig_date = datetime.strptime(str(date_value)[:10], '%Y-%m-%d').date()
                            except ValueError:
                                pass
                
                if not gig_date:
                    if verbosity >= 2:
                        self.stdout.write(
                            self.style.WARNING(f'Skipping gig {gig_id} with invalid date: {date_value}')
                        )
                    error_count += 1
                    continue
                
                gig_data = {
                    'title': gig.get('title', 'Untitled Gig')[:500],
                    'date': gig_date,
                    'time': gig_time,
                    'address': gig.get('address', '') or '',
                    'gig_status': gig.get('gig_status', 'unknown')[:50],
                    'band': gig.get('band', '')[:255],
                    'raw_data': gig,
                }
                
                if dry_run:
                    # In dry run mode, just check if it would be created or updated
                    exists = CachedGig.objects.filter(gig_id=gig_id).exists()
                    if exists:
                        updated_count += 1
                        if verbosity >= 2:
                            self.stdout.write(f'  Would update: {gig_data["title"]} ({gig_date})')
                    else:
                        created_count += 1
                        if verbosity >= 2:
                            self.stdout.write(f'  Would create: {gig_data["title"]} ({gig_date})')
                else:
                    # Actual sync
                    obj, created = CachedGig.objects.update_or_create(
                        gig_id=gig_id,
                        defaults=gig_data
                    )
                    
                    if created:
                        created_count += 1
                        if verbosity >= 2:
                            self.stdout.write(f'  Created: {obj.title} ({obj.date})')
                    else:
                        updated_count += 1
                        if verbosity >= 2:
                            self.stdout.write(f'  Updated: {obj.title} ({obj.date})')
                            
            except Exception as e:
                error_count += 1
                logger.exception(f'Error syncing gig {gig.get("id", "unknown")}: {e}')
                if verbosity >= 1:
                    self.stdout.write(
                        self.style.ERROR(f'Error syncing gig {gig.get("id", "unknown")}: {e}')
                    )
        
        # Report results
        self.stdout.write('')
        if dry_run:
            self.stdout.write(self.style.SUCCESS(
                f'DRY RUN complete: {created_count} would be created, '
                f'{updated_count} would be updated, {error_count} errors'
            ))
        else:
            self.stdout.write(self.style.SUCCESS(
                f'Sync complete: {created_count} created, {updated_count} updated, {error_count} errors'
            ))
            logger.info(
                f'sync_gigs: Synced {created_count + updated_count} gigs '
                f'({created_count} created, {updated_count} updated, {error_count} errors)'
            )
