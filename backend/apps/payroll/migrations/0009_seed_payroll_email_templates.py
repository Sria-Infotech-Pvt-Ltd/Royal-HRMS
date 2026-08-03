"""
Seed the two email templates used by the payroll approval notification flow.

payroll_l1_approval_required — sent to each manager when a cycle enters the
                               Approval stage (and again as a 24-hour reminder).
payroll_l2_approval_required — sent to HR when all L1 managers have approved
                               and the cycle is ready for HR sign-off.
"""
from django.db import migrations

_TEMPLATES = [
    {
        'name':         'payroll_l1_approval_required',
        'display_name': 'Payroll Attendance Sign-off Required (Manager)',
        'description':  'Sent to each manager when a payroll cycle enters the Approval stage.',
        'template_type': 'hrms',
        'subject':      'Action required: Payroll attendance sign-off for {month}',
        'body': (
            '<p>Dear {manager_name},</p>'
            '<p>The payroll cycle for <strong>{month}</strong> has been initiated and is '
            'waiting for your attendance sign-off before it can proceed.</p>'
            '<table style="border-collapse:collapse;margin:16px 0;">'
            '  <tr>'
            '    <td style="padding:6px 16px;font-weight:600;color:#555;">Cycle Period</td>'
            '    <td style="padding:6px 16px;">{cycle_start} &ndash; {cycle_end}</td>'
            '  </tr>'
            '  <tr style="background:#f8f9fa;">'
            '    <td style="padding:6px 16px;font-weight:600;color:#555;">Pay Date</td>'
            '    <td style="padding:6px 16px;">{pay_date}</td>'
            '  </tr>'
            '</table>'
            '<p>Please log in to the HRMS portal and approve your team\'s attendance '
            'under <strong>Payroll &rarr; Approval</strong>.</p>'
            '<p>Warm regards,<br/><strong>HR Team &mdash; {company_name}</strong></p>'
        ),
        'is_active':  True,
        'is_builtin': True,
        'available_variables': [
            'manager_name', 'month', 'cycle_start', 'cycle_end', 'pay_date', 'company_name',
        ],
    },
    {
        'name':         'payroll_l2_approval_required',
        'display_name': 'Payroll Ready for HR Sign-off (L2)',
        'description':  'Sent to HR when all managers have approved and the cycle is ready for L2 sign-off.',
        'template_type': 'hrms',
        'subject':      'All managers approved — {month} payroll ready for your sign-off',
        'body': (
            '<p>Dear {hr_name},</p>'
            '<p>All managers have completed their attendance sign-off for the '
            '<strong>{month}</strong> payroll cycle. The cycle is now ready for your '
            '<strong>HR (L2) approval</strong>.</p>'
            '<table style="border-collapse:collapse;margin:16px 0;">'
            '  <tr>'
            '    <td style="padding:6px 16px;font-weight:600;color:#555;">Cycle Period</td>'
            '    <td style="padding:6px 16px;">{cycle_start} &ndash; {cycle_end}</td>'
            '  </tr>'
            '  <tr style="background:#f8f9fa;">'
            '    <td style="padding:6px 16px;font-weight:600;color:#555;">Pay Date</td>'
            '    <td style="padding:6px 16px;">{pay_date}</td>'
            '  </tr>'
            '</table>'
            '<p>Please log in to the HRMS portal and complete your sign-off under '
            '<strong>Payroll &rarr; Approval</strong> to unlock payroll processing.</p>'
            '<p>Warm regards,<br/><strong>HR Team &mdash; {company_name}</strong></p>'
        ),
        'is_active':  True,
        'is_builtin': True,
        'available_variables': [
            'hr_name', 'month', 'cycle_start', 'cycle_end', 'pay_date', 'company_name',
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
        ('payroll',  '0008_add_epf_statutory_rates_to_payroll_settings'),
        ('accounts', '0048_add_uan_aadhar_to_employee_profile'),
    ]

    operations = [
        migrations.RunPython(seed_templates, remove_templates),
    ]
