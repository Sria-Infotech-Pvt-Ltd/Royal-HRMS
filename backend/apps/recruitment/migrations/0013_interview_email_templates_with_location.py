"""
Refresh (or create, if missing) the interview-scheduled email templates so
they actually tell the candidate how to attend — a direct link for video
calls, the branch address for in-person, and the interviewer's name —
instead of just a bare "Mode: Video Call" with no way to act on it.

Uses update_or_create rather than get_or_create: all three templates were
found completely absent from the live database despite the original seeding
migrations (0006/0007) being marked applied, so this heals that gap and
guarantees the new content lands regardless of what state a given
environment is actually in.
"""
from django.db import migrations

CANDIDATE_LOCATION_ROW = (
    '  <tr>'
    '    <td style="padding:6px 12px;font-weight:600;color:#555;">Time</td>'
    '    <td style="padding:6px 12px;">{interview_time_display}</td>'
    '  </tr>'
    '  <tr>'
    '    <td style="padding:6px 12px;font-weight:600;color:#555;">Interviewer</td>'
    '    <td style="padding:6px 12px;">{interviewer_name}</td>'
    '  </tr>'
    '  <tr>'
    '    <td style="padding:6px 12px;font-weight:600;color:#555;vertical-align:top;">Where / How to Join</td>'
    '    <td style="padding:6px 12px;">{location_details}</td>'
    '  </tr>'
)

CANDIDATE_VARS = [
    'candidate_name', 'position_applied', 'interview_date_display', 'interview_time_display',
    'interview_mode_display', 'interviewer_name', 'location_details', 'branch_name', 'company_name',
]

TEMPLATES = [
    {
        'name':         'interview_scheduled_candidate',
        'display_name': 'Interview Scheduled — Candidate Notification',
        'description':  'Sent to a candidate when HR schedules (or reschedules) their interview.',
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
            '    <td style="padding:6px 12px;">{interview_date_display}</td>'
            '  </tr>'
            f'{CANDIDATE_LOCATION_ROW}'
            '  <tr>'
            '    <td style="padding:6px 12px;font-weight:600;color:#555;">Branch</td>'
            '    <td style="padding:6px 12px;">{branch_name}</td>'
            '  </tr>'
            '</table>'
            '<p>A calendar invite is attached to this email — please add it to your calendar.</p>'
            '<p>Please ensure you are available on the scheduled date and time. '
            'If you need to reschedule, contact HR as soon as possible.</p>'
            '<p style="color:#888;font-size:13px;">'
            'If you did not expect this email, please contact HR immediately.'
            '</p>'
            '<p>Warm regards,<br/><strong>HR Team — {company_name}</strong></p>'
        ),
        'is_active':  True,
        'is_builtin': True,
        'available_variables': CANDIDATE_VARS,
    },
    {
        'name':         'referral_interview_scheduled_candidate',
        'display_name': 'Interview Scheduled — Referred Candidate Notification',
        'description':  'Sent to a referred candidate when HR schedules (or reschedules) their interview.',
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
            '    <td style="padding:6px 12px;">{interview_date_display}</td>'
            '  </tr>'
            f'{CANDIDATE_LOCATION_ROW}'
            '  <tr>'
            '    <td style="padding:6px 12px;font-weight:600;color:#555;">Branch</td>'
            '    <td style="padding:6px 12px;">{branch_name}</td>'
            '  </tr>'
            '</table>'
            '<p>A calendar invite is attached to this email — please add it to your calendar.</p>'
            '<p>Please ensure you are available on the scheduled date and time. '
            'If you need to reschedule, contact HR as soon as possible.</p>'
            '<p style="color:#888;font-size:13px;">'
            'If you did not expect this email, please contact HR immediately.'
            '</p>'
            '<p>Warm regards,<br/><strong>HR Team — {company_name}</strong></p>'
        ),
        'is_active':  True,
        'is_builtin': True,
        'available_variables': CANDIDATE_VARS,
    },
    {
        'name':         'referral_interview_scheduled_referrer',
        'display_name': 'Interview Scheduled — Referrer Notification',
        'description':  'Sent to the referring employee when their referral\'s interview is scheduled.',
        'template_type': 'recruitment',
        'subject':      'Update on your referral — {company_name}',
        'body': (
            '<p>Hi {referrer_name},</p>'
            '<p>Good news — an interview has been scheduled for your referral, '
            '<strong>{candidate_name}</strong>, for the <strong>{position_applied}</strong> role.</p>'
            '<table style="border-collapse:collapse;margin:16px 0;">'
            '  <tr>'
            '    <td style="padding:6px 12px;font-weight:600;color:#555;">Date</td>'
            '    <td style="padding:6px 12px;">{interview_date_display}</td>'
            '  </tr>'
            '</table>'
            '<p>We\'ll keep you posted as the process moves forward. Thank you for the referral!</p>'
            '<p>Warm regards,<br/><strong>HR Team — {company_name}</strong></p>'
        ),
        'is_active':  True,
        'is_builtin': True,
        'available_variables': [
            'referrer_name', 'candidate_name', 'position_applied', 'interview_date_display', 'company_name',
        ],
    },
]


def seed_forward(apps, schema_editor):
    EmailTemplate = apps.get_model('accounts', 'EmailTemplate')
    for tpl in TEMPLATES:
        EmailTemplate.objects.update_or_create(
            name=tpl['name'],
            defaults={k: v for k, v in tpl.items() if k != 'name'},
        )


def seed_reverse(apps, schema_editor):
    # No-op: reversing would delete templates that may have been customized
    # by an admin since this migration ran. Forward-only content refresh.
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('recruitment', '0012_candidate_interview_time_candidate_meeting_link'),
    ]

    operations = [
        migrations.RunPython(seed_forward, seed_reverse),
    ]
