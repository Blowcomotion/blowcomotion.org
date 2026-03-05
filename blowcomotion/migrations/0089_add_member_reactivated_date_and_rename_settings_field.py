# Generated migration for adding reactivated_date field to Member and renaming SiteSettings field

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('blowcomotion', '0088_member_gigomatic_id'),
    ]

    operations = [
        # Add reactivated_date field to Member
        migrations.AddField(
            model_name='member',
            name='reactivated_date',
            field=models.DateField(
                blank=True,
                null=True,
                help_text='Date when the member was reactivated (is_active changed to True).'
            ),
        ),
        # Rename attendance_cleanup_notification_recipients to attendance_report_notification_recipients
        migrations.RenameField(
            model_name='sitesettings',
            old_name='attendance_cleanup_notification_recipients',
            new_name='attendance_report_notification_recipients',
        ),
    ]
