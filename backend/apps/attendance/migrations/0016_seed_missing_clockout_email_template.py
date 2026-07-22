"""
Seed the attendance_missing_clockout email template.
services_unpunch.py's _deliver() sends this reminder to any employee who
forgot to clock out — it referenced the name 'attendance/missing_clockout'
(a slash, breaking the snake_case convention every other template uses) and
it was never seeded, so every delivery attempt raised LookupError (caught
and logged as a warning only — a silent failure).
"""
from django.db import migrations

TEMPLATE = {
    'name':         'attendance_missing_clockout',
    'display_name': 'Missing Clock-Out Reminder',
    'description':  'Sent to an employee who forgot to clock out at the end of their shift.',
    'template_type': 'hrms',
    'subject':      '{subject}',
    'body': (
        '<p>Dear {employee_name},</p>'
        '<p>{message}</p>'
        '<p style="color:#888;font-size:13px;">Date: {date_display}</p>'
        '<p>Warm regards,<br/><strong>HR Team — {company_name}</strong></p>'
    ),
    'is_active':  True,
    'is_builtin': True,
    'available_variables': [
        'employee_name', 'date_display', 'subject', 'message', 'company_name',
    ],
}


def seed_template(apps, schema_editor):
    EmailTemplate = apps.get_model('accounts', 'EmailTemplate')
    EmailTemplate.objects.get_or_create(
        name=TEMPLATE['name'],
        defaults={k: v for k, v in TEMPLATE.items() if k != 'name'},
    )


def remove_template(apps, schema_editor):
    EmailTemplate = apps.get_model('accounts', 'EmailTemplate')
    EmailTemplate.objects.filter(name=TEMPLATE['name']).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('attendance', '0015_audit_log_and_invalid_punch'),
        ('accounts',   '0042_clean_employee_role_permissions'),
    ]

    operations = [
        migrations.RunPython(seed_template, remove_template),
    ]
