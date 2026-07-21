"""
Seed the candidate_selected and candidate_rejected email templates.
The interview-list "Mark Selected / Rejected" modal (frontend) locks onto these
two template names and sends whichever one matches the target status — with no
manual template picker — so both must exist as active templates for that flow
to work.
"""
from django.db import migrations

_TEMPLATES = [
    {
        'name':         'candidate_selected',
        'display_name': 'Candidate Selected — Notification',
        'description':  'Sent to a candidate when they are marked Selected in the interview pipeline.',
        'template_type': 'recruitment',
        'subject':      'Congratulations! You have been selected — {company_name}',
        'body': (
            '<p>Dear {candidate_name},</p>'
            '<p>Congratulations! We are pleased to inform you that you have been '
            '<strong>selected</strong> for the <strong>{position_applied}</strong> role '
            'at <strong>{company_name}</strong>.</p>'
            '<p>Your onboarding portal login credentials will be sent to you in a separate '
            'email shortly — please keep an eye on your inbox.</p>'
            '<p style="color:#888;font-size:13px;">Branch: {branch_name}</p>'
            '<p>We look forward to having you on the team!</p>'
            '<p>Warm regards,<br/><strong>HR Team — {company_name}</strong></p>'
        ),
        'is_active':  True,
        'is_builtin': True,
        'available_variables': [
            'candidate_name', 'position_applied', 'branch_name', 'company_name',
        ],
    },
    {
        'name':         'candidate_rejected',
        'display_name': 'Candidate Rejected — Notification',
        'description':  'Sent to a candidate when they are marked Rejected in the interview pipeline.',
        'template_type': 'recruitment',
        'subject':      'Update on your application — {company_name}',
        'body': (
            '<p>Dear {candidate_name},</p>'
            '<p>Thank you for taking the time to interview for the '
            '<strong>{position_applied}</strong> role at <strong>{company_name}</strong>.</p>'
            '<p>After careful consideration, we have decided to move forward with other '
            'candidates whose profile more closely matches our current requirements. '
            'This decision does not reflect on your skills or potential.</p>'
            '<p>We appreciate your interest in joining us and encourage you to apply for '
            'future openings that match your profile.</p>'
            '<p>Warm regards,<br/><strong>HR Team — {company_name}</strong></p>'
        ),
        'is_active':  True,
        'is_builtin': True,
        'available_variables': [
            'candidate_name', 'position_applied', 'company_name',
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
        ('recruitment', '0009_referralbonus'),
        ('accounts',    '0042_clean_employee_role_permissions'),
    ]

    operations = [
        migrations.RunPython(seed_templates, remove_templates),
    ]
