"""
Django management command to send weekly birthday update emails.

This command sends a rolling-window email digest of upcoming member
birthdays to designated recipients configured in SiteSettings. It is
intended to be run weekly (e.g. via a scheduled task) so that the written
weekly rehearsal announcement has up-to-date birthday information for
members who joined recently, in addition to the monthly summary used for
the in-person shout out.

Usage:
    python manage.py send_weekly_birthday_summary [--days DAYS] [--dry-run]

Options:
    --days: Number of days ahead to look for upcoming birthdays (default: 30)
    --dry-run: Print what would be sent without actually sending emails
"""

import logging
from datetime import date, timedelta

from wagtail.models import Site

from django.conf import settings
from django.core.mail import send_mail
from django.core.management.base import BaseCommand, CommandError
from django.template.loader import render_to_string

from blowcomotion.models import Member, SiteSettings
from blowcomotion.views import (
    BIRTHDAY_RANGE_DAYS,
    get_birthday,
    get_next_year_birthday_info,
)

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Send weekly birthday update email to designated recipients'

    def add_arguments(self, parser):
        parser.add_argument(
            '--days',
            type=int,
            default=BIRTHDAY_RANGE_DAYS,
            help=f'Number of days ahead to look for upcoming birthdays (default: {BIRTHDAY_RANGE_DAYS})',
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Print what would be sent without actually sending emails',
        )

    def handle(self, *args, **options):
        """Main command handler"""
        try:
            today = date.today()
            days_ahead = options['days']
            if days_ahead <= 0:
                raise CommandError(f"--days must be a positive integer, got {days_ahead}")
            future_date = today + timedelta(days=days_ahead)

            verbosity = options.get('verbosity', 1)
            if verbosity >= 1:
                self.stdout.write(
                    self.style.SUCCESS(
                        f'Generating weekly birthday update for {today.strftime("%B %d, %Y")} '
                        f'through {future_date.strftime("%B %d, %Y")}'
                    )
                )

            # Get site settings for email recipients
            site_settings = self._get_site_settings()
            if not site_settings:
                return

            recipients = site_settings.weekly_birthday_summary_email_recipients
            if not recipients:
                raise CommandError(
                    "No weekly birthday email recipients configured. "
                    "Please add recipients in Django admin under Site Settings."
                )

            recipient_list = [email.strip() for email in recipients.split(',') if email.strip()]
            if not recipient_list:
                raise CommandError(
                    "No valid weekly birthday email recipients configured. "
                    "Please add at least one valid email address in Django admin under Site Settings."
                )
            if verbosity >= 1:
                self.stdout.write(f'Recipients: {", ".join(recipient_list)}')

            upcoming_birthdays = self._get_upcoming_birthdays(today, future_date)

            if verbosity >= 1:
                self.stdout.write(
                    f'Found {len(upcoming_birthdays)} birthday(s) in the next {days_ahead} day(s)'
                )

            if not upcoming_birthdays:
                self.stdout.write(
                    self.style.WARNING(
                        f'No birthdays scheduled in the next {days_ahead} day(s). Skipping email.'
                    )
                )
                return

            for birthday in upcoming_birthdays:
                member = birthday['member']
                birthday_date = birthday['birthday']
                age_info = f" (turning {birthday['age']})" if birthday.get('age') else ""
                instrument_names = birthday.get('instruments', [])
                instruments_info = f" - {', '.join(instrument_names)}" if instrument_names else ""
                if verbosity >= 1:
                    self.stdout.write(
                        f"  • {member.first_name} {member.last_name} - "
                        f"{birthday_date.strftime('%B %d')}{age_info}{instruments_info}"
                    )

            context = {
                'upcoming_birthdays': upcoming_birthdays,
                'today': today,
                'future_date': future_date,
                'days_ahead': days_ahead,
                'members_with_age': len([b for b in upcoming_birthdays if b.get('age')]),
            }

            try:
                html_content = render_to_string('emails/weekly_birthday_summary.html', context)
                text_content = self._generate_text_content(context)
            except Exception as e:
                logger.error(f"Error rendering email template: {str(e)}")
                raise CommandError(f"Error rendering email template: {str(e)}")

            subject = f"Weekly Birthday Update - {today.strftime('%B %d, %Y')}"

            if options['dry_run']:
                self.stdout.write(self.style.WARNING('DRY RUN - Email would be sent with:'))
                self.stdout.write(f'Subject: {subject}')
                self.stdout.write(f'Recipients: {", ".join(recipient_list)}')
                self.stdout.write('Text content preview:')
                self.stdout.write('-' * 50)
                self.stdout.write(text_content[:500] + '...' if len(text_content) > 500 else text_content)
                self.stdout.write('-' * 50)
                return

            try:
                send_mail(
                    subject=subject,
                    message=text_content,
                    html_message=html_content,
                    from_email=settings.FROM_EMAIL,
                    recipient_list=recipient_list,
                    fail_silently=False,
                )
                # Send a copy for verifying functionality
                extra_email = settings.FORM_TEST_EMAIL if hasattr(settings, 'FORM_TEST_EMAIL') else None
                if extra_email:
                    send_mail(
                        subject=f"[COPY] {subject}",
                        message=text_content,
                        html_message=html_content,
                        from_email=settings.FROM_EMAIL,
                        recipient_list=[extra_email],
                        fail_silently=False,
                    )
                logger.info(
                    f"Weekly birthday update sent successfully for {today.strftime('%B %d, %Y')} "
                    f"to {len(recipient_list)} recipient(s)"
                )

                if verbosity >= 1:
                    self.stdout.write(
                        self.style.SUCCESS(
                            f'✅ Weekly birthday update sent successfully to {len(recipient_list)} recipient(s)'
                        )
                    )

            except Exception as e:
                logger.error(f"Error sending weekly birthday update email: {str(e)}")
                raise CommandError(f"Error sending email: {str(e)}")

        except CommandError:
            raise
        except Exception as e:
            logger.error(f"Unexpected error in send_weekly_birthday_summary command: {str(e)}")
            raise CommandError(f"Unexpected error: {str(e)}")

    def _get_upcoming_birthdays(self, today, future_date):
        """Get all active members with a birthday between today and future_date (inclusive)."""
        relevant_months = set()
        current_date = today
        while current_date <= future_date:
            relevant_months.add(current_date.month)
            current_date += timedelta(days=1)

        members_with_birthdays = Member.objects.filter(
            is_active=True,
            birth_month__isnull=False,
            birth_day__isnull=False,
            birth_month__in=relevant_months,
        ).select_related('primary_instrument').prefetch_related('additional_instruments__instrument').order_by('first_name', 'last_name')

        upcoming_birthdays = []

        for member in members_with_birthdays:
            birthday_this_year = get_birthday(today.year, member.birth_month, member.birth_day)
            if birthday_this_year is None:
                continue

            birthday_info = None

            if today <= birthday_this_year <= future_date:
                age = None
                if member.birth_year:
                    age = today.year - member.birth_year
                birthday_info = {
                    'birthday': birthday_this_year,
                    'days_until': (birthday_this_year - today).days,
                    'age': age,
                }
            elif birthday_this_year < today:
                next_year_info = get_next_year_birthday_info(member, today, future_date)
                if next_year_info:
                    birthday_info = next_year_info

            if birthday_info is None:
                continue

            instrument_names = []
            if member.primary_instrument:
                instrument_names.append(member.primary_instrument.name)
            instrument_names.extend([inst.instrument.name for inst in member.additional_instruments.all()])

            birthday_info['member'] = member
            birthday_info['instruments'] = instrument_names

            upcoming_birthdays.append(birthday_info)

        upcoming_birthdays.sort(key=lambda b: b['birthday'])

        return upcoming_birthdays

    def _get_site_settings(self):
        """Retrieve SiteSettings using the established pattern for multi-site configurations"""
        try:
            site = Site.objects.filter(is_default_site=True).select_related('root_page').first()
            if not site:
                site = Site.objects.select_related('root_page').first()
            if not site:
                self.stdout.write(self.style.ERROR('No Site configured. Cannot load SiteSettings.'))
                return None
            return SiteSettings.for_site(site)
        except Exception as exc:
            logger.error(f'Error retrieving SiteSettings: {exc}')
            self.stdout.write(self.style.ERROR(f'Error retrieving SiteSettings: {exc}'))
            return None

    def _generate_text_content(self, context):
        """Generate plain text version of the email"""
        upcoming_birthdays = context['upcoming_birthdays']
        today = context['today']
        days_ahead = context['days_ahead']

        text_lines = [
            f"Weekly Birthday Update - {today.strftime('%B %d, %Y')}",
            "=" * 50,
            "",
            f"Here are the upcoming birthdays for the next {days_ahead} days.",
            "",
        ]

        if upcoming_birthdays:
            text_lines.append(f"🎉 Upcoming Birthdays ({len(upcoming_birthdays)} total):")
            text_lines.append("")

            for birthday in upcoming_birthdays:
                member = birthday['member']

                if member.preferred_name:
                    name = f'"{member.preferred_name}" {member.first_name} {member.last_name}'
                else:
                    name = f'{member.first_name} {member.last_name}'

                birthday_date = birthday['birthday'].strftime('%B %d')

                age_info = f" - Turning {birthday['age']}" if birthday.get('age') else ""
                instruments = birthday.get('instruments', [])
                instruments_info = f" (🎵 {', '.join(instruments)})" if instruments else ""

                text_lines.append(f"• {name}")
                text_lines.append(f"  {birthday_date}{age_info}{instruments_info}")
                text_lines.append("")
        else:
            text_lines.extend([
                f"🎈 No birthdays scheduled in the next {days_ahead} days.",
                "",
            ])

        text_lines.extend([
            "",
            "Start Wearing Purple,",
            "Blowcomotion Band Management",
            "",
            "This is an automated weekly birthday update.",
            "For questions, contact the band leadership.",
        ])

        return "\n".join(text_lines)
