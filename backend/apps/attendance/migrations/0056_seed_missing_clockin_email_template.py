"""
Seed the attendance_missing_clockin email template: the morning reminder sent (services_clockin_reminder.py) to an employee who is
expected at work today and has not clocked in yet. get_or_create, so a template an admin has edited is never overwritten.
"""
from django.db import migrations

TEMPLATE = {
    'name':         'attendance_missing_clockin',
    'display_name': 'Missing Clock-In Reminder',
    'description':  'Sent to an employee who has not clocked in once the clock-in reminder time has passed.',
    'template_type': 'hrms',
    'subject':      'Reminder: You have not Clocked In yet today',
    'body': (
        '<p>Dear {employee_name},</p>'
        '<p>You have not clocked in yet today. Please clock in now. If you are not working today, '
        'or you already worked and forgot to clock in, raise a leave or an attendance correction request.</p>'
        '<p style="color:#888;font-size:13px;">If Clock In asks for Face ID, register your Face ID from your Profile first. '
        'Date: {date_display}</p>'
        '<p>Warm regards,<br/><strong>HR Team — {company_name}</strong></p>'
    ),
    'is_active':  True,
    'is_builtin': True,
    'available_variables': ['employee_name', 'date_display', 'company_name'],
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
        ('attendance', '0055_clock_in_reminder'),
        ('accounts',   '0042_clean_employee_role_permissions'),
    ]
    operations = [migrations.RunPython(seed_template, remove_template)]
