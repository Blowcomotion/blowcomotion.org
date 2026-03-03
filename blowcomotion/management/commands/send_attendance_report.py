import datetime
from collections import defaultdict

from wagtail.models import Site

from django.conf import settings
from django.core.mail import send_mail
from django.core.management.base import BaseCommand
from django.db.models import Count

from blowcomotion.models import AttendanceRecord, Member, Section, SiteSettings


class Command(BaseCommand):
    help = 'Send a weekly attendance report on Fridays'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Simulate the report without sending email.',
        )
        parser.add_argument(
            '--day-to-run',
            type=int,
            choices=range(7),
            help='Day of the week to run the command (0=Monday, 6=Sunday, default=4 for Friday)',
            default=4,
        )

    def _send_mail(self, subject, message, recipients, dry_run):
        """Send notification email or display if in dry-run mode."""
        if dry_run:
            self.stdout.write(
                self.style.NOTICE(f'[Dry Run] Would send email to {recipients}:\nSubject: {subject}\n\nMessage:\n{message}')
            )
        else:
            send_mail(
                subject,
                message,
                settings.FROM_EMAIL,
                recipients,
                fail_silently=False,
            )
            self.stdout.write(
                self.style.SUCCESS(
                    f'✅ Attendance report sent to {len(recipients)} recipient(s)'
                )
            )

    def _get_site_settings(self):
        """Retrieve site settings."""
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

    def _cleanup_inactive_members(self, site_settings, dry_run=False):
        """Mark inactive members and return the list of cleaned up members."""
        cleanup_days = site_settings.attendance_cleanup_days
        cutoff_date = datetime.date.today() - datetime.timedelta(days=cleanup_days)
        
        # Query members who haven't been seen since cutoff date
        # Materialize the queryset before iterating to avoid re-query after saves
        cleaned_up_members = list(Member.objects.filter(
            last_seen__lt=cutoff_date,
            is_active=True
        ).order_by('-last_seen'))
        
        if not dry_run:
            for member in cleaned_up_members:
                member.is_active = False
                member.save()
                self.stdout.write(
                    self.style.SUCCESS(f'  Marked member {member.full_name} as inactive (last seen: {member.last_seen}).')
                )
        else:
            for member in cleaned_up_members:
                self.stdout.write(
                    self.style.NOTICE(f'  [Dry Run] Would mark member {member.full_name} as inactive (last seen: {member.last_seen}).')
                )
        
        return cleaned_up_members

    def _calculate_metrics(self):
        """Calculate attendance metrics for the past 7 days."""
        end_date = datetime.date.today()
        # Use days=6 for an inclusive 7-day window (today through 6 days ago)
        start_date = end_date - datetime.timedelta(days=6)
        
        metrics = {
            'start_date': start_date,
            'end_date': end_date,
            'attendance_records': AttendanceRecord.objects.filter(
                date__gte=start_date,
                date__lte=end_date
            ).select_related('member', 'member__primary_instrument', 'member__primary_instrument__section'),
        }
        
        # Get all unique members who attended in past week
        attended_members = set(
            member_id for member_id in 
            metrics['attendance_records'].filter(member__isnull=False).values_list('member_id', flat=True).distinct()
        )
        
        metrics['total_attendance'] = len(attended_members)
        metrics['unique_members'] = Member.objects.filter(id__in=attended_members)
        
        # Calculate attendance by section
        section_attendance = defaultdict(lambda: {'count': 0, 'members': set()})
        for record in metrics['attendance_records'].filter(member__isnull=False):
            if record.member.primary_instrument and record.member.primary_instrument.section:
                section = record.member.primary_instrument.section
                section_attendance[section]['count'] += 1
                section_attendance[section]['members'].add(record.member_id)
        
        metrics['section_attendance'] = dict(section_attendance)
        
        # Count guest attendance
        metrics['guest_attendance'] = metrics['attendance_records'].filter(
            member__isnull=True,
            guest_name__isnull=False
        ).count()
        
        # Find new members (joined in past 7 days)
        metrics['new_members'] = Member.objects.filter(
            join_date__gte=start_date,
            join_date__lte=end_date
        )
        
        # Find reactivated members (is_active set to True in past 7 days)
        metrics['reactivated_members'] = Member.objects.filter(
            reactivated_date__gte=start_date,
            reactivated_date__lte=end_date
        )
        
        # Get most attended members (top 5) with proper ordering
        # Use annotation on Member model to get consistent ordering by attendance count
        most_attended_ids = list(
            metrics['attendance_records']
            .filter(member__isnull=False)
            .values('member')
            .annotate(count=Count('id'))
            .order_by('-count')[:5]
        )
        # Preserve the order by creating the list in count order
        id_to_count = {item['member']: item['count'] for item in most_attended_ids}
        members = {m.id: m for m in Member.objects.filter(id__in=id_to_count.keys())}
        metrics['most_attended_members'] = [members[item['member']] for item in most_attended_ids if item['member'] in members]
        metrics['most_attended_counts'] = id_to_count
        
        # Calculate turnout % per section with optimized queries
        # Get active member counts per section in one query
        section_active_counts = dict(
            Member.objects.filter(
                is_active=True,
                primary_instrument__section__isnull=False
            ).values('primary_instrument__section').annotate(
                count=Count('id')
            ).values_list('primary_instrument__section', 'count')
        )
        
        section_turnout = {}
        for section in Section.objects.all():
            active_in_section = section_active_counts.get(section.id, 0)
            
            if active_in_section > 0:
                attended_in_section = len(section_attendance.get(section, {}).get('members', set()))
                turnout_pct = (attended_in_section / active_in_section) * 100
            else:
                turnout_pct = 0
            
            section_turnout[section] = {
                'attended': len(section_attendance.get(section, {}).get('members', set())),
                'active': active_in_section,
                'turnout_pct': turnout_pct,
            }
        
        metrics['section_turnout'] = section_turnout
        
        return metrics

    def _format_report_message(self, metrics):
        """Format the attendance report as an email message."""
        message = []
        message.append(f"Blowcomotion Weekly Attendance Report")
        message.append(f"Week of {metrics['start_date']} to {metrics['end_date']}")
        message.append("=" * 60)
        message.append("")
        
        # Total attendance
        message.append(f"TOTAL ATTENDANCE: {metrics['total_attendance']} unique member(s) attended")
        if metrics['guest_attendance']:
            message.append(f"GUEST ATTENDANCE: {metrics['guest_attendance']} guest(s)")
        message.append("")
        
        # Cleaned up members (marked as inactive)
        if metrics.get('cleaned_up_members'):
            cleanup_days = metrics.get('cleanup_days', 90)
            message.append(f"MEMBERS MARKED INACTIVE (no attendance for {cleanup_days}+ days):")
            message.append("-" * 40)
            for member in metrics['cleaned_up_members']:
                message.append(f"  • {member.full_name} (last seen: {member.last_seen})")
            message.append("")
        
        # Attendance by section
        message.append("ATTENDANCE BY SECTION:")
        message.append("-" * 40)
        for section, data in sorted(metrics['section_attendance'].items(), key=lambda x: x[0].name):
            count = data['count']
            members = len(data['members'])
            message.append(f"  {section.name}: {count} attendance record(s) ({members} unique member(s))")
        message.append("")
        
        # Turnout % per section
        message.append("TURNOUT PERCENTAGE BY SECTION:")
        message.append("-" * 40)
        for section, data in sorted(metrics['section_turnout'].items(), key=lambda x: x[0].name):
            attended = data['attended']
            active = data['active']
            turnout = data['turnout_pct']
            if active > 0:
                message.append(f"  {section.name}: {turnout:.1f}% ({attended}/{active} active members)")
            else:
                message.append(f"  {section.name}: N/A (no active members)")
        message.append("")
        
        # New members
        if metrics['new_members']:
            message.append("NEW MEMBERS (this week):")
            message.append("-" * 40)
            for member in metrics['new_members']:
                message.append(f"  • {member.full_name} ({member.primary_instrument.name if member.primary_instrument else 'No instrument'})")
            message.append("")
        
        # Reactivated members
        if metrics['reactivated_members']:
            message.append("REACTIVATED MEMBERS (this week):")
            message.append("-" * 40)
            for member in metrics['reactivated_members']:
                message.append(f"  • {member.full_name} ({member.primary_instrument.name if member.primary_instrument else 'No instrument'})")
            message.append("")
        
        # Most attended members
        if metrics['most_attended_members']:
            message.append("TOP 5 MOST ATTENDED:")
            message.append("-" * 40)
            # Use pre-computed counts from metrics
            member_attendance_counts = metrics.get('most_attended_counts', {})
            
            for i, member in enumerate(metrics['most_attended_members'], 1):
                count = member_attendance_counts.get(member.id, 0)
                message.append(f"  {i}. {member.full_name} - {count} attendance(s)")
            message.append("")
        
        message.append("=" * 60)
        message.append("End of report")
        
        return "\n".join(message)

    def handle(self, *args, **options):
        today = datetime.date.today()
        weekday = today.weekday()  # Monday=0, Sunday=6
        day_to_run = options['day_to_run']
        days_of_week = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
        
        # Check if this is the correct day to run
        if weekday != day_to_run:
            self.stdout.write(
                self.style.WARNING(
                    f'This command is intended to be run on {days_of_week[day_to_run]} only. Exiting.'
                )
            )
            return

        # Get site settings
        site_settings = self._get_site_settings()
        if not site_settings:
            self.stdout.write(self.style.ERROR('SiteSettings could not be loaded. Exiting.'))
            return

        # Run cleanup of inactive members
        self.stdout.write(self.style.SUCCESS('Running attendance cleanup...'))
        cleaned_up_members = self._cleanup_inactive_members(site_settings, dry_run=options['dry_run'])

        # Calculate metrics
        self.stdout.write(self.style.SUCCESS('Calculating attendance metrics...'))
        metrics = self._calculate_metrics()
        metrics['cleaned_up_members'] = cleaned_up_members
        metrics['cleanup_days'] = site_settings.attendance_cleanup_days
        
        # Format report
        self.stdout.write(self.style.SUCCESS('Formatting report...'))
        message = self._format_report_message(metrics)
        
        # Send email
        recipients = site_settings.attendance_report_notification_recipients
        if recipients:
            subject = f'Weekly Attendance Report - {metrics["end_date"]}'
            try:
                # Support comma or newline-separated recipients, strip whitespace, filter empty strings
                import re
                recipients_list = [r.strip() for r in re.split(r'[,\n]', recipients) if r.strip()]
            except AttributeError:
                recipients_list = [recipients] if recipients else []
            
            self.stdout.write(self.style.SUCCESS('Sending attendance report...'))
            self._send_mail(subject, message, recipients_list, dry_run=options['dry_run'])
        else:
            self.stdout.write(
                self.style.WARNING('No email recipients configured in Site Settings.')
            )
