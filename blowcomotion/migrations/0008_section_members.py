# Generated by Django 5.1.6 on 2025-02-24 04:47

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('blowcomotion', '0007_instrument_member_section_instrument_section'),
    ]

    operations = [
        migrations.AddField(
            model_name='section',
            name='members',
            field=models.ManyToManyField(blank=True, related_name='+', to='blowcomotion.member'),
        ),
    ]
