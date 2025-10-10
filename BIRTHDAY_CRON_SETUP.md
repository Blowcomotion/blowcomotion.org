# Monthly Birthday Summary Cron Job Setup

This document explains how to set up the monthly birthday summary email as a cron job.

## Overview

The `send_monthly_birthday_summary` management command automatically sends a monthly email digest with upcoming member birthdays to designated recipients.

## Command Usage

```bash
# Send summary for next month (default behavior)
python manage.py send_monthly_birthday_summary

# Send summary for specific month and year
python manage.py send_monthly_birthday_summary --month 9 --year 2025

# Dry run (preview without sending)
python manage.py send_monthly_birthday_summary --dry-run
```

## Configuration

### 1. Email Recipients

Configure email recipients in Django admin:

1. Go to **Settings** → **Site Settings**
2. In the **Form Email Recipients** section, set **Birthday summary email recipients**
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

Add to system crontab to run on the 1st of each month at 9:00 AM:

```bash
# Edit crontab
crontab -e

# Add this line (adjust paths as needed)
0 9 1 * * /path/to/your/venv/bin/python /path/to/blowcomotion.org/manage.py send_monthly_birthday_summary
```

### Option 2: Django Settings Crontab (if using django-crontab)

```python
# In settings.py
CRONJOBS = [
    ('0 9 1 * *', 'blowcomotion.management.commands.send_monthly_birthday_summary'),
]
```

### Option 3: Systemd Timer (Modern Linux Systems)

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
OnCalendar=monthly
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
# Test with dry run
python manage.py send_monthly_birthday_summary --dry-run

# Test with specific month
python manage.py send_monthly_birthday_summary --month 9 --year 2025 --dry-run

# Test actual sending (be careful in production)
python manage.py send_monthly_birthday_summary --month 9 --year 2025
```

### Run Tests

```bash
python manage.py test blowcomotion.tests.test_birthday_command
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
   - Verify template file exists: `templates/emails/monthly_birthday_summary.html`
   - Check template syntax

### Debug Mode

Use dry-run mode to debug without sending emails:

```bash
python manage.py send_monthly_birthday_summary --dry-run
```

## Features

- **Automatic monthly scheduling**: Runs on 1st of each month by default
- **Professional HTML emails**: Responsive design with band branding
- **Member details**: Names, preferred names, instruments, ages
- **Flexible scheduling**: Can specify any month/year
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