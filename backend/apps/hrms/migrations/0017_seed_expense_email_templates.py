"""
Seed the two email templates used by the expense approval lifecycle.

Expense approval had no dedicated email templates at all — the "Approve
expense" modal could only offer unrelated templates (Pay Slip, Leave Request
Approved, birthday wishes, ...) whose variables can never resolve for an
expense record, since fields like leave_type/start_date or MONTH/YEAR simply
don't exist on an Expense. Mirrors the shape of 0014_seed_leave_email_templates.py.
"""
from django.db import migrations

_TEMPLATES = [
    {
        'name':         'expense_approved',
        'display_name': 'Expense Claim Approved',
        'description':  'Sent to the employee when their expense claim is approved.',
        'template_type': 'hrms',
        'subject':      'Your expense claim has been approved',
        'body': (
            '<p>Dear {employee_name},</p>'
            '<p>Your expense claim <strong>"{title}"</strong> ({category}) for '
            '<strong>{amount}</strong> has been '
            '<strong style="color:#1b8a6b;">approved</strong> by {approver_name} ({approver_role}).</p>'
            '<table style="border-collapse:collapse;margin:16px 0;">'
            '  <tr>'
            '    <td style="padding:6px 12px;font-weight:600;color:#555;">Expense Date</td>'
            '    <td style="padding:6px 12px;">{expense_date}</td>'
            '  </tr>'
            '  <tr>'
            '    <td style="padding:6px 12px;font-weight:600;color:#555;">Amount</td>'
            '    <td style="padding:6px 12px;">{amount}</td>'
            '  </tr>'
            '</table>'
            '<p>Warm regards,<br/><strong>HR Team — {company_name}</strong></p>'
        ),
        'is_active':  True,
        'is_builtin': True,
        'available_variables': [
            'employee_name', 'title', 'category', 'amount', 'expense_date',
            'approver_name', 'approver_role', 'company_name',
        ],
    },
    {
        'name':         'expense_rejected',
        'display_name': 'Expense Claim Rejected',
        'description':  'Sent to the employee when their expense claim is rejected.',
        'template_type': 'hrms',
        'subject':      'Your expense claim has been rejected',
        'body': (
            '<p>Dear {employee_name},</p>'
            '<p>Your expense claim <strong>"{title}"</strong> ({category}) for '
            '<strong>{amount}</strong> has been '
            '<strong style="color:#b91c1c;">rejected</strong> by {approver_name} ({approver_role}).</p>'
            '<p style="color:#888;font-size:13px;">Remarks: {remarks}</p>'
            '<p>If you have questions about this decision, please reach out to your approver or HR.</p>'
            '<p>Warm regards,<br/><strong>HR Team — {company_name}</strong></p>'
        ),
        'is_active':  True,
        'is_builtin': True,
        'available_variables': [
            'employee_name', 'title', 'category', 'amount',
            'approver_name', 'approver_role', 'remarks', 'company_name',
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
        ('hrms',     '0016_merge_0014_carry_forward_0015_merge_20260722_1100'),
        ('accounts', '0047_role_add_can_manage_team'),
    ]

    operations = [
        migrations.RunPython(seed_templates, remove_templates),
    ]
