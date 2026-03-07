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
    Reverse the migration by restoring music_video_url from SongVideo entries,
    then deleting the SongVideo entries that were created from music_video_url.

    Note: This only affects SongVideo entries with no title (those created from
    the old field). SongVideo entries with titles (manually added) are preserved.
    """
    Song = apps.get_model('blowcomotion', 'Song')
    SongVideo = apps.get_model('blowcomotion', 'SongVideo')

    # First, restore the music_video_url field from auto-migrated SongVideo entries.
    restored_count = 0
    auto_migrated_videos = SongVideo.objects.filter(title__isnull=True).select_related("song")

    for song_video in auto_migrated_videos:
        song = song_video.song
        # Avoid overwriting any non-empty value that may have been set after migration.
        if getattr(song, "music_video_url", None) in (None, "") and song_video.url:
            song.music_video_url = song_video.url
            song.save(update_fields=["music_video_url"])
            restored_count += 1

    # Now delete SongVideo entries that have no title (these were auto-migrated).
    deleted_count, _ = auto_migrated_videos.delete()

    if restored_count > 0 or deleted_count > 0:
        print(
            f"\n⟲ Rolled back migration: restored URLs for {restored_count} songs "
            f"and deleted {deleted_count} auto-migrated SongVideo entries"
        )
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
