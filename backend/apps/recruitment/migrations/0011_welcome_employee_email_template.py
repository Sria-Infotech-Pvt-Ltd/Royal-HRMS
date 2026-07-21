"""
Seed the welcome_employee email template.
CandidateHRDecisionView falls back to this exact name when HR approves a
selected candidate for onboarding without picking a template explicitly —
it never existed, so that fallback silently failed until now.
"""
from django.db import migrations

TEMPLATE = {
    'name':         'welcome_employee',
    'display_name': 'Welcome to the Team',
    'description':  'Sent to a candidate when HR gives final approval to onboard them as an employee.',
    'template_type': 'onboarding',
    'subject':      'Welcome to {company_name}, {candidate_name}!',
    'body': (
        '<p>Dear {candidate_name},</p>'
        '<p>Congratulations and welcome! We are delighted to confirm that you have '
        'been onboarded as an employee at <strong>{company_name}</strong> for the '
        '<strong>{position_applied}</strong> role.</p>'
        '<p>Your onboarding portal will guide you through any remaining steps. '
        'Our HR team will be in touch shortly with your first-day details.</p>'
        '<p>We are excited to have you on board and look forward to working with you.</p>'
        '<p>Warm regards,<br/><strong>HR Team — {company_name}</strong></p>'
    ),
    'is_active':  True,
    'is_builtin': True,
    'available_variables': [
        'candidate_name', 'position_applied', 'company_name',
    ],
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
        ('recruitment', '0010_candidate_selected_rejected_email_templates'),
        ('accounts',    '0042_clean_employee_role_permissions'),
    ]

    operations = [
        migrations.RunPython(seed_template, remove_template),
    ]
