# Generated by Django 5.1.6 on 2025-02-24 23:03

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('blowcomotion', '0024_remove_song_event_eventsetlist'),
    ]

    operations = [
        migrations.AddField(
            model_name='chart',
            name='part',
            field=models.CharField(blank=True, max_length=255, null=True),
        ),
    ]
