# Generated by Django 5.1.6 on 2025-02-24 06:10

import django.db.models.deletion
import modelcluster.fields
from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('blowcomotion', '0015_sectioninstructor_sectionmember'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='section',
            name='instructors',
        ),
        migrations.RemoveField(
            model_name='section',
            name='members',
        ),
        migrations.AlterField(
            model_name='sectioninstructor',
            name='section',
            field=modelcluster.fields.ParentalKey(on_delete=django.db.models.deletion.CASCADE, related_name='instructors', to='blowcomotion.section'),
        ),
        migrations.AlterField(
            model_name='sectionmember',
            name='section',
            field=modelcluster.fields.ParentalKey(on_delete=django.db.models.deletion.CASCADE, related_name='members', to='blowcomotion.section'),
        ),
    ]
