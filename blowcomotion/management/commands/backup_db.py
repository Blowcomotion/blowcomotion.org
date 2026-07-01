from datetime import datetime
from pathlib import Path

from wagtail.models import Page, PageLogEntry

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.core.management.base import BaseCommand

BACKUP_DIR = Path.home() / 'backups'
KEEP = 7  # ponytail: fixed retention; add --keep arg when you need it


class Command(BaseCommand):
    help = 'Dump database to a timestamped JSON file and rotate old backups'

    def add_arguments(self, parser):
        parser.add_argument(
            '--output-dir',
            default=str(BACKUP_DIR),
            help=f'Directory to write backups (default: {BACKUP_DIR})',
        )

    def handle(self, *args, **options):
        output_dir = Path(options['output_dir'])
        output_dir.mkdir(parents=True, exist_ok=True)

        timestamp = datetime.now().strftime('%Y-%m-%d_%H%M%S')
        backup_path = output_dir / f'backup_{timestamp}.json'

        # PageLogEntry.page and .user are both DO_NOTHING / no db constraint — clean up
        # orphans before dump so --natural-foreign doesn't crash on missing natural keys
        page_ids = set(Page.objects.values_list('id', flat=True))
        deleted, _ = PageLogEntry.objects.exclude(page_id__in=page_ids).delete()
        if deleted:
            self.stdout.write(f'Deleted {deleted} PageLogEntry records for missing pages')

        user_ids = set(get_user_model().objects.values_list('id', flat=True))
        nulled = PageLogEntry.objects.exclude(user_id__isnull=True).exclude(user_id__in=user_ids).update(user=None)
        if nulled:
            self.stdout.write(f'Nulled {nulled} orphaned PageLogEntry.user references')

        self.stdout.write(f'Writing backup to {backup_path}')

        with open(backup_path, 'w', encoding='utf-8') as f:
            call_command(
                'dumpdata',
                '--natural-foreign',
                '--indent', '2',
                '--exclude', 'contenttypes',
                '--exclude', 'auth.permission',
                '--exclude', 'sessions',
                '--exclude', 'wagtailsearch',
                '--exclude', 'wagtailcore.referenceindex',
                '--exclude', 'wagtailcore.taskstate',
                '--exclude', 'wagtailcore.workflowstate',
                '--exclude', 'wagtailcore.comment',
                # pagesubscription has a direct Page FK; exclude to avoid orphan crashes
                '--exclude', 'wagtailcore.pagesubscription',
                '--exclude', 'wagtailcore.groupcollectionpermission',
                '--exclude', 'wagtailcore.grouppagepermission',
                '--exclude', 'wagtailadmin.editingsession',
                '--exclude', 'wagtailadmin.formstate',
                '--exclude', 'wagtailusers.userprofile',
                '--exclude', 'axes.accesslog',
                stdout=f,
                verbosity=0,
            )

        size_kb = backup_path.stat().st_size // 1024
        self.stdout.write(self.style.SUCCESS(f'Backup complete: {backup_path} ({size_kb} KB)'))

        # Rotate: delete oldest backups beyond KEEP
        backups = sorted(output_dir.glob('backup_*.json'))
        for old in backups[:-KEEP]:
            old.unlink()
            self.stdout.write(f'Deleted old backup: {old.name}')
