"""
Seed the five email templates used by the separation request lifecycle.

Separation requests had no dedicated email templates at all — the two-stage
approval chain (see apps.hrms.models.SeparationRequest) only ever fired
in-app Notification rows via apps.notifications.signals, never an email.
Mirrors the shape of 0014_seed_leave_email_templates.py / 0017_seed_expense_email_templates.py.
"""
from django.db import migrations

_TEMPLATES = [
    {
        'name':         'separation_request_submitted',
        'display_name': 'Separation Request Submitted — Employee Confirmation',
        'description':  'Sent to the employee confirming their separation request was submitted.',
        'template_type': 'hrms',
        'subject':      'Your separation request has been submitted',
        'body': (
            '<p>Dear {employee_name},</p>'
            '<p>Your <strong>{separation_type}</strong> separation request has been submitted '
            'successfully and is now awaiting approval.</p>'
            '<table style="border-collapse:collapse;margin:16px 0;">'
            '  <tr>'
            '    <td style="padding:6px 12px;font-weight:600;color:#555;">Reason</td>'
            '    <td style="padding:6px 12px;">{reason}</td>'
            '  </tr>'
            '  <tr>'
            '    <td style="padding:6px 12px;font-weight:600;color:#555;">Proposed Last Working Day</td>'
            '    <td style="padding:6px 12px;">{last_working_day}</td>'
            '  </tr>'
            '  <tr>'
            '    <td style="padding:6px 12px;font-weight:600;color:#555;">Notice Period</td>'
            '    <td style="padding:6px 12px;">{notice_period_days} day(s)</td>'
            '  </tr>'
            '</table>'
            '<p>You will be notified as soon as it is actioned.</p>'
            '<p>Warm regards,<br/><strong>HR Team — {company_name}</strong></p>'
        ),
        'is_active':  True,
        'is_builtin': True,
        'available_variables': [
            'employee_name', 'separation_type', 'reason', 'last_working_day',
            'notice_period_days', 'company_name',
        ],
    },
    {
        'name':         'separation_request_pending_approval',
        'display_name': 'Separation Request — Awaiting Your Approval',
        'description':  'Sent to the stage approver when a separation request needs their action.',
        'template_type': 'hrms',
        'subject':      'Separation request awaiting your approval — {employee_name}',
        'body': (
            '<p>Dear {approver_name},</p>'
            '<p><strong>{employee_name}</strong> has submitted a <strong>{separation_type}</strong> '
            'separation request that requires your <strong>{stage_name}</strong> approval.</p>'
            '<table style="border-collapse:collapse;margin:16px 0;">'
            '  <tr>'
            '    <td style="padding:6px 12px;font-weight:600;color:#555;">Reason</td>'
            '    <td style="padding:6px 12px;">{reason}</td>'
            '  </tr>'
            '  <tr>'
            '    <td style="padding:6px 12px;font-weight:600;color:#555;">Proposed Last Working Day</td>'
            '    <td style="padding:6px 12px;">{last_working_day}</td>'
            '  </tr>'
            '</table>'
            '<p>Please review it at your earliest convenience.</p>'
            '<p>Warm regards,<br/><strong>HR Team — {company_name}</strong></p>'
        ),
        'is_active':  True,
        'is_builtin': True,
        'available_variables': [
            'approver_name', 'employee_name', 'separation_type', 'reason',
            'last_working_day', 'stage_name', 'company_name',
        ],
    },
    {
        'name':         'separation_stage_approved',
        'display_name': 'Separation Request — Stage Approved',
        'description':  'Sent to the employee when one approval stage clears and the request moves to the next.',
        'template_type': 'hrms',
        'subject':      'Your separation request has moved to the next approval stage',
        'body': (
            '<p>Dear {employee_name},</p>'
            '<p>Good news — <strong>{approver_name}</strong> has approved the '
            '<strong>{stage_name}</strong> stage of your separation request, and it has now '
            'moved to <strong>{next_stage_name}</strong> approval.</p>'
            '<p>You will be notified as soon as it is actioned.</p>'
            '<p>Warm regards,<br/><strong>HR Team — {company_name}</strong></p>'
        ),
        'is_active':  True,
        'is_builtin': True,
        'available_variables': [
            'employee_name', 'approver_name', 'stage_name', 'next_stage_name', 'company_name',
        ],
    },
    {
        'name':         'separation_approved',
        'display_name': 'Separation Request Approved',
        'description':  'Sent to the employee when their separation request receives final approval.',
        'template_type': 'hrms',
        'subject':      'Your separation request has been approved',
        'body': (
            '<p>Dear {employee_name},</p>'
            '<p>Your <strong>{separation_type}</strong> separation request has been '
            '<strong style="color:#1b8a6b;">fully approved</strong>. Your proposed last working '
            'day is <strong>{last_working_day}</strong>.</p>'
            '<p>HR will reach out with next steps for your exit formalities.</p>'
            '<p>Warm regards,<br/><strong>HR Team — {company_name}</strong></p>'
        ),
        'is_active':  True,
        'is_builtin': True,
        'available_variables': [
            'employee_name', 'separation_type', 'last_working_day', 'company_name',
        ],
    },
    {
        'name':         'separation_rejected',
        'display_name': 'Separation Request Rejected',
        'description':  'Sent to the employee when their separation request is rejected at any stage.',
        'template_type': 'hrms',
        'subject':      'Your separation request has been rejected',
        'body': (
            '<p>Dear {employee_name},</p>'
            '<p>Your separation request has been <strong style="color:#b91c1c;">rejected</strong> '
            'by {approver_name} at the <strong>{stage_name}</strong> stage.</p>'
            '<p style="color:#888;font-size:13px;">Remarks: {remarks}</p>'
            '<p>If you have questions about this decision, please reach out to your approver or HR.</p>'
            '<p>Warm regards,<br/><strong>HR Team — {company_name}</strong></p>'
        ),
        'is_active':  True,
        'is_builtin': True,
        'available_variables': [
            'employee_name', 'approver_name', 'stage_name', 'remarks', 'company_name',
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
        ('hrms',     '0025_wfhsavedlocation'),
        ('accounts', '0135_rename_branch_admin_display_name'),
    ]

    operations = [
        migrations.RunPython(seed_templates, remove_templates),
    ]
