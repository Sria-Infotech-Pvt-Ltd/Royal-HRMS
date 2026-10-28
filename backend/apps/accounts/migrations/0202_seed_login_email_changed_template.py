from django.db import migrations


LOGIN_EMAIL_CHANGED_BODY = """<p>Hi {employee_name},</p>

<p>The email address on your {company_name} account was changed by HR.</p>

<table style="border-collapse:collapse;margin:16px 0;">
  <tr>
    <td style="padding:6px 12px;font-weight:600;color:#555;">Previous email</td>
    <td style="padding:6px 12px;font-family:monospace;">{old_email}</td>
  </tr>
  <tr>
    <td style="padding:6px 12px;font-weight:600;color:#555;">New email</td>
    <td style="padding:6px 12px;font-family:monospace;">{new_email}</td>
  </tr>
</table>

<p>This is also the email you log in with, so sign in with the new address from now on. Your password has not changed.</p>

<p style="color:#888;font-size:13px;">If you did not expect this change, please contact your HR team straight away.</p>

<p>Regards,<br/><strong>HR Team — {company_name}</strong></p>"""


def seed_template(apps, schema_editor):
    EmailTemplate = apps.get_model('accounts', 'EmailTemplate')
    EmailTemplate.objects.get_or_create(
        name='login_email_changed',
        defaults={
            'display_name':        'Login Email Changed',
            'description':         'Sent to an employee, at the old and the new address, when HR changes their email (which is also their login).',
            'template_type':       'accounts',
            'subject':             'Your {company_name} login email was changed',
            'body':                LOGIN_EMAIL_CHANGED_BODY,
            'is_active':           True,
            'is_builtin':          False,
            'available_variables': ['employee_name', 'old_email', 'new_email', 'company_name'],
        },
    )


def reverse_migration(apps, schema_editor):
    EmailTemplate = apps.get_model('accounts', 'EmailTemplate')
    EmailTemplate.objects.filter(name='login_email_changed').delete()


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0201_welcome_email_face_id_block'),
    ]

    operations = [
        migrations.RunPython(seed_template, reverse_migration),
    ]
