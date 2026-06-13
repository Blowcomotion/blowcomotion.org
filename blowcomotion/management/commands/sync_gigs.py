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
from datetime import date, datetime

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
        
        # Get today's date for filtering
        today = date.today()
        
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
        
        # Filter out gigs before today's date and track invalid dates separately
        original_count = len(gigs_list)
        future_gigs = []
        past_gigs_count = 0
        invalid_date_count = 0
        
        for gig in gigs_list:
            date_value = gig.get('date', '')
            try:
                # Parse the date to check if it's today or in the future
                if hasattr(date_value, 'date') and callable(getattr(date_value, 'date', None)):
                    gig_date = date_value.date()
                elif hasattr(date_value, 'year'):
                    gig_date = date_value
                else:
                    gig_date = datetime.strptime(str(date_value)[:10], '%Y-%m-%d').date()
                
                if gig_date >= today:
                    future_gigs.append(gig)
                else:
                    past_gigs_count += 1
            except (ValueError, TypeError, AttributeError) as e:
                # If we can't parse the date, track as invalid
                invalid_date_count += 1
                if verbosity >= 2:
                    self.stdout.write(
                        self.style.WARNING(
                            f'Skipping gig with invalid date: {date_value!r} ({gig.get("id", "unknown")}: {gig.get("title", "untitled")})'
                        )
                    )
        
        gigs_list = future_gigs
        
        # Report filtering results
        if past_gigs_count > 0:
            self.stdout.write(f'Filtered out {past_gigs_count} past gigs (keeping {len(gigs_list)} current/future gigs)')
        if invalid_date_count > 0:
            self.stdout.write(
                self.style.WARNING(f'Skipped {invalid_date_count} gigs with invalid dates')
            )
        
        # Delete cached gigs before today's date
        if dry_run:
            old_gigs_count = CachedGig.objects.filter(date__lt=today).count()
            if old_gigs_count > 0:
                self.stdout.write(f'Would delete {old_gigs_count} cached gigs before {today}')
        else:
            deleted_count, _ = CachedGig.objects.filter(date__lt=today).delete()
            if deleted_count > 0:
                self.stdout.write(f'Deleted {deleted_count} cached gigs before {today}')
                logger.info(f'sync_gigs: Deleted {deleted_count} old cached gigs before {today}')
        
        created_count = 0
        updated_count = 0
        error_count = 0
        
        for gig in gigs_list:
            try:
                # Coerce gig_id to int to ensure consistent typing
                raw_gig_id = gig.get('id')
                try:
                    gig_id = int(raw_gig_id)
                except (TypeError, ValueError):
                    if verbosity >= 2:
                        self.stdout.write(self.style.WARNING(f'Skipping gig with invalid ID: {raw_gig_id!r} ({gig})'))
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
                        # It's a datetime object - use API date, convert time to Central
                        from zoneinfo import ZoneInfo
                        dt = date_value
                        # Use the date from the API as-is (don't shift across days)
                        gig_date = dt.date()
                        # If naive datetime, assume UTC (GO3 stores times in UTC)
                        if dt.tzinfo is None:
                            dt = dt.replace(tzinfo=ZoneInfo("UTC"))
                        # Convert to Central timezone and strip tzinfo for TimeField
                        central_dt = dt.astimezone(ZoneInfo("America/Chicago"))
                        gig_time = central_dt.time().replace(tzinfo=None)
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
                                # Strip tzinfo before saving to TimeField
                                gig_time = central_time_obj.time().replace(tzinfo=None)
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
