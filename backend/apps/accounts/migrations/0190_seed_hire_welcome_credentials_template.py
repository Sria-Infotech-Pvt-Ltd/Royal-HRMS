from django.db import migrations


HIRE_WELCOME_CREDENTIALS_BODY = """<p>Hi {employee_name},</p>

<p>Your {company_name} account has been created{employee_id_line}.</p>

<p>Use the credentials below to log in:</p>

<table style="border-collapse:collapse;margin:16px 0;">
  <tr>
    <td style="padding:6px 12px;font-weight:600;color:#555;">Email</td>
    <td style="padding:6px 12px;font-family:monospace;">{employee_email}</td>
  </tr>
  <tr>
    <td style="padding:6px 12px;font-weight:600;color:#555;">Temporary Password</td>
    <td style="padding:6px 12px;font-family:monospace;letter-spacing:1px;">{temp_password}</td>
  </tr>
</table>

<p>You will be asked to change this password immediately after logging in.</p>

<p style="color:#888;font-size:13px;">If you did not expect this email, please contact your HR team.</p>

<p>Regards,<br/><strong>HR Team — {company_name}</strong></p>"""


def seed_template(apps, schema_editor):
    EmailTemplate = apps.get_model('accounts', 'EmailTemplate')
    EmailTemplate.objects.get_or_create(
        name='hire_welcome_credentials',
        defaults={
            'display_name':        'New Hire Welcome (Credentials)',
            'description':         'Sent to a newly hired employee with their login email and a temporary password.',
            'template_type':       'accounts',
            'subject':             'Welcome to {company_name} — Your Login Details',
            'body':                HIRE_WELCOME_CREDENTIALS_BODY,
            'is_active':           True,
            'is_builtin':          False,
            'available_variables': ['employee_name', 'employee_email', 'employee_id_line', 'temp_password', 'company_name'],
        },
    )


def reverse_migration(apps, schema_editor):
    EmailTemplate = apps.get_model('accounts', 'EmailTemplate')
    EmailTemplate.objects.filter(name='hire_welcome_credentials').delete()


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0189_seed_mother_name_field_config'),
    ]

    operations = [
        migrations.RunPython(seed_template, reverse_migration),
    ]
