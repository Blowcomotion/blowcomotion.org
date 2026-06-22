"""
Invite all active members without accounts to set their password.

Usage:
    python manage.py invite_members [--dry-run] [--member-id MEMBER_ID]
"""
import logging

from django.core.management.base import BaseCommand
from django.http import HttpRequest

from blowcomotion.member_auth import create_member_user, send_set_password_email
from blowcomotion.models import Member

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Send set-password invitations to active members without accounts"

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Print who would be invited without sending emails or creating users",
        )
        parser.add_argument(
            "--member-id",
            type=int,
            default=None,
            help="Process a single member by ID (for testing)",
        )

    def handle(self, *args, **options):
        dry_run = options["dry_run"]
        member_id = options["member_id"]

        qs = Member.objects.filter(is_active=True, user__isnull=True)
        if member_id:
            qs = qs.filter(pk=member_id)

        # Build a minimal request so build_absolute_uri works
        request = HttpRequest()
        request.META["SERVER_NAME"] = "www.blowcomotion.org"
        request.META["SERVER_PORT"] = "443"
        request.META["wsgi.url_scheme"] = "https"

        invited = skipped = errored = 0

        for member in qs:
            if not member.email:
                self.stdout.write(f"  SKIP (no email): {member}")
                skipped += 1
                continue

            if dry_run:
                self.stdout.write(f"  DRY RUN — would invite: {member} <{member.email}>")
                invited += 1
                continue

            try:
                create_member_user(member)
                send_set_password_email(member, request)
                self.stdout.write(f"  Invited: {member} <{member.email}>")
                invited += 1
            except Exception as exc:
                self.stderr.write(f"  ERROR for {member} <{member.email}>: {exc}")
                logger.error(f"invite_members: error inviting member {member.pk}: {exc}")
                errored += 1

        prefix = "Would invite" if dry_run else "Invited"
        self.stdout.write(
            f"\nDone. {prefix}: {invited} | Skipped: {skipped} | Errored: {errored}"
        )
