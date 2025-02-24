# Generated by Django 5.1.6 on 2025-02-24 06:10

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('blowcomotion', '0016_remove_section_instructors_remove_section_members_and_more'),
    ]

    operations = [
        migrations.AlterModelOptions(
            name='sectioninstructor',
            options={'ordering': ['sort_order']},
        ),
        migrations.AlterModelOptions(
            name='sectionmember',
            options={'ordering': ['sort_order']},
        ),
        migrations.AddField(
            model_name='sectioninstructor',
            name='sort_order',
            field=models.IntegerField(blank=True, editable=False, null=True),
        ),
        migrations.AddField(
            model_name='sectionmember',
            name='sort_order',
            field=models.IntegerField(blank=True, editable=False, null=True),
        ),
    ]
