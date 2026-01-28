"""
Django management command to send monthly birthday summary emails.

This command sends a monthly email digest with upcoming member birthdays
to designated recipients configured in SiteSettings.

Usage:
    python manage.py send_monthly_birthday_summary [--month MONTH] [--year YEAR] [--dry-run] [--ignore-date-check]

Options:
    --month: Month to generate summary for (1-12, default: next month)
    --year: Year to generate summary for (default: current year, or next year if month wraps)
    --dry-run: Print what would be sent without actually sending emails
    --ignore-date-check: Bypass the first-day-of-month check (for manual/testing runs)
"""

import calendar
import logging
from datetime import date

from wagtail.models import Site

from django.core.mail import send_mail
from django.core.management.base import BaseCommand, CommandError
from django.template.loader import render_to_string

from blowcomotion.models import Member, SiteSettings
from blowcomotion.views import get_birthday

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Send monthly birthday summary email to designated recipients'

    def add_arguments(self, parser):
        parser.add_argument(
            '--month',
            type=int,
            help='Month to generate summary for (1-12, default: next month)',
        )
        parser.add_argument(
            '--year',
            type=int,
            help='Year to generate summary for (default: current year, or next year if month wraps)',
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Print what would be sent without actually sending emails',
        )
        parser.add_argument(
            '--ignore-date-check',
            action='store_true',
            help='Bypass the first-day-of-month check (for manual/testing runs)',
        )

    def handle(self, *args, **options):
        """Main command handler"""
        try:
            # Determine target month and year
            today = date.today()
            
            # Check if it's the first day of the month (unless bypassed)
            if not options['ignore_date_check'] and today.day != 1:
                self.stdout.write(
                    self.style.WARNING(
                        f'This command is intended to be run on the 1st of each month only. '
                        f'Today is {today.strftime("%B %d, %Y")}. Use --ignore-date-check to bypass this restriction.'
                    )
                )
                return
            
            # First, compute the default target period: next month from today
            if today.month == 12:
                default_month = 1
                default_year = today.year + 1
            else:
                default_month = today.month + 1
                default_year = today.year

            if options['month'] and options['year']:
                # Explicit month and year: use exactly as provided
                target_month = options['month']
                target_year = options['year']
            elif options['month']:
                # Month only: choose a year so the target month is not in the past
                target_month = options['month']
                # Start with the current year; if that month has already passed, roll to next year
                target_year = today.year
                # Compare year and month only to determine if month has passed
                if target_year < today.year or (target_year == today.year and target_month < today.month):
                    target_year = today.year + 1
            else:
                # No month specified: use the default "next month" period
                target_month = default_month
                target_year = default_year

            # Validate month
            if not (1 <= target_month <= 12):
                raise CommandError(f"Month must be between 1 and 12, got {target_month}")

            month_name = calendar.month_name[target_month]
            
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
            self.stdout.write(f'Recipients: {", ".join(recipient_list)}')

            # Get members with birthdays in the target month
            upcoming_birthdays = self._get_upcoming_birthdays(target_month, target_year)
            
            self.stdout.write(
                f'Found {len(upcoming_birthdays)} birthday(s) in {month_name} {target_year}'
            )

            # Skip email if no birthdays
            if not upcoming_birthdays:
                self.stdout.write(
                    self.style.WARNING(
                        f'No birthdays scheduled for {month_name} {target_year}. Skipping email.'
                    )
                )
                return

            for birthday in upcoming_birthdays:
                member = birthday['member']
                birthday_date = birthday['birthday']
                age_info = f" (turning {birthday['age']})" if birthday.get('age') else ""
                instrument_names = birthday.get('instruments', [])
                instruments_info = f" - {', '.join(instrument_names)}" if instrument_names else ""
                
                self.stdout.write(
                    f"  • {member.first_name} {member.last_name} - "
                    f"{birthday_date.strftime('%B %d')}{age_info}{instruments_info}"
                )

            # Generate email content
            context = {
                'upcoming_birthdays': upcoming_birthdays,
                'month_name': month_name,
                'year': target_year,
                'members_with_age': len([b for b in upcoming_birthdays if b.get('age')]),
            }

            try:
                html_content = render_to_string('emails/monthly_birthday_summary.html', context)
                text_content = self._generate_text_content(context)
                
            except Exception as e:
                logger.error(f"Error rendering email template: {str(e)}")
                raise CommandError(f"Error rendering email template: {str(e)}")

            subject = f"Monthly Birthday Summary - {month_name} {target_year}"

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
                    from_email='website@blowcomotion.org',
                    recipient_list=recipient_list,
                    fail_silently=False,
                )
                
                logger.info(
                    f"Monthly birthday summary sent successfully for {month_name} {target_year} "
                    f"to {len(recipient_list)} recipient(s): {', '.join(recipient_list)}"
                )
                
                self.stdout.write(
                    self.style.SUCCESS(
                        f'✅ Monthly birthday summary sent successfully to {len(recipient_list)} recipient(s)'
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

            instrument_names = []
            if member.primary_instrument:
                instrument_names.append(member.primary_instrument.name)
            instrument_names.extend([inst.instrument.name for inst in member.additional_instruments.all()])

            birthday_info = {
                'member': member,
                'birthday': birthday_this_year,
                'age': age,
                'instruments': instrument_names,
            }

            upcoming_birthdays.append(birthday_info)

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