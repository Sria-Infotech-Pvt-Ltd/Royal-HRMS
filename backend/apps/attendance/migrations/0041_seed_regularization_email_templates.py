"""
Seed the email templates used by the attendance regularization
(AttendanceCorrection) lifecycle. Wired up in apps/notifications/signals.py
alongside the existing in-app Notification records — regularization
requests previously only ever notified in-app, never by email.
"""
from django.db import migrations

_TEMPLATES = [
    {
        'name':         'regularization_submitted',
        'display_name': 'Attendance Regularization Submitted — Employee Confirmation',
        'description':  'Sent to the employee confirming their regularization request was submitted.',
        'template_type': 'hrms',
        'subject':      'Your attendance regularization request for {date} has been submitted',
        'body': (
            '<p>Dear {employee_name},</p>'
            '<p>Your attendance regularization request for <strong>{date}</strong> has been '
            'submitted successfully and is now awaiting approval.</p>'
            '<p style="color:#888;font-size:13px;">Reason: {reason}</p>'
            '<p>You will be notified as soon as it is actioned.</p>'
            '<p>Warm regards,<br/><strong>HR Team — {company_name}</strong></p>'
        ),
        'is_active':  True,
        'is_builtin': True,
        'available_variables': ['employee_name', 'date', 'reason', 'company_name'],
    },
    {
        'name':         'regularization_pending_approval',
        'display_name': 'Attendance Regularization — Awaiting Your Approval',
        'description':  'Sent to the employee\'s assigned HR when a regularization request needs their action.',
        'template_type': 'hrms',
        'subject':      'Attendance regularization awaiting your approval — {employee_name}',
        'body': (
            '<p>Dear {approver_name},</p>'
            '<p><strong>{employee_name}</strong> has submitted an attendance regularization '
            'request for <strong>{date}</strong> that requires your approval.</p>'
            '<p style="color:#888;font-size:13px;">Reason: {reason}</p>'
            '<p>Please review it at your earliest convenience.</p>'
            '<p>Warm regards,<br/><strong>HR Team — {company_name}</strong></p>'
        ),
        'is_active':  True,
        'is_builtin': True,
        'available_variables': ['approver_name', 'employee_name', 'date', 'reason', 'company_name'],
    },
    {
        'name':         'regularization_approved',
        'display_name': 'Attendance Regularization Approved',
        'description':  'Sent to the employee when their regularization request is approved.',
        'template_type': 'hrms',
        'subject':      'Your attendance regularization for {date} has been approved',
        'body': (
            '<p>Dear {employee_name},</p>'
            '<p>Your attendance regularization request for <strong>{date}</strong> has been '
            '<strong style="color:#1b8a6b;">approved</strong>.</p>'
            '<p>Warm regards,<br/><strong>HR Team — {company_name}</strong></p>'
        ),
        'is_active':  True,
        'is_builtin': True,
        'available_variables': ['employee_name', 'date', 'company_name'],
    },
    {
        'name':         'regularization_rejected',
        'display_name': 'Attendance Regularization Rejected',
        'description':  'Sent to the employee when their regularization request is rejected.',
        'template_type': 'hrms',
        'subject':      'Your attendance regularization for {date} has been rejected',
        'body': (
            '<p>Dear {employee_name},</p>'
            '<p>Your attendance regularization request for <strong>{date}</strong> has been '
            '<strong style="color:#b91c1c;">rejected</strong>.</p>'
            '<p>If you have questions about this decision, please reach out to your HR representative.</p>'
            '<p>Warm regards,<br/><strong>HR Team — {company_name}</strong></p>'
        ),
        'is_active':  True,
        'is_builtin': True,
        'available_variables': ['employee_name', 'date', 'company_name'],
    },
]


def seed_templates(apps, schema_editor):
    EmailTemplate = apps.get_model('accounts', 'EmailTemplate')
    for tpl in _TEMPLATES:
        EmailTemplate.objects.get_or_create(
            name=tpl['name'],
            defaults={k: v for k, v in tpl.items() if k != 'name'},
        )


def remove_templates(apps, schema_editor):
    EmailTemplate = apps.get_model('accounts', 'EmailTemplate')
    EmailTemplate.objects.filter(name__in=[t['name'] for t in _TEMPLATES]).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('attendance', '0040_attendancerecord_work_mode'),
        ('accounts',   '0096_ensure_assessments_permissions_defaults'),
    ]

    operations = [
        migrations.RunPython(seed_templates, remove_templates),
    ]
