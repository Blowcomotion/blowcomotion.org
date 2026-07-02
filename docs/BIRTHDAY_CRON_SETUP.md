# Birthday Summary Cron Job Setup

This document explains how to set up the monthly and weekly birthday summary emails as scheduled tasks.

## Overview

Two management commands automatically send birthday email digests to designated recipients:

- `send_monthly_birthday_summary` sends a summary of birthdays for a calendar month. It is intended to be run on the 1st of each month and is used for the in-person shout out at the start of the month.
- `send_weekly_birthday_summary` sends a rolling-window update of birthdays coming up in the next N days (30 by default). It is intended to be run weekly so the written weekly rehearsal announcement has up-to-date birthday information, including for members who joined recently.

## Command Usage

```bash
# Monthly: send summary for next month (default behavior)
python manage.py send_monthly_birthday_summary

# Monthly: send summary for specific month and year
python manage.py send_monthly_birthday_summary --month 9 --year 2025

# Monthly: dry run (preview without sending)
python manage.py send_monthly_birthday_summary --dry-run

# Weekly: send update for birthdays in the next 30 days (default)
python manage.py send_weekly_birthday_summary

# Weekly: send update for birthdays in a custom lookahead window
python manage.py send_weekly_birthday_summary --days 14

# Weekly: dry run (preview without sending)
python manage.py send_weekly_birthday_summary --dry-run
```

## Configuration

### 1. Email Recipients

Configure email recipients in Django admin:

1. Go to **Settings** → **Site Settings**
2. In the **Form Email Recipients** section, set **Birthday summary email recipients** (used by the monthly command) and/or **Weekly birthday summary email recipients** (used by the weekly command)
3. Enter comma-separated email addresses: `admin@blowcomotion.org, leadership@blowcomotion.org`

### 2. Email Backend

Ensure Django is configured with a proper email backend in production settings:

```python
# In production settings
EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
EMAIL_HOST = 'your-smtp-server.com'
EMAIL_PORT = 587
EMAIL_USE_TLS = True
EMAIL_HOST_USER = 'your-email@blowcomotion.org'
EMAIL_HOST_PASSWORD = 'your-password'
```

## Cron Job Setup

### Option 1: System Crontab

Add to system crontab to run the monthly summary on the 1st of each month at 9:00 AM, and the weekly update every Monday at 9:00 AM:

```bash
# Edit crontab
crontab -e

# Add these lines (adjust paths as needed)
0 9 1 * * /path/to/your/venv/bin/python /path/to/blowcomotion.org/manage.py send_monthly_birthday_summary
0 9 * * 1 /path/to/your/venv/bin/python /path/to/blowcomotion.org/manage.py send_weekly_birthday_summary
```

### Option 2: Django Settings Crontab (if using django-crontab)

```python
# In settings.py
CRONJOBS = [
    ('0 9 1 * *', 'django.core.management.call_command', ['send_monthly_birthday_summary']),
    ('0 9 * * 1', 'django.core.management.call_command', ['send_weekly_birthday_summary']),
]
```

### Option 3: PythonAnywhere Scheduled Tasks

In the PythonAnywhere dashboard, under **Tasks**, add one scheduled task per command:

- `send_monthly_birthday_summary` — schedule daily at 9:00 AM; the command checks that it's the 1st of the month before sending, so it is a no-op on other days
- `send_weekly_birthday_summary` — schedule weekly, at a time that runs shortly before the weekly rehearsal announcement is written. Unlike the monthly command, this command has no built-in date check, so scheduling it more often than weekly will re-send the same upcoming-birthday digest to recipients.

Command to enter for each task (adjust the path to your virtualenv and project):

```bash
/path/to/your/venv/bin/python /path/to/blowcomotion.org/manage.py send_weekly_birthday_summary
```

### Option 4: Systemd Timer (Modern Linux Systems)

Create `/etc/systemd/system/birthday-summary.service`:

```ini
[Unit]
Description=Send Monthly Birthday Summary
After=network.target

[Service]
Type=oneshot
User=www-data
WorkingDirectory=/path/to/blowcomotion.org
Environment=DJANGO_SETTINGS_MODULE=blowcomotion.settings.production
ExecStart=/path/to/your/venv/bin/python manage.py send_monthly_birthday_summary
```

Create `/etc/systemd/system/birthday-summary.timer`:

```ini
[Unit]
Description=Run Birthday Summary Monthly
Requires=birthday-summary.service

[Timer]
OnCalendar=*-*-01 09:00:00
Persistent=true

[Install]
WantedBy=timers.target
```

Enable and start:

```bash
sudo systemctl enable birthday-summary.timer
sudo systemctl start birthday-summary.timer
```

## Testing

### Test the Command

```bash
# Test with dry run combined with --ignore-date-check (bypasses the 1st-of-month date check for testing)
python manage.py send_monthly_birthday_summary --dry-run --ignore-date-check

# Test a specific month with dry run and --ignore-date-check (bypasses the 1st-of-month date check for testing)
python manage.py send_monthly_birthday_summary --month 9 --year 2025 --dry-run --ignore-date-check

# Test actual sending on the 1st (command only sends on the 1st due to a safety check; use --ignore-date-check to bypass this)
python manage.py send_monthly_birthday_summary --month 9 --year 2025

# Force actual sending on any day (bypasses the 1st-of-month safety check; be very careful in production)
python manage.py send_monthly_birthday_summary --month 9 --year 2025 --ignore-date-check

# Weekly: dry run for the default 30-day lookahead window
python manage.py send_weekly_birthday_summary --dry-run

# Weekly: dry run for a custom lookahead window
python manage.py send_weekly_birthday_summary --days 14 --dry-run
```

### Run Tests

```bash
python manage.py test blowcomotion.tests.test_birthday_command
python manage.py test blowcomotion.tests.test_weekly_birthday_command
```

## Monitoring

### Logs

The command logs all activity. Check logs for:
- Successful sends
- Error conditions
- Member birthday information

### Email Delivery

Monitor email delivery success and ensure:
- Recipients receive emails
- HTML formatting displays correctly
- All member information is accurate

## Troubleshooting

### Common Issues

1. **No recipients configured**
   - Error: "No birthday email recipients configured"
   - Solution: Add recipients in Django admin Site Settings

2. **No SiteSettings found**
   - Error: "No SiteSettings found"
   - Solution: Create SiteSettings in Django admin

3. **Email sending fails**
   - Check Django email configuration
   - Verify SMTP settings
   - Check network connectivity

4. **Template rendering errors**
   - Verify template files exist: `templates/emails/monthly_birthday_summary.html` and `templates/emails/weekly_birthday_summary.html`
   - Check template syntax

5. **Weekly recipients not configured**
   - Error: "No weekly birthday email recipients configured"
   - Solution: Set **Weekly birthday summary email recipients** in Django admin Site Settings (this is a separate field from the monthly recipients)

### Debug Mode

Use dry-run mode to debug without sending emails:

```bash
python manage.py send_monthly_birthday_summary --dry-run
python manage.py send_weekly_birthday_summary --dry-run
```

## Features

- **Automatic monthly scheduling**: Runs on 1st of each month by default
- **Rolling weekly lookahead**: Weekly command surfaces birthdays in the next N days (30 by default) regardless of calendar month boundaries
- **Professional HTML emails**: Responsive design with band branding
- **Member details**: Names, preferred names, instruments, ages
- **Flexible scheduling**: Can specify any month/year (monthly) or lookahead window (weekly)
- **Comprehensive logging**: All activities logged for monitoring
- **Error handling**: Graceful handling of invalid dates and email failures
- **Dry-run mode**: Test without sending emails

## Email Content

The monthly summary includes:
- All active members with birthdays in the target month
- Member names (with preferred names when available)
- Birthday dates
- Ages (when birth year is available)
- Instruments played
- Professional Blowcomotion branding
- Both HTML and plain text versions

The weekly update includes the same member details, but for birthdays falling within the next N days (30 by default) from today, rather than a fixed calendar month. This keeps the weekly rehearsal announcement current even for members who join partway through the month.