import uuid

from django.db import migrations


def create_default_weekly_off_policy(apps, schema_editor):
    """
    UAT-042: no weekly-off pattern existed anywhere, so pattern_id was null
    for every employee — the "assign on hire" code path already exists
    (apps.attendance.services_hr.assign_weekly_off) but only fires when a
    WeeklyDayPolicy with is_default=True exists, and none ever did outside
    demo/seed data. This creates that default (Sat+Sun off) and backfills
    every employee who currently has no assignment at all.
    """
    WeeklyDayPolicy = apps.get_model('attendance', 'WeeklyDayPolicy')
    EmployeeWeeklyOffAssignment = apps.get_model('attendance', 'EmployeeWeeklyOffAssignment')
    User = apps.get_model('accounts', 'User')

    policy, _ = WeeklyDayPolicy.objects.get_or_create(
        is_default=True,
        defaults={
            'id': uuid.uuid4(),
            'name': 'Standard (Sat-Sun Off)',
            'policy_code': 'WD-DEFAULT',
            'description': 'Default weekly-off pattern — Monday to Friday working, Saturday and Sunday off.',
            'monday': 'working', 'tuesday': 'working', 'wednesday': 'working',
            'thursday': 'working', 'friday': 'working',
            'saturday': 'off', 'sunday': 'off',
            'is_active': True,
        },
    )

    assigned_ids = set(
        EmployeeWeeklyOffAssignment.objects
        .filter(effective_to__isnull=True)
        .values_list('employee_id', flat=True)
    )
    unassigned = User.objects.filter(is_active=True).exclude(id__in=assigned_ids)
    EmployeeWeeklyOffAssignment.objects.bulk_create([
        EmployeeWeeklyOffAssignment(
            id=uuid.uuid4(),
            employee_id=user.id,
            policy=policy,
            effective_from=user.date_of_joining or user.date_joined.date(),
        )
        for user in unassigned
    ])


def noop_reverse(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('attendance', '0044_face_id_registration_mode_and_fallback'),
    ]

    operations = [
        migrations.RunPython(create_default_weekly_off_policy, noop_reverse),
    ]
