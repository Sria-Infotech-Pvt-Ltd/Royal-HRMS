"""
Seed the interview_scheduled_candidate email template.
Sent to any candidate (non-referred) when an admin sets their interview date for the first time.
"""
from django.db import migrations

TEMPLATE = {
    'name':         'interview_scheduled_candidate',
    'display_name': 'Interview Scheduled — Candidate Notification',
    'description':  'Sent to a candidate when HR schedules their interview for the first time.',
    'template_type': 'recruitment',
    'subject':      'Your interview has been scheduled — {company_name}',
    'body': (
        '<p>Dear {candidate_name},</p>'
        '<p>We are pleased to inform you that your interview for the '
        '<strong>{position_applied}</strong> role at <strong>{company_name}</strong> '
        'has been scheduled.</p>'
        '<table style="border-collapse:collapse;margin:16px 0;">'
        '  <tr>'
        '    <td style="padding:6px 12px;font-weight:600;color:#555;">Date</td>'
        '    <td style="padding:6px 12px;">{interview_date}</td>'
        '  </tr>'
        '  <tr>'
        '    <td style="padding:6px 12px;font-weight:600;color:#555;">Mode</td>'
        '    <td style="padding:6px 12px;">{interview_mode_display}</td>'
        '  </tr>'
        '  <tr>'
        '    <td style="padding:6px 12px;font-weight:600;color:#555;">Branch</td>'
        '    <td style="padding:6px 12px;">{branch_name}</td>'
        '  </tr>'
        '</table>'
        '<p>Please ensure you are available on the scheduled date. '
        'Our HR team will reach out with further details closer to the time.</p>'
        '<p style="color:#888;font-size:13px;">'
        'If you did not expect this email, please contact HR immediately.'
        '</p>'
        '<p>Warm regards,<br/><strong>HR Team — {company_name}</strong></p>'
    ),
    'is_active':  True,
    'is_builtin': True,
    'available_variables': [
        'candidate_name', 'position_applied', 'interview_date',
        'interview_mode_display', 'branch_name', 'company_name',
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
        ('recruitment', '0006_referral_email_templates'),
        ('accounts',    '0037_update_email_templates_for_new_assessment_flow'),
    ]

    operations = [
        migrations.RunPython(seed_template, remove_template),
    ]
