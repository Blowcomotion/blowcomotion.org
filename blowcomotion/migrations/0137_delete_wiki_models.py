# Kept separate from 0136 so the data conversion is recorded before any table is
# dropped (MySQL can't roll back DDL).
from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('blowcomotion', '0136_wiki_to_blank_canvas'),
    ]

    operations = [
        migrations.DeleteModel(
            name='WikiAuthor',
        ),
        migrations.DeleteModel(
            name='WikiIndexPage',
        ),
        migrations.DeleteModel(
            name='WikiPage',
        ),
    ]
