"""
Close expired auction items: pick winners/backups and send notifications.

Cron (hourly backstop; page views also close lazily):
0 * * * * cd /path/to/project && /path/to/venv/bin/python manage.py close_auction_items
"""
from django.core.management.base import BaseCommand

from auction.services import close_expired_items


class Command(BaseCommand):
    help = "Pick winners for expired auction items and send notifications"

    def handle(self, *args, **options):
        closed = close_expired_items()
        self.stdout.write(f"Closed {closed} item(s)")
