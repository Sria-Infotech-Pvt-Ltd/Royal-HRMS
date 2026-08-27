# Backfills a real Placement row for every Position that already has a
# holder assigned (from before this feature existed), before 0107 removes
# Position.holder entirely.
#
# effective_from backfill source, per this change's own design notes: the
# employee's real date_of_joining where known, falling back to this
# migration's run date where not — a wrong start date corrupts tenure/
# payroll proration, so "unknown" must be an honest, visible fallback, not
# a silent guess.

from django.db import migrations
from django.utils import timezone


def backfill_forward(apps, schema_editor):
    Position = apps.get_model('accounts', 'Position')
    Placement = apps.get_model('accounts', 'Placement')
    today = timezone.now().date()

    for position in Position.objects.exclude(holder=None).select_related('holder'):
        Placement.objects.create(
            position=position,
            employee=position.holder,
            effective_from=position.holder.date_of_joining or today,
            effective_to=None,
            note='Backfilled from Position.holder during the Placement migration.',
        )


def backfill_reverse(apps, schema_editor):
    Placement = apps.get_model('accounts', 'Placement')
    Placement.objects.filter(note='Backfilled from Position.holder during the Placement migration.').delete()


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0105_placement_and_active_fields'),
    ]

    operations = [
        migrations.RunPython(backfill_forward, backfill_reverse),
    ]
