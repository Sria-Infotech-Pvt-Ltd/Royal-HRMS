"""
Add a Google Maps link right after the address in the interview-scheduled
candidate emails — "123 Main St, Hyderabad" on its own told a candidate
where to go but gave them nothing to tap/click to actually navigate there.

{location_map_link} (core/template_context.py's candidate_context()) is a
pre-built HTML snippet, already empty for video-call/phone interviews or an
in-person one with no branch address, so it's safe to always drop right
after {location_details} with no template-side conditional needed.
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
    '    <td style="padding:6px 12px;">{location_details}{location_map_link}</td>'
    '  </tr>'
)

CANDIDATE_VARS = [
    'candidate_name', 'position_applied', 'interview_date_display', 'interview_time_display',
    'interview_mode_display', 'interviewer_name', 'location_details', 'location_map_link',
    'branch_name', 'company_name',
]

TEMPLATES = [
    {
        'name': 'interview_scheduled_candidate',
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
        'available_variables': CANDIDATE_VARS,
    },
    {
        'name': 'referral_interview_scheduled_candidate',
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
        'available_variables': CANDIDATE_VARS,
    },
]


def seed_forward(apps, schema_editor):
    EmailTemplate = apps.get_model('accounts', 'EmailTemplate')
    for tpl in TEMPLATES:
        EmailTemplate.objects.filter(name=tpl['name']).update(
            body=tpl['body'],
            available_variables=tpl['available_variables'],
        )


def seed_reverse(apps, schema_editor):
    # No-op — reversing would drop the map link from a template an admin
    # may have further customized since. Forward-only content refresh,
    # same convention as 0013.
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('recruitment', '0018_candidateconsent_candidateduplicatemerge_and_more'),
    ]

    operations = [
        migrations.RunPython(seed_forward, seed_reverse),
    ]
