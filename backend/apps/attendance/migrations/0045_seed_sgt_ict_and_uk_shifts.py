"""
Idempotent data migration: seeds two named WorkingHoursPolicy rows for the
SGT/ICT and UK shifts (07:30-16:30 and 12:00-21:00), so they exist in the
shift catalog ready for per-employee assignment via EmployeeShiftAssignment.

Safety:
  - Uses get_or_create(name=...) — if a policy with that exact name already
    exists (e.g. an administrator created one by hand before this migration
    ran), it is left completely untouched; nothing is overwritten.
  - Never touches AttendanceSettings/AttendanceWorkingHours (the existing
    global 09:00-18:00 singleton) at all — this migration only inserts rows
    into the separate WorkingHoursPolicy table.
  - is_default is never set True here, so no existing default policy
    (enforced only at the serializer layer, not the DB) can be disturbed.
  - Runs per-tenant-schema like every other migration in this app (TENANT_APPS
    + migrate_schemas) — safe to run against every existing tenant.
"""
from django.db import migrations


SHIFTS_TO_SEED = [
    {
        'name': 'SGT/ICT Shift',
        'policy_code': 'WH-SGT-ICT',
        'description': 'Singapore / Indochina Time shift: 07:30 AM - 04:30 PM.',
        'start_time': '07:30:00',
        'end_time': '16:30:00',
        'break_duration': 30,
        'grace_period': 15,
        'minimum_working_hours': '4.00',
        'maximum_working_hours': '9.00',
    },
    {
        'name': 'UK Shift',
        'policy_code': 'WH-UK',
        'description': 'UK shift: 12:00 PM - 09:00 PM.',
        'start_time': '12:00:00',
        'end_time': '21:00:00',
        'break_duration': 30,
        'grace_period': 15,
        'minimum_working_hours': '4.00',
        'maximum_working_hours': '9.00',
    },
]


def seed_shifts(apps, schema_editor):
    WorkingHoursPolicy = apps.get_model('attendance', 'WorkingHoursPolicy')
    for shift in SHIFTS_TO_SEED:
        name = shift['name']
        if WorkingHoursPolicy.objects.filter(name=name).exists():
            continue  # already present (admin-created or a previous run) — leave it untouched
        if WorkingHoursPolicy.objects.filter(policy_code=shift['policy_code']).exists():
            continue  # code collision guard — don't risk a duplicate-key error on a rerun/edge case
        WorkingHoursPolicy.objects.create(is_default=False, is_active=True, **shift)


def unseed_shifts(apps, schema_editor):
    """Reverse: only removes the exact rows this migration would have
    created (matched by policy_code), and only if nothing has ever been
    assigned to them (PROTECT on EmployeeShiftAssignment.policy blocks the
    delete otherwise, which is the correct, safe outcome)."""
    WorkingHoursPolicy = apps.get_model('attendance', 'WorkingHoursPolicy')
    codes = [s['policy_code'] for s in SHIFTS_TO_SEED]
    WorkingHoursPolicy.objects.filter(policy_code__in=codes).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('attendance', '0044_employee_shift_assignment'),
    ]

    operations = [
        migrations.RunPython(seed_shifts, unseed_shifts),
    ]
