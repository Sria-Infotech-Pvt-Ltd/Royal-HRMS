from django.db import migrations


def backfill_is_department_level(apps, schema_editor):
    """Every OrgUnit already explicitly linked to a Department (via the
    Phase 3 bridge, §17) represents a real department — carry that forward
    onto the new native flag before the FK itself is removed. Also catches
    units that were never explicitly linked but share a Department's exact
    name (case-insensitive) — not every real department got the manual
    link set up during Phase 3, and this is the last chance to carry that
    association forward before the Department table itself goes away."""
    OrgUnit = apps.get_model('accounts', 'OrgUnit')
    Department = apps.get_model('accounts', 'Department')

    OrgUnit.objects.filter(department__isnull=False).update(is_department_level=True)

    dept_names = set(Department.objects.values_list('name', flat=True))
    for unit in OrgUnit.objects.filter(is_department_level=False):
        if any(unit.name.lower() == name.lower() for name in dept_names):
            unit.is_department_level = True
            unit.save(update_fields=['is_department_level'])


def noop_reverse(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0112_orgunit_is_department_level"),
    ]

    operations = [
        migrations.RunPython(backfill_is_department_level, noop_reverse),
    ]
