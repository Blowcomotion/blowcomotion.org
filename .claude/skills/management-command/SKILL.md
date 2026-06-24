---
name: management-command
description: Scaffold a new Django management command for blowcomotion with a matching test stub
disable-model-invocation: true
---

Scaffold a new management command. The user will provide the command name as an argument (e.g. `/management-command export_venues`).

## File to create: `blowcomotion/management/commands/<name>.py`

Follow the exact pattern used in the existing commands:

```python
import logging

from django.core.management.base import BaseCommand

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = '<one-line description of what the command does>'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Preview without making changes',
        )

    def handle(self, *args, **options):
        verbosity = options.get('verbosity', 1)
        dry_run = options.get('dry_run', False)

        if dry_run:
            self.stdout.write(self.style.WARNING('DRY RUN - No changes will be saved'))

        # TODO: implement command logic

        self.stdout.write(self.style.SUCCESS('Done'))
```

- Use `self.stdout.write(self.style.SUCCESS(...))` for success
- Use `self.stdout.write(self.style.WARNING(...))` for warnings
- Use `self.stdout.write(self.style.ERROR(...))` for errors
- Log with `logger.info(...)` / `logger.error(...)` for background/cron runs
- Check `verbosity >= 2` before printing per-record detail
- Always include `--dry-run` unless the command is purely read-only

## File to create: `blowcomotion/tests/test_<name>_command.py`

```python
from io import StringIO

from django.core.management import call_command
from django.test import TestCase


class <Name>CommandTests(TestCase):

    def test_basic_run(self):
        out = StringIO()
        call_command('<name>', stdout=out)
        self.assertIn('done', out.getvalue().lower())

    def test_dry_run(self):
        out = StringIO()
        call_command('<name>', '--dry-run', stdout=out)
        output = out.getvalue()
        self.assertIn('dry run', output.lower())
```

Use `unittest.mock.patch` to mock any external API calls (see `test_sync_gigs_command.py` for the pattern).

## After creating the files

Run: `python manage.py help <name>` to confirm the command registers correctly.
