# Generated by Django 5.1.6 on 2025-02-24 23:16

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('blowcomotion', '0026_alter_chart_part'),
    ]

    operations = [
        migrations.RenameModel(
            old_name='EventSetlist',
            new_name='EventSetlistSong',
        ),
        migrations.AddField(
            model_name='event',
            name='time',
            field=models.TimeField(blank=True, null=True),
        ),
        migrations.AlterField(
            model_name='event',
            name='date',
            field=models.DateField(blank=True, null=True),
        ),
    ]
