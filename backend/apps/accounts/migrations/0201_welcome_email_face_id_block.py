"""
Add the Face ID instruction to the new-hire welcome email.

The email now carries {face_id_block}: one consistent Face ID instruction for the chosen registration mode, or nothing
when Face ID is not required. Only the built-in wording is changed: if an admin has already edited this template it is
left alone (the new variable is just made available to them).
"""
import importlib

from django.db import migrations

TEMPLATE_NAME = 'hire_welcome_credentials'
ANCHOR = '<p>You will be asked to change this password immediately after logging in.</p>'


def add_face_id_block(apps, schema_editor):
    EmailTemplate = apps.get_model('accounts', 'EmailTemplate')
    seeded = importlib.import_module(
        'apps.accounts.migrations.0190_seed_hire_welcome_credentials_template',
    ).HIRE_WELCOME_CREDENTIALS_BODY

    template = EmailTemplate.objects.filter(name=TEMPLATE_NAME).first()
    if template is None:
        return
    variables = list(template.available_variables or [])
    if 'face_id_block' not in variables:
        variables.append('face_id_block')
        template.available_variables = variables
    if template.body == seeded and ANCHOR in template.body:
        template.body = template.body.replace(ANCHOR, ANCHOR + '\n\n{face_id_block}', 1)
    template.save(update_fields=['body', 'available_variables'])


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0200_link_employees_to_branches'),
    ]

    operations = [
        migrations.RunPython(add_face_id_block, migrations.RunPython.noop),
    ]
