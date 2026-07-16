"""
Force-update the five recruitment email templates to have the correct
single-brace placeholder body/subject.

Migrations 0006 and 0007 used get_or_create, which only sets defaults for
NEW records. If these templates already existed in the DB from a previous
dev session or manual creation, the correct bodies were never applied.
This migration fetches each template by name and overwrites subject, body,
and available_variables so the placeholders match what the code sends.
"""
from django.db import migrations

_TEMPLATES = [
    {
        'name':    'referral_submitted_referrer',
        'subject': 'Your referral for {candidate_name} has been received',
        'body': (
            '<p>Dear {referrer_name},</p>'
            '<p>Thank you for referring <strong>{candidate_name}</strong> for the '
            '<strong>{position_applied}</strong> role at <strong>{company_name}</strong>.</p>'
            '<p>We have received their details and our recruitment team will review the application. '
            'You will be notified of any updates.</p>'
            '<p style="color:#888;font-size:13px;">Branch: {branch_name}</p>'
            '<p>Warm regards,<br/><strong>HR Team — {company_name}</strong></p>'
        ),
        'available_variables': [
            'referrer_name', 'candidate_name', 'position_applied', 'branch_name', 'company_name',
        ],
    },
    {
        'name':    'referral_submitted_candidate',
        'subject': "You've been referred to {company_name}",
        'body': (
            '<p>Dear {candidate_name},</p>'
            '<p><strong>{referrer_name}</strong> has referred you for the '
            '<strong>{position_applied}</strong> position at <strong>{company_name}</strong>.</p>'
            '<p>Our recruitment team will review your profile and reach out if your application '
            'moves forward. No action is required from you at this stage.</p>'
            '<p>Warm regards,<br/><strong>HR Team — {company_name}</strong></p>'
        ),
        'available_variables': [
            'candidate_name', 'referrer_name', 'position_applied', 'company_name',
        ],
    },
    {
        'name':    'referral_interview_scheduled_candidate',
        'subject': 'Your interview has been scheduled — {company_name}',
        'body': (
            '<p>Dear {candidate_name},</p>'
            '<p>Great news! Your interview for the <strong>{position_applied}</strong> role at '
            '<strong>{company_name}</strong> has been scheduled.</p>'
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
            'Our HR team will share further details closer to the time.</p>'
            '<p>Warm regards,<br/><strong>HR Team — {company_name}</strong></p>'
        ),
        'available_variables': [
            'candidate_name', 'position_applied', 'interview_date',
            'interview_mode_display', 'branch_name', 'company_name',
        ],
    },
    {
        'name':    'referral_interview_scheduled_referrer',
        'subject': 'Update: {candidate_name} has been shortlisted',
        'body': (
            '<p>Dear {referrer_name},</p>'
            '<p>We are pleased to let you know that your referral, '
            '<strong>{candidate_name}</strong>, has been shortlisted for the '
            '<strong>{position_applied}</strong> role and an interview has been scheduled '
            'on <strong>{interview_date}</strong>.</p>'
            '<p>Thank you for helping us find great talent at <strong>{company_name}</strong>. '
            'We will keep you updated on further progress.</p>'
            '<p>Warm regards,<br/><strong>HR Team — {company_name}</strong></p>'
        ),
        'available_variables': [
            'referrer_name', 'candidate_name', 'position_applied', 'interview_date', 'company_name',
        ],
    },
    {
        'name':    'interview_scheduled_candidate',
        'subject': 'Your interview has been scheduled — {company_name}',
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
        'available_variables': [
            'candidate_name', 'position_applied', 'interview_date',
            'interview_mode_display', 'branch_name', 'company_name',
        ],
    },
]


def fix_templates(apps, schema_editor):
    EmailTemplate = apps.get_model('accounts', 'EmailTemplate')
    for tpl in _TEMPLATES:
        EmailTemplate.objects.update_or_create(
            name=tpl['name'],
            defaults={
                'subject':             tpl['subject'],
                'body':                tpl['body'],
                'available_variables': tpl['available_variables'],
                'is_active':           True,
                'is_builtin':          True,
                'template_type':       'recruitment',
            },
        )


def revert_templates(apps, schema_editor):
    pass  # no safe revert — forward-only fix


class Migration(migrations.Migration):

    dependencies = [
        ('recruitment', '0007_interview_scheduled_email_template'),
        ('accounts',    '0037_update_email_templates_for_new_assessment_flow'),
    ]

    operations = [
        migrations.RunPython(fix_templates, revert_templates),
    ]
