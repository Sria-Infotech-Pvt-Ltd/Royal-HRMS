"""
Seed the email templates used by the separation request lifecycle.
Wired up in apps/notifications/signals.py alongside the existing in-app
Notification records — separation requests previously only ever notified
in-app, never by email (unlike leave, which already emails on every
transition — see 0014_seed_leave_email_templates.py).
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
            '<p>Your <strong>{separation_type}</strong> request has been submitted successfully '
            'and is now awaiting approval.</p>'
            '<table style="border-collapse:collapse;margin:16px 0;">'
            '  <tr>'
            '    <td style="padding:6px 12px;font-weight:600;color:#555;">Proposed Last Working Day</td>'
            '    <td style="padding:6px 12px;">{proposed_last_working_day}</td>'
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
            'employee_name', 'separation_type', 'proposed_last_working_day',
            'notice_period_days', 'company_name',
        ],
    },
    {
        'name':         'separation_pending_approval',
        'display_name': 'Separation Request — Awaiting Your Approval',
        'description':  'Sent to an approval-stage approver when a separation request needs their action.',
        'template_type': 'hrms',
        'subject':      'Separation request awaiting your approval — {employee_name}',
        'body': (
            '<p>Dear {approver_name},</p>'
            '<p><strong>{employee_name}</strong> has submitted a <strong>{separation_type}</strong> '
            'request that requires your approval.</p>'
            '<table style="border-collapse:collapse;margin:16px 0;">'
            '  <tr>'
            '    <td style="padding:6px 12px;font-weight:600;color:#555;">Proposed Last Working Day</td>'
            '    <td style="padding:6px 12px;">{proposed_last_working_day}</td>'
            '  </tr>'
            '</table>'
            '<p>Please review it at your earliest convenience.</p>'
            '<p>Warm regards,<br/><strong>HR Team — {company_name}</strong></p>'
        ),
        'is_active':  True,
        'is_builtin': True,
        'available_variables': [
            'approver_name', 'employee_name', 'separation_type',
            'proposed_last_working_day', 'company_name',
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
            '<p>Your separation request has cleared its current approval stage and has now '
            'moved to the next stage.</p>'
            '<p>You will be notified as soon as it is fully actioned.</p>'
            '<p>Warm regards,<br/><strong>HR Team — {company_name}</strong></p>'
        ),
        'is_active':  True,
        'is_builtin': True,
        'available_variables': ['employee_name', 'company_name'],
    },
    {
        'name':         'separation_approved',
        'display_name': 'Separation Request Approved',
        'description':  'Sent to the employee when their separation request receives final approval.',
        'template_type': 'hrms',
        'subject':      'Your separation request has been approved',
        'body': (
            '<p>Dear {employee_name},</p>'
            '<p>Your separation request has been <strong style="color:#1b8a6b;">approved</strong>. '
            'Your proposed last working day is <strong>{proposed_last_working_day}</strong>.</p>'
            '<p>HR will be in touch regarding your exit formalities and handover.</p>'
            '<p>Warm regards,<br/><strong>HR Team — {company_name}</strong></p>'
        ),
        'is_active':  True,
        'is_builtin': True,
        'available_variables': ['employee_name', 'proposed_last_working_day', 'company_name'],
    },
    {
        'name':         'separation_rejected',
        'display_name': 'Separation Request Rejected',
        'description':  'Sent to the employee when their separation request is rejected at any stage.',
        'template_type': 'hrms',
        'subject':      'Your separation request has been rejected',
        'body': (
            '<p>Dear {employee_name},</p>'
            '<p>Your separation request has been <strong style="color:#b91c1c;">rejected</strong>.</p>'
            '<p>If you have questions about this decision, please reach out to your approver or HR.</p>'
            '<p>Warm regards,<br/><strong>HR Team — {company_name}</strong></p>'
        ),
        'is_active':  True,
        'is_builtin': True,
        'available_variables': ['employee_name', 'company_name'],
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
        ('accounts', '0096_ensure_assessments_permissions_defaults'),
    ]

    operations = [
        migrations.RunPython(seed_templates, remove_templates),
    ]
