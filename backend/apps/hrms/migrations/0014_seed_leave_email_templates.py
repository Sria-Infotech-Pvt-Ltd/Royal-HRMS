"""
Seed the six email templates used by the leave request lifecycle.
Wired up in apps/notifications/signals.py alongside the existing in-app
Notification records — leave requests previously only ever notified
in-app, never by email.
"""
from django.db import migrations

_TEMPLATES = [
    {
        'name':         'leave_request_submitted',
        'display_name': 'Leave Request Submitted — Employee Confirmation',
        'description':  'Sent to the employee confirming their leave request was submitted.',
        'template_type': 'hrms',
        'subject':      'Your {leave_type} request has been submitted',
        'body': (
            '<p>Dear {employee_name},</p>'
            '<p>Your <strong>{leave_type}</strong> request has been submitted successfully '
            'and is now awaiting approval.</p>'
            '<table style="border-collapse:collapse;margin:16px 0;">'
            '  <tr>'
            '    <td style="padding:6px 12px;font-weight:600;color:#555;">Dates</td>'
            '    <td style="padding:6px 12px;">{start_date} – {end_date}</td>'
            '  </tr>'
            '  <tr>'
            '    <td style="padding:6px 12px;font-weight:600;color:#555;">Total Days</td>'
            '    <td style="padding:6px 12px;">{total_days}</td>'
            '  </tr>'
            '  <tr>'
            '    <td style="padding:6px 12px;font-weight:600;color:#555;">Reason</td>'
            '    <td style="padding:6px 12px;">{reason}</td>'
            '  </tr>'
            '</table>'
            '<p>You will be notified as soon as it is actioned.</p>'
            '<p>Warm regards,<br/><strong>HR Team — {company_name}</strong></p>'
        ),
        'is_active':  True,
        'is_builtin': True,
        'available_variables': [
            'employee_name', 'leave_type', 'start_date', 'end_date',
            'total_days', 'reason', 'company_name',
        ],
    },
    {
        'name':         'leave_request_pending_approval',
        'display_name': 'Leave Request — Awaiting Your Approval',
        'description':  'Sent to the L1 or L2 approver when a leave request needs their action.',
        'template_type': 'hrms',
        'subject':      'Leave request awaiting your approval — {employee_name}',
        'body': (
            '<p>Dear {approver_name},</p>'
            '<p><strong>{employee_name}</strong> has submitted a <strong>{leave_type}</strong> '
            'request that requires your approval.</p>'
            '<table style="border-collapse:collapse;margin:16px 0;">'
            '  <tr>'
            '    <td style="padding:6px 12px;font-weight:600;color:#555;">Dates</td>'
            '    <td style="padding:6px 12px;">{start_date} – {end_date}</td>'
            '  </tr>'
            '  <tr>'
            '    <td style="padding:6px 12px;font-weight:600;color:#555;">Total Days</td>'
            '    <td style="padding:6px 12px;">{total_days}</td>'
            '  </tr>'
            '  <tr>'
            '    <td style="padding:6px 12px;font-weight:600;color:#555;">Reason</td>'
            '    <td style="padding:6px 12px;">{reason}</td>'
            '  </tr>'
            '</table>'
            '<p>Please review it at your earliest convenience.</p>'
            '<p>Warm regards,<br/><strong>HR Team — {company_name}</strong></p>'
        ),
        'is_active':  True,
        'is_builtin': True,
        'available_variables': [
            'approver_name', 'employee_name', 'leave_type', 'start_date',
            'end_date', 'total_days', 'reason', 'company_name',
        ],
    },
    {
        'name':         'leave_forwarded_to_hr',
        'display_name': 'Leave Request Forwarded to HR',
        'description':  'Sent to the employee when their manager approves and the request moves to HR.',
        'template_type': 'hrms',
        'subject':      'Your {leave_type} request has been forwarded to HR',
        'body': (
            '<p>Dear {employee_name},</p>'
            '<p>Good news — <strong>{approver_name}</strong> has approved your '
            '<strong>{leave_type}</strong> request ({start_date} – {end_date}), and it has '
            'now been forwarded to HR for final approval.</p>'
            '<p>You will be notified as soon as HR actions it.</p>'
            '<p>Warm regards,<br/><strong>HR Team — {company_name}</strong></p>'
        ),
        'is_active':  True,
        'is_builtin': True,
        'available_variables': [
            'employee_name', 'approver_name', 'leave_type', 'start_date',
            'end_date', 'company_name',
        ],
    },
    {
        'name':         'leave_approved',
        'display_name': 'Leave Request Approved',
        'description':  'Sent to the employee when their leave request receives final approval.',
        'template_type': 'hrms',
        'subject':      'Your {leave_type} request has been approved',
        'body': (
            '<p>Dear {employee_name},</p>'
            '<p>Your <strong>{leave_type}</strong> request for '
            '<strong>{start_date} – {end_date}</strong> ({total_days} day(s)) has been '
            '<strong style="color:#1b8a6b;">approved</strong> by {approver_name} ({approver_role}).</p>'
            '<p>Enjoy your time off!</p>'
            '<p>Warm regards,<br/><strong>HR Team — {company_name}</strong></p>'
        ),
        'is_active':  True,
        'is_builtin': True,
        'available_variables': [
            'employee_name', 'leave_type', 'start_date', 'end_date',
            'total_days', 'approver_name', 'approver_role', 'company_name',
        ],
    },
    {
        'name':         'leave_rejected',
        'display_name': 'Leave Request Rejected',
        'description':  'Sent to the employee when their leave request is rejected at any stage.',
        'template_type': 'hrms',
        'subject':      'Your {leave_type} request has been rejected',
        'body': (
            '<p>Dear {employee_name},</p>'
            '<p>Your <strong>{leave_type}</strong> request for '
            '<strong>{start_date} – {end_date}</strong> has been '
            '<strong style="color:#b91c1c;">rejected</strong> by {approver_name} ({approver_role}).</p>'
            '<p style="color:#888;font-size:13px;">Remarks: {remarks}</p>'
            '<p>If you have questions about this decision, please reach out to your approver or HR.</p>'
            '<p>Warm regards,<br/><strong>HR Team — {company_name}</strong></p>'
        ),
        'is_active':  True,
        'is_builtin': True,
        'available_variables': [
            'employee_name', 'leave_type', 'start_date', 'end_date',
            'approver_name', 'approver_role', 'remarks', 'company_name',
        ],
    },
    {
        'name':         'leave_cancelled',
        'display_name': 'Leave Request Cancelled',
        'description':  'Sent to the employee confirming their leave request was cancelled.',
        'template_type': 'hrms',
        'subject':      'Your {leave_type} request has been cancelled',
        'body': (
            '<p>Dear {employee_name},</p>'
            '<p>Your <strong>{leave_type}</strong> request for '
            '<strong>{start_date} – {end_date}</strong> has been cancelled.</p>'
            '<p>If this was not intentional, please submit a new request.</p>'
            '<p>Warm regards,<br/><strong>HR Team — {company_name}</strong></p>'
        ),
        'is_active':  True,
        'is_builtin': True,
        'available_variables': [
            'employee_name', 'leave_type', 'start_date', 'end_date', 'company_name',
        ],
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
        ('hrms',     '0013_seed_leave_approval_workflow'),
        ('accounts', '0042_clean_employee_role_permissions'),
    ]

    operations = [
        migrations.RunPython(seed_templates, remove_templates),
    ]
