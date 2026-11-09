"""
Seed the email template used when someone emails a report from the Reports screen.

  - report_shared    "{sender_name} has shared a report with you": the CSV is attached; no data is placed in the body.

Idempotent (get_or_create): a template an administrator has already edited is left exactly as it is. The reverse step
removes only this template.
"""
from django.db import migrations

TEMPLATE = {
    'name': 'report_shared',
    'display_name': 'Report shared with you',
    'description': 'Sent when someone emails a report from the Reports screen. The report is attached as a CSV file.',
    'template_type': 'accounts',
    'subject': '{report_title} — shared by {sender_name}',
    'body': (
        '<p>Dear {recipient_name},</p>'
        '<p>{sender_name} has shared the <strong>{report_title}</strong> report with you ({row_count} rows, generated on {generated_on}). '
        'It is attached to this email as a CSV file.</p>'
        '<p><strong>Note from {sender_name}:</strong><br/>{note}</p>'
        '<p style="color:#555;font-size:13px;">This report may contain confidential employee information. Please do not forward it '
        'or store it anywhere that is not approved by {company_name}. Reply to this email to reach {sender_name}.</p>'
        '<p>Regards,<br/><strong>{company_name}</strong></p>'
    ),
    'is_active': True,
    'is_builtin': True,
    'available_variables': ['recipient_name', 'sender_name', 'report_title', 'row_count', 'generated_on', 'note', 'company_name'],
}


def seed(apps, schema_editor):
    EmailTemplate = apps.get_model('accounts', 'EmailTemplate')
    EmailTemplate.objects.get_or_create(name=TEMPLATE['name'], defaults={k: v for k, v in TEMPLATE.items() if k != 'name'})


def unseed(apps, schema_editor):
    apps.get_model('accounts', 'EmailTemplate').objects.filter(name=TEMPLATE['name']).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0214_onboarding_link_and_interview_feedback'),
    ]

    operations = [
        migrations.RunPython(seed, unseed),
    ]
