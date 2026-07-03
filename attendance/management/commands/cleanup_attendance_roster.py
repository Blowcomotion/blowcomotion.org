import datetime

from wagtail.models import Site

from django.core.management.base import BaseCommand

from blowcomotion.models import Member, SiteSettings


class Command(BaseCommand):
    help = 'Clean up attendance records by marking inactive members'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Simulate the cleanup without making any changes.',
        )
        parser.add_argument(
            '--day-to-run',
            type=int,
            choices=range(7),
            help='Day of the week to run the command (0=Monday, 6=Sunday)',
        )

    def _get_site_settings(self):
        try:
            site = Site.objects.filter(is_default_site=True).select_related('root_page').first()
            if not site:
                site = Site.objects.select_related('root_page').first()
            if not site:
                self.stdout.write(self.style.ERROR('No Site configured. Cannot load SiteSettings.'))
                return None
            return SiteSettings.for_site(site)
        except Exception as exc:
            self.stdout.write(self.style.ERROR(f'Error retrieving SiteSettings: {exc}'))
            return None

    def handle(self, *args, **options):
        today = datetime.date.today()
        weekday = today.weekday()  # Monday=0, Sunday=6
        day_to_run = options['day_to_run']
        days_of_week = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
        if day_to_run is not None and weekday != day_to_run:
            self.stdout.write(
                self.style.WARNING(
                    f'This command is intended to be run on {days_of_week[day_to_run]} only. Exiting.'
                )
            )
            return

        # Get site settings to determine cleanup threshold
        site_settings = self._get_site_settings()
        if not site_settings:
            self.stdout.write(self.style.ERROR('SiteSettings could not be loaded. Exiting.'))
            return
        cleanup_days = site_settings.attendance_cleanup_days

        # Calculate cutoff date
        cutoff_date = datetime.date.today() - datetime.timedelta(days=cleanup_days)

        # Query members who haven't been seen since cutoff date
        inactive_members = Member.objects.filter(
            last_seen__lt=cutoff_date,
            is_active=True
        )

        if not options['dry_run']:
            self.stdout.write(
                self.style.SUCCESS(f'Found {inactive_members.count()} members to mark as inactive (last seen before {cutoff_date}).')
            )
        else:
            self.stdout.write(
                self.style.NOTICE(f'[Dry Run] Found {inactive_members.count()} members to mark as inactive (last seen before {cutoff_date}).')
            )

        # Mark members as inactive
        for member in inactive_members:
            if options['dry_run']:
                self.stdout.write(
                    self.style.NOTICE(f'[Dry Run] Would mark member {member.full_name} as inactive.')
                )
                continue
            member.is_active = False
            member.save()
            self.stdout.write(
                self.style.SUCCESS(f'Marked member {member.full_name} as inactive.')
            )

        if not inactive_members:
            self.stdout.write(
                self.style.SUCCESS('No members to mark as inactive.')
            )