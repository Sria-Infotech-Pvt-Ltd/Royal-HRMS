"""
Phase 1 Task G — copies the EXISTING accounts.EmployeeCodeSettings
(singleton fallback) and accounts.EmployeeCodeSeries (one row per
employment type) rows into the new platform_core.NumberSeries table.

Purely additive: EmployeeCodeSettings/EmployeeCodeSeries are untouched,
and nothing in the real employee-code generation path reads from
NumberSeries yet (that cutover is behind feature flag `numbering.v2`,
deferred past this phase — see PHASE1_REPORT.md). This migration exists
so the NumberSeries rows are ready and already in parity with the real
counters whenever that cutover does happen.

Reversible: the reverse migration simply deletes the NumberSeries rows
this migration created (tracked by the `platform_core` seed source, not
by re-deriving them).
"""
from django.db import migrations


def seed_forward(apps, schema_editor):
    NumberSeries = apps.get_model('platform_core', 'NumberSeries')
    EmployeeCodeSettings = apps.get_model('accounts', 'EmployeeCodeSettings')
    EmployeeCodeSeries = apps.get_model('accounts', 'EmployeeCodeSeries')

    settings_row = EmployeeCodeSettings.objects.first()
    if settings_row is not None:
        NumberSeries.objects.get_or_create(
            code='employee_default',
            defaults={
                'entity': 'employee',
                'pattern': '{PREFIX}{SEQ:%d}' % settings_row.padding,
                'prefix': settings_row.prefix,
                'padding': settings_row.padding,
                'next_value': settings_row.next_sequence,
                'reset_period': 'never',
                'scope_key': '',
                'is_active': True,
            },
        )

    for series in EmployeeCodeSeries.objects.all():
        NumberSeries.objects.get_or_create(
            code=f'employee_{series.employment_type}',
            defaults={
                'entity': 'employee',
                'pattern': '{PREFIX}{SEQ:%d}' % series.padding,
                'prefix': series.prefix,
                'padding': series.padding,
                'next_value': series.next_sequence,
                'reset_period': 'never',
                'scope_key': series.employment_type,
                'is_active': True,
            },
        )


def seed_reverse(apps, schema_editor):
    NumberSeries = apps.get_model('platform_core', 'NumberSeries')
    NumberSeries.objects.filter(entity='employee').delete()


class Migration(migrations.Migration):

    dependencies = [
        ('platform_core', '0001_initial'),
        ('accounts', '0178_add_external_api_key'),
    ]

    operations = [
        migrations.RunPython(seed_forward, seed_reverse),
    ]
