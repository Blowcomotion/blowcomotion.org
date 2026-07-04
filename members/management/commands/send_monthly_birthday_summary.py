"""
Django management command to send birthday summary emails.

By default this command sends a monthly email digest with member birthdays
for a calendar month to designated recipients configured in SiteSettings.
It is intended to be run on the 1st of each month and is used for the
in-person shout out at the start of the month.

With --days it instead sends a rolling-window update of birthdays coming
up in the next N days (7 by default). This mode is intended to be run
weekly (e.g. via a scheduled task) so that the written weekly rehearsal
announcement has up-to-date birthday information, including for members
who joined recently. Like the monthly mode, it is meant to be scheduled
daily (PythonAnywhere only supports daily/hourly scheduling) and no-ops
on every day but Sunday.

Usage:
    # Monthly summary (run on the 1st of each month)
    python manage.py send_monthly_birthday_summary [--month MONTH] [--year YEAR] [--dry-run] [--ignore-date-check]

    # Rolling-window update (run daily, only sends on Sundays)
    python manage.py send_monthly_birthday_summary --days [DAYS] [--dry-run] [--ignore-date-check]

Options:
    --month: Month to generate summary for (1-12, default: current month)
    --year: Year to generate summary for (default: current year, or next year if month wraps)
    --days: Send a rolling-window update of birthdays in the next DAYS days
            instead of a calendar-month summary (default when the flag is
            given without a value: 7)
    --dry-run: Print what would be sent without actually sending emails
    --ignore-date-check: Bypass the first-day-of-month check (monthly mode)
            or the Sunday-only check (weekly --days mode); for manual/testing runs
"""

import calendar
import logging
from datetime import date, timedelta

from wagtail.models import Site

from django.conf import settings
from django.core.mail import send_mail
from django.core.management.base import BaseCommand, CommandError
from django.template.loader import render_to_string

from blowcomotion.models import Member, SiteSettings
from members.birthdays import get_birthday, get_next_year_birthday_info

logger = logging.getLogger(__name__)

DEFAULT_LOOKAHEAD_DAYS = 7


class Command(BaseCommand):
    help = (
        'Send birthday summary email to designated recipients. '
        'By default sends a calendar-month summary; with --days sends a '
        'rolling-window update of upcoming birthdays.'
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--month',
            type=int,
            help='Month to generate summary for (1-12, default: current month)',
        )
        parser.add_argument(
            '--year',
            type=int,
            help='Year to generate summary for (default: current year, or next year if month wraps)',
        )
        parser.add_argument(
            '--days',
            type=int,
            nargs='?',
            const=DEFAULT_LOOKAHEAD_DAYS,
            default=None,
            help=(
                'Send a rolling-window update of birthdays in the next DAYS days '
                f'instead of a calendar-month summary (default: {DEFAULT_LOOKAHEAD_DAYS})'
            ),
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Print what would be sent without actually sending emails',
        )
        parser.add_argument(
            '--ignore-date-check',
            action='store_true',
            help=(
                'Bypass the first-day-of-month check (monthly mode) or the '
                'Sunday-only check (weekly --days mode); for manual/testing runs'
            ),
        )

    def handle(self, *args, **options):
        """Main command handler"""
        try:
            today = date.today()
            days_ahead = options['days']
            verbosity = options.get('verbosity', 1)

            if days_ahead is not None:
                # Rolling-window mode (weekly update)
                if options['month'] or options['year']:
                    raise CommandError('--days cannot be combined with --month or --year')
                if days_ahead <= 0:
                    raise CommandError(f"--days must be a positive integer, got {days_ahead}")

                # PythonAnywhere only supports daily/hourly scheduling, so this is
                # scheduled to run daily and this check (like the 1st-of-month check
                # below) makes it a no-op except on the intended day.
                if not options['ignore_date_check'] and today.weekday() != 6:
                    self.stdout.write(
                        self.style.WARNING(
                            f'This command is intended to be run on Sundays only. '
                            f'Today is {today.strftime("%A, %B %d, %Y")}. Use --ignore-date-check to bypass this restriction.'
                        )
                    )
                    return

                future_date = today + timedelta(days=days_ahead)
                period_label = f'the next {days_ahead} day(s)'
                email_label = 'Weekly birthday update'

                if verbosity >= 1:
                    self.stdout.write(
                        self.style.SUCCESS(
                            f'Generating birthday update for {today.strftime("%B %d, %Y")} '
                            f'through {future_date.strftime("%B %d, %Y")}'
                        )
                    )
            else:
                # Calendar-month mode (monthly summary)
                # Check if it's the first day of the month (unless bypassed)
                if not options['ignore_date_check'] and today.day != 1:
                    self.stdout.write(
                        self.style.WARNING(
                            f'This command is intended to be run on the 1st of each month only. '
                            f'Today is {today.strftime("%B %d, %Y")}. Use --ignore-date-check to bypass this restriction.'
                        )
                    )
                    return

                if options['month'] and options['year']:
                    # Explicit month and year: use exactly as provided
                    target_month = options['month']
                    target_year = options['year']
                elif options['month']:
                    # Month only: choose a year so the target month is not in the past
                    target_month = options['month']
                    target_year = today.year
                    # If the specified month has already passed this year, roll to next year
                    if target_month < today.month:
                        target_year = today.year + 1
                else:
                    # No month specified: use the default "this month" period
                    target_month = today.month
                    target_year = today.year

                # Validate month
                if not (1 <= target_month <= 12):
                    raise CommandError(f"Month must be between 1 and 12, got {target_month}")

                month_name = calendar.month_name[target_month]
                period_label = f'{month_name} {target_year}'
                email_label = 'Monthly birthday summary'

                if verbosity >= 1:
                    self.stdout.write(
                        self.style.SUCCESS(
                            f'Generating birthday summary for {month_name} {target_year}'
                        )
                    )

            # Get site settings for email recipients
            site_settings = self._get_site_settings()
            if not site_settings:
                return

            recipients = site_settings.birthday_summary_email_recipients
            if not recipients:
                raise CommandError(
                    "No birthday email recipients configured. "
                    "Please add recipients in Django admin under Site Settings."
                )

            recipient_list = [email.strip() for email in recipients.split(',') if email.strip()]
            if not recipient_list:
                raise CommandError(
                    "No valid birthday email recipients configured. "
                    "Please add at least one valid email address in Django admin under Site Settings."
                )
            if verbosity >= 1:
                self.stdout.write(f'Recipients: {", ".join(recipient_list)}')

            # Get members with upcoming birthdays for the selected period
            if days_ahead is not None:
                upcoming_birthdays = self._get_birthdays_in_window(today, future_date)
            else:
                upcoming_birthdays = self._get_upcoming_birthdays(target_month, target_year)

            if verbosity >= 1:
                self.stdout.write(
                    f'Found {len(upcoming_birthdays)} birthday(s) in {period_label}'
                )

            # Skip email if no birthdays
            if not upcoming_birthdays:
                self.stdout.write(
                    self.style.WARNING(
                        f'No birthdays scheduled for {period_label}. Skipping email.'
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

            # Generate email content
            if days_ahead is not None:
                context = {
                    'upcoming_birthdays': upcoming_birthdays,
                    'today': today,
                    'future_date': future_date,
                    'days_ahead': days_ahead,
                    'members_with_age': len([b for b in upcoming_birthdays if b.get('age')]),
                }
                template_name = 'emails/weekly_birthday_summary.html'
                subject = f"Weekly Birthday Update - {today.strftime('%B %d, %Y')}"
            else:
                context = {
                    'upcoming_birthdays': upcoming_birthdays,
                    'month_name': month_name,
                    'year': target_year,
                    'members_with_age': len([b for b in upcoming_birthdays if b.get('age')]),
                }
                template_name = 'emails/monthly_birthday_summary.html'
                subject = f"Monthly Birthday Summary - {month_name} {target_year}"

            try:
                html_content = render_to_string(template_name, context)
                if days_ahead is not None:
                    text_content = self._generate_window_text_content(context)
                else:
                    text_content = self._generate_text_content(context)
            except Exception as e:
                logger.error(f"Error rendering email template: {str(e)}")
                raise CommandError(f"Error rendering email template: {str(e)}")

            if options['dry_run']:
                self.stdout.write(self.style.WARNING('DRY RUN - Email would be sent with:'))
                self.stdout.write(f'Subject: {subject}')
                self.stdout.write(f'Recipients: {", ".join(recipient_list)}')
                self.stdout.write('Text content preview:')
                self.stdout.write('-' * 50)
                self.stdout.write(text_content[:500] + '...' if len(text_content) > 500 else text_content)
                self.stdout.write('-' * 50)
                return

            # Send email
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
                    f"{email_label} sent successfully for {period_label} "
                    f"to {len(recipient_list)} recipient(s)"
                )

                if verbosity >= 1:
                    self.stdout.write(
                        self.style.SUCCESS(
                            f'✅ {email_label} sent successfully to {len(recipient_list)} recipient(s)'
                        )
                    )

            except Exception as e:
                logger.error(f"Error sending birthday summary email: {str(e)}")
                raise CommandError(f"Error sending email: {str(e)}")

        except CommandError:
            raise
        except Exception as e:
            logger.error(f"Unexpected error in send_monthly_birthday_summary command: {str(e)}")
            raise CommandError(f"Unexpected error: {str(e)}")

    def _get_upcoming_birthdays(self, target_month, target_year):
        """Get all members with birthdays in the specified month"""
        # Get all active members with birthday information for the target month
        members_with_birthdays = Member.objects.filter(
            is_active=True,
            birth_month=target_month,
            birth_day__isnull=False,
        ).select_related('primary_instrument').prefetch_related('additional_instruments__instrument').order_by('birth_day', 'first_name', 'last_name')

        upcoming_birthdays = []

        for member in members_with_birthdays:
            # Create birthday for the target year
            birthday_this_year = get_birthday(target_year, member.birth_month, member.birth_day)
            if birthday_this_year is None:
                # Skip invalid dates (shouldn't happen since we filter by month)
                continue

            # Calculate age if birth year is available
            age = None
            if member.birth_year:
                age = target_year - member.birth_year

            birthday_info = {
                'member': member,
                'birthday': birthday_this_year,
                'age': age,
                'instruments': self._get_instrument_names(member),
            }

            upcoming_birthdays.append(birthday_info)

        return upcoming_birthdays

    def _get_birthdays_in_window(self, today, future_date):
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

            birthday_info['member'] = member
            birthday_info['instruments'] = self._get_instrument_names(member)

            upcoming_birthdays.append(birthday_info)

        upcoming_birthdays.sort(key=lambda b: b['birthday'])

        return upcoming_birthdays

    def _get_instrument_names(self, member):
        """Collect primary and additional instrument names for a member"""
        instrument_names = []
        if member.primary_instrument:
            instrument_names.append(member.primary_instrument.name)
        instrument_names.extend([inst.instrument.name for inst in member.additional_instruments.all()])
        return instrument_names

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
        """Generate plain text version of the monthly email"""
        upcoming_birthdays = context['upcoming_birthdays']
        month_name = context['month_name']
        year = context['year']

        text_lines = [
            f"Monthly Birthday Summary - {month_name} {year}",
            "=" * 50,
            "",
            f"Here are the upcoming birthdays for {month_name} {year}.",
            "Don't forget to celebrate our amazing band members!",
            "",
        ]

        if upcoming_birthdays:
            text_lines.append(f"🎉 Upcoming Birthdays ({len(upcoming_birthdays)} total):")
            text_lines.append("")
            text_lines.extend(self._format_birthday_lines(upcoming_birthdays))
        else:
            text_lines.extend([
                f"🎈 No birthdays scheduled for {month_name} {year}.",
                "Enjoy the break from birthday celebrations!",
                "",
            ])

        text_lines.extend([
            "",
            "Start Wearing Purple,",
            "Blowcomotion Band Management",
            "",
            "This is an automated monthly birthday summary.",
            "For questions, contact the band leadership.",
        ])

        return "\n".join(text_lines)

    def _generate_window_text_content(self, context):
        """Generate plain text version of the rolling-window update email"""
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
            text_lines.extend(self._format_birthday_lines(upcoming_birthdays))
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

    def _format_birthday_lines(self, upcoming_birthdays):
        """Format the per-member birthday lines shared by both text emails"""
        text_lines = []
        for birthday in upcoming_birthdays:
            member = birthday['member']

            # Format name with preferred name if available
            if member.preferred_name:
                name = f'"{member.preferred_name}" {member.first_name} {member.last_name}'
            else:
                name = f'{member.first_name} {member.last_name}'

            # Format birthday date
            birthday_date = birthday['birthday'].strftime('%B %d')

            # Add age if available
            age_info = f" - Turning {birthday['age']}" if birthday.get('age') else ""
            instruments = birthday.get('instruments', [])
            instruments_info = f" (🎵 {', '.join(instruments)})" if instruments else ""

            text_lines.append(f"• {name}")
            text_lines.append(f"  {birthday_date}{age_info}{instruments_info}")
            text_lines.append("")
        return text_lines
