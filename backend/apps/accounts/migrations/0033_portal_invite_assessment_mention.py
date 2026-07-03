"""
Update the portal_invite email template body to mention the assessments
step that candidates must complete before reaching the onboarding wizard.
"""
from django.db import migrations

OLD_PARAGRAPH = (
    '<p>Once you log in, you will be guided through a short onboarding wizard '
    'where you can fill in your personal, educational, and bank details and '
    'upload required documents.</p>'
)

NEW_PARAGRAPHS = (
    '<p>Once you log in, you may be asked to complete a short assessment before '
    'proceeding. The assessment includes a brief video and a few questions to '
    'help us understand your profile better. <strong>Please complete all '
    'assessment tasks first</strong> — the onboarding wizard will unlock '
    'automatically once you are done.</p>'
    '\n\n'
    '<p>After the assessment, the onboarding wizard will guide you through '
    'filling in your personal, educational, and bank details and uploading '
    'required documents.</p>'
)


def update_portal_invite(apps, schema_editor):
    EmailTemplate = apps.get_model('accounts', 'EmailTemplate')
    try:
        template = EmailTemplate.objects.get(name='portal_invite')
    except EmailTemplate.DoesNotExist:
        return
    if OLD_PARAGRAPH in template.body:
        template.body = template.body.replace(OLD_PARAGRAPH, NEW_PARAGRAPHS)
        template.save(update_fields=['body'])


def revert_portal_invite(apps, schema_editor):
    EmailTemplate = apps.get_model('accounts', 'EmailTemplate')
    try:
        template = EmailTemplate.objects.get(name='portal_invite')
    except EmailTemplate.DoesNotExist:
        return
    if NEW_PARAGRAPHS in template.body:
        template.body = template.body.replace(NEW_PARAGRAPHS, OLD_PARAGRAPH)
        template.save(update_fields=['body'])


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0032_user_assessment_status'),
    ]

    operations = [
        migrations.RunPython(update_portal_invite, revert_portal_invite),
    ]
