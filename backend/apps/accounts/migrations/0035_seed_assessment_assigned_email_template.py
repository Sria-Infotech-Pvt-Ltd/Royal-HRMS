"""
Seed the assessment_assigned email template.
Sent to a candidate when HR manually assigns an assessment to them.
"""
from django.db import migrations

TEMPLATE = {
    'name':         'assessment_assigned',
    'display_name': 'Assessment Assigned',
    'description':  'Sent to a candidate when HR manually assigns a new assessment.',
    'template_type': 'onboarding',
    'subject':      'New Assessment Assigned — {company_name}',
    'body': (
        '<p>Dear {candidate_name},</p>'
        '<p>A new assessment has been assigned to you as part of your onboarding process at '
        '<strong>{company_name}</strong>.</p>'
        '<table style="border-collapse:collapse;margin:16px 0;">'
        '  <tr>'
        '    <td style="padding:6px 12px;font-weight:600;color:#555;">Assessment</td>'
        '    <td style="padding:6px 12px;">{assessment_title}</td>'
        '  </tr>'
        '  <tr>'
        '    <td style="padding:6px 12px;font-weight:600;color:#555;">Portal URL</td>'
        '    <td style="padding:6px 12px;">{portal_url}</td>'
        '  </tr>'
        '</table>'
        '<p>Please log in to your portal and complete this assessment at your earliest convenience. '
        'The onboarding wizard will become available once all assessments are completed.</p>'
        '<p><strong>Please complete this at the earliest so HR can process your joining formalities.</strong></p>'
        '<p style="color:#888;font-size:13px;">If you did not expect this email, please ignore it or contact HR immediately.</p>'
        '<p>Warm regards,<br/><strong>HR Team — {company_name}</strong></p>'
    ),
    'is_active':  True,
    'is_builtin': True,
    'available_variables': [
        'candidate_name',
        'assessment_title',
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
        ('accounts', '0034_seed_missing_email_template_categories'),
    ]

    operations = [
        migrations.RunPython(seed_template, remove_template),
    ]
