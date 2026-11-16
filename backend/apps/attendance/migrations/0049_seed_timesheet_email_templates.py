"""
Seed the three emails the weekly timesheet sends: submitted (to the approver), sent back and approved (to the employee).
`get_or_create`, so a template an admin has already edited is never overwritten. The reminders are in-app only.
"""
from django.db import migrations

_TEMPLATES = [
    {
        'name': 'timesheet_submitted',
        'display_name': 'Timesheet Submitted for Approval',
        'description': "Sent to the approver when an employee submits their weekly timesheet.",
        'template_type': 'hrms',
        'subject': '{employee_name} submitted a timesheet for {week}',
        'body': (
            '<p>Dear {approver_name},</p>'
            '<p><strong>{employee_name}</strong> has submitted their timesheet for <strong>{week}</strong> for your approval.</p>'
            '<p>Total hours: {total_hours} (billable: {billable_hours}).{late_note}</p>'
            '<p>Open <strong>Approvals &rarr; Timesheets</strong> to review it.</p>'
            '<p>Warm regards,<br/><strong>HR Team — {company_name}</strong></p>'
        ),
        'is_active': True,
        'is_builtin': True,
        'available_variables': ['approver_name', 'employee_name', 'week', 'total_hours', 'billable_hours', 'late_note', 'company_name'],
    },
    {
        'name': 'timesheet_returned',
        'display_name': 'Timesheet Sent Back',
        'description': 'Sent to the employee when their timesheet is sent back for changes (or reopened by HR).',
        'template_type': 'hrms',
        'subject': 'Your timesheet for {week} needs changes',
        'body': (
            '<p>Dear {employee_name},</p>'
            '<p>Your timesheet for <strong>{week}</strong> was <strong style="color:#b91c1c;">sent back</strong> by {decided_by}.</p>'
            '<p style="color:#888;font-size:13px;">Reason: {reason}</p>'
            '<p>Please correct it and submit it again from <strong>Attendance &rarr; Weekly timesheet</strong>.</p>'
            '<p>Warm regards,<br/><strong>HR Team — {company_name}</strong></p>'
        ),
        'is_active': True,
        'is_builtin': True,
        'available_variables': ['employee_name', 'week', 'decided_by', 'reason', 'company_name'],
    },
    {
        'name': 'timesheet_approved',
        'display_name': 'Timesheet Approved',
        'description': 'Sent to the employee when their weekly timesheet is approved.',
        'template_type': 'hrms',
        'subject': 'Your timesheet for {week} was approved',
        'body': (
            '<p>Dear {employee_name},</p>'
            '<p>Your timesheet for <strong>{week}</strong> has been <strong style="color:#1b8a6b;">approved</strong> by {decided_by}. '
            'It is now locked.</p>'
            '<p>Total hours: {total_hours} (billable: {billable_hours}).</p>'
            '<p>Warm regards,<br/><strong>HR Team — {company_name}</strong></p>'
        ),
        'is_active': True,
        'is_builtin': True,
        'available_variables': ['employee_name', 'week', 'decided_by', 'total_hours', 'billable_hours', 'company_name'],
    },
]


def seed_templates(apps, schema_editor):
    EmailTemplate = apps.get_model('accounts', 'EmailTemplate')
    for tpl in _TEMPLATES:
        EmailTemplate.objects.get_or_create(name=tpl['name'], defaults={k: v for k, v in tpl.items() if k != 'name'})


def remove_templates(apps, schema_editor):
    EmailTemplate = apps.get_model('accounts', 'EmailTemplate')
    EmailTemplate.objects.filter(name__in=[t['name'] for t in _TEMPLATES]).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('attendance', '0048_timesheets'),
        ('accounts', '0224_seed_timesheet_approval_rule'),
    ]

    operations = [
        migrations.RunPython(seed_templates, remove_templates),
    ]
