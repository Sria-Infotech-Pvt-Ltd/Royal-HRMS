"""
Seed two email templates for the HR-led recruitment path:

  - candidate_onboarding_link          the password-less, one-time link a selected candidate uses to open the onboarding wizard.
                                       It carries no password and does not create or activate an employee account.
  - interview_scheduled_interviewer    tells the assigned interviewer about the interview and where to submit feedback.

Idempotent (get_or_create): a template an administrator has already edited is left exactly as it is.
"""
from django.db import migrations

_TEMPLATES = [
    {
        'name':          'candidate_onboarding_link',
        'display_name':  'Candidate onboarding link',
        'description':   'Sent to a selected candidate: a one-time link to the onboarding wizard (no password, no account activation).',
        'template_type': 'recruitment',
        'subject':       'Complete your onboarding — {company_name}',
        'body': (
            '<p>Dear {candidate_name},</p>'
            '<p>Congratulations on being selected for the <strong>{position}</strong> role at {company_name}.</p>'
            '<p>Please use the secure link below to complete your onboarding form and upload your documents:</p>'
            '<p style="text-align:center;margin:24px 0;"><a href="{onboarding_link}" '
            'style="background:#4f46e5;color:#fff;padding:12px 28px;border-radius:6px;text-decoration:none;'
            'font-weight:bold;display:inline-block;">Open my onboarding form</a></p>'
            '<p style="color:#555;font-size:13px;">If the button does not work, copy this address into your browser:<br/>{onboarding_link}</p>'
            '<p>This link can be opened once and expires on <strong>{expires_on}</strong>. It only opens the onboarding '
            'form: it does not create your employee account and there is no password to remember yet. After HR reviews and '
            'approves your submission you will receive a separate email with your account activation link.</p>'
            '<p>If the link has expired, reply to this email and HR will send you a new one.</p>'
            '<p>Warm regards,<br/><strong>HR Team — {company_name}</strong></p>'
        ),
        'is_active': True,
        'is_builtin': True,
        'available_variables': ['candidate_name', 'position', 'company_name', 'onboarding_link', 'expires_on'],
    },
    {
        'name':          'interview_scheduled_interviewer',
        'display_name':  'Interview assigned to interviewer',
        'description':   'Sent to the interviewer when an interview is scheduled (or its time, link or interviewer changes).',
        'template_type': 'recruitment',
        'subject':       'Interview assigned: {candidate_name} — {position_applied}',
        'body': (
            '<p>Dear {interviewer_name},</p>'
            '<p>You have been assigned to interview <strong>{candidate_name}</strong> for the '
            '<strong>{position_applied}</strong> role.</p>'
            '<p><strong>Date:</strong> {interview_date_display}<br/>'
            '<strong>Time:</strong> {interview_time_display}<br/>'
            '<strong>Mode:</strong> {interview_mode_display}<br/>'
            '<strong>Link / location:</strong> {meeting_link} {location_details}</p>'
            '<p>After the interview, please submit your feedback (a rating, your recommendation and comments) in the HRMS under '
            '<strong>My interviews</strong>. HR reads all feedback before making the final decision.</p>'
            '<p>Warm regards,<br/><strong>HR Team — {company_name}</strong></p>'
        ),
        'is_active': True,
        'is_builtin': True,
        'available_variables': ['interviewer_name', 'candidate_name', 'position_applied', 'interview_date_display',
                                'interview_time_display', 'interview_mode_display', 'meeting_link', 'location_details', 'company_name'],
    },
]


def seed_templates(apps, schema_editor):
    EmailTemplate = apps.get_model('accounts', 'EmailTemplate')
    for tpl in _TEMPLATES:
        EmailTemplate.objects.get_or_create(name=tpl['name'], defaults={k: v for k, v in tpl.items() if k != 'name'})


def remove_templates(apps, schema_editor):
    EmailTemplate = apps.get_model('accounts', 'EmailTemplate')
    EmailTemplate.objects.filter(name__in=[t['name'] for t in _TEMPLATES]).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('recruitment', '0020_onboarding_link_and_interview_feedback'),
        ('accounts', '0214_onboarding_link_and_interview_feedback'),
    ]

    operations = [
        migrations.RunPython(seed_templates, remove_templates),
    ]
