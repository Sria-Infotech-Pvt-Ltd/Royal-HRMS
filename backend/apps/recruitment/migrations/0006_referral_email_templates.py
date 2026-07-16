"""
Seed the four email templates used by the referral flow.
All templates use {VARIABLE} single-brace substitution (EmailTemplate.render).
"""
from django.db import migrations

_TEMPLATES = [
    {
        'name':         'referral_submitted_referrer',
        'display_name': 'Referral Submitted — Referrer Notification',
        'description':  'Sent to the referring employee when their referral is received.',
        'template_type': 'recruitment',
        'subject':      'Your referral for {candidate_name} has been received',
        'body': (
            '<p>Dear {referrer_name},</p>'
            '<p>Thank you for referring <strong>{candidate_name}</strong> for the '
            '<strong>{position_applied}</strong> role at <strong>{company_name}</strong>.</p>'
            '<p>We have received their details and our recruitment team will review the application. '
            'You will be notified of any updates.</p>'
            '<p style="color:#888;font-size:13px;">Branch: {branch_name}</p>'
            '<p>Warm regards,<br/><strong>HR Team — {company_name}</strong></p>'
        ),
        'is_active':  True,
        'is_builtin': True,
        'available_variables': [
            'referrer_name', 'candidate_name', 'position_applied', 'branch_name', 'company_name',
        ],
    },
    {
        'name':         'referral_submitted_candidate',
        'display_name': 'Referral Submitted — Candidate Notification',
        'description':  'Sent to the referred candidate when they are first referred.',
        'template_type': 'recruitment',
        'subject':      "You've been referred to {company_name}",
        'body': (
            '<p>Dear {candidate_name},</p>'
            '<p><strong>{referrer_name}</strong> has referred you for the '
            '<strong>{position_applied}</strong> position at <strong>{company_name}</strong>.</p>'
            '<p>Our recruitment team will review your profile and reach out if your application '
            'moves forward. No action is required from you at this stage.</p>'
            '<p>Warm regards,<br/><strong>HR Team — {company_name}</strong></p>'
        ),
        'is_active':  True,
        'is_builtin': True,
        'available_variables': [
            'candidate_name', 'referrer_name', 'position_applied', 'company_name',
        ],
    },
    {
        'name':         'referral_interview_scheduled_candidate',
        'display_name': 'Referral Interview Scheduled — Candidate',
        'description':  'Sent to the referred candidate when an interview date is set.',
        'template_type': 'recruitment',
        'subject':      'Your interview has been scheduled — {company_name}',
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
        'is_active':  True,
        'is_builtin': True,
        'available_variables': [
            'candidate_name', 'position_applied', 'interview_date',
            'interview_mode_display', 'branch_name', 'company_name',
        ],
    },
    {
        'name':         'referral_interview_scheduled_referrer',
        'display_name': 'Referral Interview Scheduled — Referrer',
        'description':  'Sent to the referring employee when an interview is scheduled for their referral.',
        'template_type': 'recruitment',
        'subject':      'Update: {candidate_name} has been shortlisted',
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
        'is_active':  True,
        'is_builtin': True,
        'available_variables': [
            'referrer_name', 'candidate_name', 'position_applied', 'interview_date', 'company_name',
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
        ('recruitment', '0005_referralrule_seed'),
        ('accounts',    '0037_update_email_templates_for_new_assessment_flow'),
    ]

    operations = [
        migrations.RunPython(seed_templates, remove_templates),
    ]
