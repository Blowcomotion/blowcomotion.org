from django.db import migrations


def backfill_conductor_charts(apps, schema_editor):
    """
    Convert legacy charts that used the "Conductor" instrument into proper conductor charts.
    After this migration, the Conductor Instrument and Section records can be safely deleted
    from the admin (they are no longer needed by the chart system).
    """
    Chart = apps.get_model("blowcomotion", "Chart")
    updated = (
        Chart.objects.filter(instrument__name__iexact="Conductor")
        .update(is_conductor_chart=True, instrument=None)
    )
    if updated:
        print(f"\n  Converted {updated} Conductor-instrument chart(s) to conductor charts.")


class Migration(migrations.Migration):

    dependencies = [
        ("blowcomotion", "0126_chart_conductor_flag"),
    ]

    operations = [
        migrations.RunPython(backfill_conductor_charts, migrations.RunPython.noop),
    ]
