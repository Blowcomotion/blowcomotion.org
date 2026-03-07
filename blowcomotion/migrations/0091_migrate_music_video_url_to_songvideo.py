# Generated migration to safely migrate music_video_url to SongVideo model

from django.db import migrations


def migrate_video_urls(apps, schema_editor):
    """
    Migrate existing music_video_url values to SongVideo entries.
    This preserves data from the old field before it's removed.
    """
    Song = apps.get_model('blowcomotion', 'Song')
    SongVideo = apps.get_model('blowcomotion', 'SongVideo')
    
    migrated_count = 0
    for song in Song.objects.filter(music_video_url__isnull=False).exclude(music_video_url=''):
        # Create a SongVideo entry for each existing music_video_url
        # Only create if one doesn't already exist
        if not SongVideo.objects.filter(song=song).exists():
            SongVideo.objects.create(
                song=song,
                url=song.music_video_url,
                title=None,  # Original field didn't have a title, so leave blank
                sort_order=0
            )
            migrated_count += 1
    
    if migrated_count > 0:
        print(f"\n✓ Successfully migrated {migrated_count} music video URLs to SongVideo model")
    else:
        print("\n✓ No music video URLs to migrate (all songs already updated or field was empty)")


def reverse_migration(apps, schema_editor):
    """
    Reverse the migration by deleting SongVideo entries that were created from music_video_url.
    Note: This only deletes SongVideo entries with no title (those created from the old field).
    SongVideo entries with titles (manually added) are preserved.
    """
    SongVideo = apps.get_model('blowcomotion', 'SongVideo')
    
    # Delete SongVideo entries that have no title (these were auto-migrated)
    deleted_count, _ = SongVideo.objects.filter(title__isnull=True).delete()
    
    if deleted_count > 0:
        print(f"\n⟲ Rolled back {deleted_count} auto-migrated SongVideo entries")


class Migration(migrations.Migration):

    dependencies = [
        ('blowcomotion', '0090_alter_blankcanvaspage_body_and_more'),
    ]

    operations = [
        migrations.RunPython(migrate_video_urls, reverse_migration),
        migrations.RemoveField(
            model_name='song',
            name='music_video_url',
        ),
    ]
