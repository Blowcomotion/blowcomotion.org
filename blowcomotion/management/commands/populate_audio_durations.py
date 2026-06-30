from mutagen.mp3 import MP3
from wagtailmedia.models import Media

from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Populate duration field on audio Media objects from file metadata"

    def handle(self, *args, **options):
        qs = Media.objects.filter(type="audio", duration=0)
        updated = 0
        failed = 0
        for media in qs:
            try:
                audio = MP3(media.file.path)
                media.duration = audio.info.length
                media.save(update_fields=["duration"])
                updated += 1
            except Exception as e:
                self.stderr.write(f"  {media.title}: {e}")
                failed += 1
        self.stdout.write(f"Updated {updated}, failed {failed}")
