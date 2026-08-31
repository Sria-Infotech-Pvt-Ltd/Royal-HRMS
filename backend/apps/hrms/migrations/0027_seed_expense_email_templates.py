"""
Seed the email templates used by the expense claim lifecycle.
Wired up in apps/notifications/signals.py alongside the existing in-app
Notification records — expenses previously only ever notified in-app,
never automatically by email (an approver could optionally attach a
template on approve/reject, but nothing was sent by default — see
apps/hrms/views/expenses.py's _send_decision_email).
"""
from django.db import migrations

_TEMPLATES = [
    {
        'name':         'expense_submitted',
        'display_name': 'Expense Submitted — Employee Confirmation',
        'description':  'Sent to the employee confirming their expense claim was submitted.',
        'template_type': 'hrms',
        'subject':      'Your expense claim "{title}" has been submitted',
        'body': (
            '<p>Dear {employee_name},</p>'
            '<p>Your expense claim has been submitted successfully and is now awaiting approval.</p>'
            '<table style="border-collapse:collapse;margin:16px 0;">'
            '  <tr>'
            '    <td style="padding:6px 12px;font-weight:600;color:#555;">Title</td>'
            '    <td style="padding:6px 12px;">{title}</td>'
            '  </tr>'
            '  <tr>'
            '    <td style="padding:6px 12px;font-weight:600;color:#555;">Category</td>'
            '    <td style="padding:6px 12px;">{category}</td>'
            '  </tr>'
            '  <tr>'
            '    <td style="padding:6px 12px;font-weight:600;color:#555;">Amount</td>'
            '    <td style="padding:6px 12px;">₹{amount}</td>'
            '  </tr>'
            '  <tr>'
            '    <td style="padding:6px 12px;font-weight:600;color:#555;">Date</td>'
            '    <td style="padding:6px 12px;">{expense_date}</td>'
            '  </tr>'
            '</table>'
            '<p>You will be notified as soon as it is actioned.</p>'
            '<p>Warm regards,<br/><strong>HR Team — {company_name}</strong></p>'
        ),
        'is_active':  True,
        'is_builtin': True,
        'available_variables': [
            'employee_name', 'title', 'category', 'amount', 'expense_date', 'company_name',
        ],
    },
    {
        'name':         'expense_pending_approval',
        'display_name': 'Expense Claim — Awaiting Your Approval',
        'description':  'Sent to the resolved approver when an expense claim needs their action.',
        'template_type': 'hrms',
        'subject':      'Expense claim awaiting your approval — {employee_name}',
        'body': (
            '<p>Dear {approver_name},</p>'
            '<p><strong>{employee_name}</strong> has submitted an expense claim that requires '
            'your approval.</p>'
            '<table style="border-collapse:collapse;margin:16px 0;">'
            '  <tr>'
            '    <td style="padding:6px 12px;font-weight:600;color:#555;">Title</td>'
            '    <td style="padding:6px 12px;">{title}</td>'
            '  </tr>'
            '  <tr>'
            '    <td style="padding:6px 12px;font-weight:600;color:#555;">Category</td>'
            '    <td style="padding:6px 12px;">{category}</td>'
            '  </tr>'
            '  <tr>'
            '    <td style="padding:6px 12px;font-weight:600;color:#555;">Amount</td>'
            '    <td style="padding:6px 12px;">₹{amount}</td>'
            '  </tr>'
            '</table>'
            '<p>Please review it at your earliest convenience.</p>'
            '<p>Warm regards,<br/><strong>HR Team — {company_name}</strong></p>'
        ),
        'is_active':  True,
        'is_builtin': True,
        'available_variables': [
            'approver_name', 'employee_name', 'title', 'category', 'amount', 'company_name',
        ],
    },
    {
        'name':         'expense_approved',
        'display_name': 'Expense Claim Approved',
        'description':  'Sent to the employee when their expense claim is approved.',
        'template_type': 'hrms',
        'subject':      'Your expense claim "{title}" has been approved',
        'body': (
            '<p>Dear {employee_name},</p>'
            '<p>Your expense claim <strong>"{title}"</strong> for <strong>₹{amount}</strong> '
            'has been <strong style="color:#1b8a6b;">approved</strong>.</p>'
            '<p>It will be reimbursed in an upcoming payroll cycle.</p>'
            '<p>Warm regards,<br/><strong>HR Team — {company_name}</strong></p>'
        ),
        'is_active':  True,
        'is_builtin': True,
        'available_variables': ['employee_name', 'title', 'amount', 'company_name'],
    },
    {
        'name':         'expense_rejected',
        'display_name': 'Expense Claim Rejected',
        'description':  'Sent to the employee when their expense claim is rejected.',
        'template_type': 'hrms',
        'subject':      'Your expense claim "{title}" has been rejected',
        'body': (
            '<p>Dear {employee_name},</p>'
            '<p>Your expense claim <strong>"{title}"</strong> for <strong>₹{amount}</strong> '
            'has been <strong style="color:#b91c1c;">rejected</strong>.</p>'
            '<p>If you have questions about this decision, please reach out to your approver or HR.</p>'
            '<p>Warm regards,<br/><strong>HR Team — {company_name}</strong></p>'
        ),
        'is_active':  True,
        'is_builtin': True,
        'available_variables': ['employee_name', 'title', 'amount', 'company_name'],
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
        ('hrms',     '0026_seed_separation_email_templates'),
        ('accounts', '0096_ensure_assessments_permissions_defaults'),
    ]

    operations = [
        migrations.RunPython(seed_templates, remove_templates),
    ]
