"""
Seed one EmployeeCodeSeries row per employment type, initialized from the
existing EmployeeCodeSettings singleton's current prefix/padding/next_sequence
— preserves continuity so the new per-type series never collides with an
employee_id already issued through the old global counter.
"""
from django.db import migrations

EMPLOYMENT_TYPES = (
    'Permanent', 'Contract', 'Freelancer', 'Consultant',
    'Part-Time', 'Temporary', 'Intern',
)


def seed_forward(apps, schema_editor):
    EmployeeCodeSettings = apps.get_model('accounts', 'EmployeeCodeSettings')
    EmployeeCodeSeries = apps.get_model('accounts', 'EmployeeCodeSeries')

    base, _ = EmployeeCodeSettings.objects.get_or_create(
        pk=1, defaults={'prefix': 'EMP', 'padding': 5, 'next_sequence': 1},
    )
    for employment_type in EMPLOYMENT_TYPES:
        EmployeeCodeSeries.objects.get_or_create(
            employment_type=employment_type,
            defaults={
                'prefix': base.prefix,
                'padding': base.padding,
                'next_sequence': base.next_sequence,
            },
        )


def seed_reverse(apps, schema_editor):
    EmployeeCodeSeries = apps.get_model('accounts', 'EmployeeCodeSeries')
    EmployeeCodeSeries.objects.filter(employment_type__in=EMPLOYMENT_TYPES).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0154_employeecodeseries_user_dotted_line_manager_and_more'),
    ]

    operations = [
        migrations.RunPython(seed_forward, seed_reverse),
    ]
