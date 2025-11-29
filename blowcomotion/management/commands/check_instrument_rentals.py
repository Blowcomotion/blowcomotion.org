"""
Management command to check instrument rental status and send notifications.

This command checks for:
1. Renters who haven't been seen at rehearsal/performance for 3+ weeks
2. Instruments that need rental review (6- or 12-month date has passed)

Run this command regularly (e.g., monthly via cron) to send notification emails.
"""
import datetime

from wagtail.models import Site

from django.core.mail import send_mail
from django.core.management.base import BaseCommand

from blowcomotion.models import LibraryInstrument, SiteSettings


class Command(BaseCommand):
    help = 'Check instrument rental status and send notification emails'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Print notifications without sending emails',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        
        # Get email recipients from site settings
        site_settings = self._get_site_settings()
        if not site_settings:
            return

        recipients = self._get_recipients(site_settings)
        if not recipients:
            self.stdout.write(
                self.style.WARNING('No email recipients configured in Site Settings')
            )
            return
        
        # Check for inactive renters
        inactive_renters = self._check_inactive_renters()
        
        # Check for instruments needing review
        needs_review = self._check_review_needed()
        
        # Send notifications if any issues found
        if inactive_renters or needs_review:
            self._send_notifications(
                inactive_renters,
                needs_review,
                recipients,
                dry_run
            )
        else:
            self.stdout.write(
                self.style.SUCCESS('No rental issues found - all good!')
            )
    
    def _check_inactive_renters(self):
        """
        Find rented instruments where the member hasn't been seen in 3+ weeks.
        """
        inactive = []
        rented_instruments = LibraryInstrument.objects.filter(
            status=LibraryInstrument.STATUS_RENTED,
            member__isnull=False
        ).select_related('instrument', 'member')
        
        for instrument in rented_instruments:
            if instrument.renter_inactive:
                days_since_seen = (
                    datetime.date.today() - instrument.member.last_seen
                ).days
                inactive.append({
                    'instrument': instrument,
                    'member': instrument.member,
                    'days_since_seen': days_since_seen,
                })
                self.stdout.write(
                    self.style.WARNING(
                        f'⚠️  {instrument.member.full_name} renting '
                        f'{instrument.instrument.name} - not seen for {days_since_seen} days'
                    )
                )
        
        return inactive
    
    def _check_review_needed(self):
        """Find instruments that need review at 6-month or 12-month cycles."""
        needs_review = []
        today = datetime.date.today()
        rented_instruments = LibraryInstrument.objects.filter(
            status=LibraryInstrument.STATUS_RENTED
        ).select_related('instrument', 'member')

        for instrument in rented_instruments:
            overdue_checks = []
            for label, review_date in instrument.review_schedule.items():
                if review_date and today >= review_date:
                    overdue_checks.append(
                        {
                            'label': label,
                            'review_date': review_date,
                            'days_overdue': (today - review_date).days,
                        }
                    )

            if overdue_checks:
                needs_review.append(
                    {
                        'instrument': instrument,
                        'member': instrument.member,
                        'rental_date': instrument.rental_date,
                        'checks': overdue_checks,
                    }
                )
                overdue_strings = ", ".join(
                    f"{check['label']} ({check['days_overdue']} days overdue)"
                    for check in overdue_checks
                )
                self.stdout.write(
                    self.style.WARNING(
                        f"📅 {instrument.instrument.name} rented to "
                        f"{instrument.member.full_name if instrument.member else 'Unknown'} - "
                        f"reviews overdue: {overdue_strings}"
                    )
                )

        return needs_review
    
    def _send_notifications(self, inactive_renters, needs_review, recipients, dry_run):
        """
        Send email notifications about rental issues.
        """
        subject = 'Instrument Library Rental Notifications'
        message_parts = ['Instrument Library Rental Report\n', '=' * 50, '\n\n']

        if inactive_renters:
            message_parts.extend([
                'INACTIVE RENTERS (Not seen for 3+ weeks):\n',
                '-' * 50,
                '\n',
            ])
            for item in inactive_renters:
                member = item['member']
                member_display = member.full_name if member else 'Unknown'
                last_seen = member.last_seen if member and member.last_seen else 'Unknown'
                email = member.email if member and member.email else 'No email on file'
                phone = member.phone if member and member.phone else 'No phone on file'
                message_parts.append(
                    f"• {member_display} - {item['instrument'].instrument.name}\n"
                    f"  Serial: {item['instrument'].serial_number}\n"
                    f"  Last seen: {last_seen} ({item['days_since_seen']} days ago)\n"
                    f"  Email: {email}\n"
                    f"  Phone: {phone}\n\n"
                )

        if needs_review:
            if inactive_renters:
                message_parts.append('\n')
            message_parts.extend([
                'RENTALS NEEDING REVIEW:\n',
                '-' * 50,
                '\n',
            ])
            for item in needs_review:
                member = item['member']
                member_display = member.full_name if member else 'Unknown'
                email = member.email if member and member.email else 'N/A'
                phone = member.phone if member and member.phone else 'N/A'
                message_parts.append(
                    f"• {item['instrument'].instrument.name} - {member_display}\n"
                    f"  Serial: {item['instrument'].serial_number}\n"
                    f"  Rental date: {item['rental_date'] or 'Unknown'}\n"
                )
                for check in item['checks']:
                    message_parts.append(
                        f"  {check['label']} review date: {check['review_date']} ("
                        f"{check['days_overdue']} days overdue)\n"
                    )
                message_parts.append(
                    f"  Email: {email}\n  Phone: {phone}\n\n"
                )

        message_parts.extend([
            '\n',
            'Please follow up on these rentals as needed.\n\n',
            'Start Wearing Purple,\n',
            'Blowcomotion Instrument Library System',
        ])

        message = ''.join(message_parts)

        if dry_run:
            self.stdout.write(self.style.SUCCESS('\n--- DRY RUN MODE ---'))
            self.stdout.write(f"Would send to: {', '.join(recipients)}")
            self.stdout.write(f'Subject: {subject}')
            self.stdout.write(f'\n{message}')
            return

        try:
            send_mail(
                subject=subject,
                message=message,
                from_email='info@blowcomotion.org',
                recipient_list=recipients,
                fail_silently=False,
            )
            self.stdout.write(
                self.style.SUCCESS(
                    f'✅ Notification email sent to {len(recipients)} recipient(s)'
                )
            )
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'Error sending email: {e}')
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

    def _get_recipients(self, site_settings):
        raw_recipients = (
            site_settings.instrument_rental_notification_recipients
            or site_settings.contact_form_email_recipients
            or ''
        )
        recipients = [email.strip() for email in raw_recipients.replace('\n', ',').split(',') if email.strip()]
        return recipients
