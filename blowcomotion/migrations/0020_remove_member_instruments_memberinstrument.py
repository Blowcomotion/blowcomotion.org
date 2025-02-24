# Generated by Django 5.1.6 on 2025-02-24 06:30

import django.db.models.deletion
import modelcluster.fields
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('blowcomotion', '0019_member_instruments_delete_memberinstrument'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='member',
            name='instruments',
        ),
        migrations.CreateModel(
            name='MemberInstrument',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('sort_order', models.IntegerField(blank=True, editable=False, null=True)),
                ('instrument', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='blowcomotion.instrument')),
                ('member', modelcluster.fields.ParentalKey(on_delete=django.db.models.deletion.CASCADE, related_name='instruments', to='blowcomotion.member')),
            ],
            options={
                'ordering': ['sort_order'],
                'abstract': False,
            },
        ),
    ]
