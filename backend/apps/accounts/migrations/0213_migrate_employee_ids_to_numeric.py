"""
One-time, one-way migration of every existing employee's old prefix+digits
employee_id (EMP00004, CON00004, FL00005, ...) to the new 8-digit numeric
ID ranges, per the business's decision to fully migrate rather than keep
legacy IDs live. The old ID is preserved in legacy_employee_code so it stays
searchable and old paperwork/emails/bookmarks still resolve (see
apps/accounts/views/shared.py::_get_employee).

Deterministic, one-to-one allocation: within each employment type, existing
employees are renumbered in a stable order (date_joined, then id) starting
right after that type's configured range_start, so the result is
reproducible if this migration is ever re-run against a restored snapshot
with the same input data.
"""
from django.db import migrations


def migrate_ids(apps, schema_editor):
    User = apps.get_model('accounts', 'User')
    EmployeeCodeSeries = apps.get_model('accounts', 'EmployeeCodeSeries')

    series_by_type = {s.employment_type: s for s in EmployeeCodeSeries.objects.all()}

    for employment_type, series in series_by_type.items():
        employees = (
            User.objects
            .filter(employee_type=employment_type)
            .exclude(employee_id='')
            .order_by('date_joined', 'id')
        )
        next_number = series.range_start + 1
        for employee in employees:
            if next_number > series.range_end:
                # Range genuinely can't fit this type's existing headcount —
                # surfaced loudly rather than silently truncating data.
                raise RuntimeError(
                    f'Employee ID migration: {employment_type} has more existing employees than its '
                    f'configured range ({series.range_start}-{series.range_end}) can hold. Widen the '
                    f'range in DEFAULT_EMPLOYEE_ID_RANGES before re-running this migration.',
                )
            old_id = employee.employee_id
            new_id = str(next_number)
            employee.legacy_employee_code = old_id
            employee.employee_id = new_id
            employee.save(update_fields=['legacy_employee_code', 'employee_id'])
            next_number += 1

        series.next_sequence = next_number
        series.save(update_fields=['next_sequence'])

    # Draft hires mid-flight had a number reserved from the now-removed
    # prefix-based series — those reservations no longer match anything
    # real. Clear them so the Hire wizard requests a fresh, valid 8-digit
    # number from the new range when that draft is next touched, rather
    # than silently carrying a stale, unparseable value forward.
    HireAction = apps.get_model('accounts', 'HireAction')
    HireAction.objects.exclude(reserved_employee_id='').update(reserved_employee_id='')


def noop_reverse(apps, schema_editor):
    # Not reversible: the old prefix/padding series state (how far each
    # counter had advanced) is gone once 0212 removed those columns, so
    # there is no way to regenerate the original EMP00004-style IDs.
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0212_employee_id_ranges'),
    ]

    operations = [
        migrations.RunPython(migrate_ids, noop_reverse),
    ]
