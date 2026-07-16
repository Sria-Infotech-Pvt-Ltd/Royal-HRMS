"""
Seed the onboarding_submitted email template.
Sent to the assigned HR (or all hr_admins) when a candidate submits
the onboarding wizard and it is ready for HR review.
"""
from django.db import migrations

TEMPLATE = {
    'name':         'onboarding_submitted',
    'display_name': 'Onboarding Submitted (HR Notification)',
    'description':  'Sent to HR when a candidate submits the onboarding wizard for review.',
    'template_type': 'onboarding',
    'subject':      'Onboarding Submitted — {candidate_name} is ready for review',
    'body': (
        '<p>Dear {hr_name},</p>'
        '<p>A candidate has completed and submitted their onboarding wizard. '
        'Please log in to review and approve their details.</p>'
        '<table style="border-collapse:collapse;margin:16px 0;">'
        '  <tr>'
        '    <td style="padding:6px 12px;font-weight:600;color:#555;">Candidate</td>'
        '    <td style="padding:6px 12px;">{candidate_name}</td>'
        '  </tr>'
        '  <tr>'
        '    <td style="padding:6px 12px;font-weight:600;color:#555;">Email</td>'
        '    <td style="padding:6px 12px;">{candidate_email}</td>'
        '  </tr>'
        '</table>'
        '<p>Log in to the HR portal to review the submission and take action.</p>'
        '<p style="margin:20px 0;">'
        '  <a href="{portal_url}" '
        '     style="background:#1d4ed8;color:#fff;padding:10px 20px;border-radius:4px;'
        'text-decoration:none;font-weight:600;">Review Onboarding</a>'
        '</p>'
        '<p style="color:#888;font-size:13px;">This is an automated notification from the HRMS system.</p>'
        '<p>Regards,<br/><strong>HRMS — {company_name}</strong></p>'
    ),
    'is_active':  True,
    'is_builtin': True,
    'available_variables': [
        'hr_name',
        'candidate_name',
        'candidate_email',
        'company_name',
        'portal_url',
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
        ('accounts', '0035_seed_assessment_assigned_email_template'),
    ]

    operations = [
        migrations.RunPython(seed_template, remove_template),
    ]
