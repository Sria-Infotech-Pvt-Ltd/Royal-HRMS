"""
Seed the email templates used when a payslip is dispatched
(DispatchPayslipsView.post) or a cycle is marked paid (MarkCyclePaidView.
post). Both previously only notified L1/L2 approvers during the approval
gate (see apps/payroll/notifications.py) — the employee whose payslip
actually became visible, or who was actually paid, was never emailed at
all; they'd only find out by opening the portal.
"""
from django.db import migrations

_TEMPLATES = [
    {
        'name':         'payslip_dispatched',
        'display_name': 'Payslip Ready',
        'description':  'Sent to an employee when their payslip for a cycle is dispatched.',
        'template_type': 'hrms',
        'subject':      'Your payslip for {cycle_month} is ready',
        'body': (
            '<p>Dear {employee_name},</p>'
            '<p>Your payslip for <strong>{cycle_month}</strong> is now ready to view in the '
            'HRMS portal.</p>'
            '<table style="border-collapse:collapse;margin:16px 0;">'
            '  <tr>'
            '    <td style="padding:6px 12px;font-weight:600;color:#555;">Net Pay</td>'
            '    <td style="padding:6px 12px;">₹{net_pay}</td>'
            '  </tr>'
            '</table>'
            '<p>If you have any questions about this payslip, you can raise a query before '
            '<strong>{query_deadline}</strong>.</p>'
            '<p>Warm regards,<br/><strong>HR Team — {company_name}</strong></p>'
        ),
        'is_active':  True,
        'is_builtin': True,
        'available_variables': [
            'employee_name', 'cycle_month', 'net_pay', 'query_deadline', 'company_name',
        ],
    },
    {
        'name':         'payslip_paid',
        'display_name': 'Salary Credited',
        'description':  'Sent to an employee when their salary for a cycle is marked as paid.',
        'template_type': 'hrms',
        'subject':      'Your salary for {cycle_month} has been credited',
        'body': (
            '<p>Dear {employee_name},</p>'
            '<p>Your salary for <strong>{cycle_month}</strong> has been credited.</p>'
            '<table style="border-collapse:collapse;margin:16px 0;">'
            '  <tr>'
            '    <td style="padding:6px 12px;font-weight:600;color:#555;">Net Pay</td>'
            '    <td style="padding:6px 12px;">₹{net_pay}</td>'
            '  </tr>'
            '</table>'
            '<p>Your full payslip is available in the HRMS portal.</p>'
            '<p>Warm regards,<br/><strong>HR Team — {company_name}</strong></p>'
        ),
        'is_active':  True,
        'is_builtin': True,
        'available_variables': ['employee_name', 'cycle_month', 'net_pay', 'company_name'],
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
        ('payroll',  '0017_payrollsettings_default_working_days_per_month_and_more'),
        ('accounts', '0096_ensure_assessments_permissions_defaults'),
    ]

    operations = [
        migrations.RunPython(seed_templates, remove_templates),
    ]
