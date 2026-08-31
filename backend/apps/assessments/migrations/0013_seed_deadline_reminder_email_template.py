"""
Seed the email template for the assessment deadline reminder
(apps.assessments.tasks.send_assessment_deadline_reminders). Previously
there was no reminder feature at all — an assignee who never opened the
portal got no nudge as their deadline approached.
"""
from django.db import migrations

_TEMPLATES = [
    {
        'name':         'assessment_deadline_reminder',
        'display_name': 'Assessment Deadline Reminder',
        'description':  'Sent once, roughly 24 hours before an assigned assessment\'s deadline, if not yet completed.',
        'template_type': 'reminder',
        'subject':      'Reminder: your assessment is due soon — {company_name}',
        'body': (
            '<p>Dear {candidate_name},</p>'
            '<p>This is a reminder that your assessment is due soon and has not yet been completed.</p>'
            '<table style="border-collapse:collapse;margin:16px 0;">'
            '  <tr>'
            '    <td style="padding:6px 12px;font-weight:600;color:#555;">Assessment</td>'
            '    <td style="padding:6px 12px;">{assessment_title}</td>'
            '  </tr>'
            '  <tr>'
            '    <td style="padding:6px 12px;font-weight:600;color:#555;">Deadline</td>'
            '    <td style="padding:6px 12px;">{deadline}</td>'
            '  </tr>'
            '  <tr>'
            '    <td style="padding:6px 12px;font-weight:600;color:#555;">Portal URL</td>'
            '    <td style="padding:6px 12px;">{portal_url}</td>'
            '  </tr>'
            '</table>'
            '<p>Please log in and complete it before the deadline above.</p>'
            '<p>Warm regards,<br/><strong>HR Team — {company_name}</strong></p>'
        ),
        'is_active':  True,
        'is_builtin': True,
        'available_variables': ['candidate_name', 'assessment_title', 'deadline', 'portal_url', 'company_name'],
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
        ('assessments', '0012_candidateassignment_deadline_reminder_sent_at'),
        ('accounts',    '0096_ensure_assessments_permissions_defaults'),
    ]

    operations = [
        migrations.RunPython(seed_templates, remove_templates),
    ]
