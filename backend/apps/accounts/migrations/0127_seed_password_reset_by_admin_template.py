from django.db import migrations


PASSWORD_RESET_BY_ADMIN_BODY = """<p>Dear {employee_name},</p>

<p>Your password has been reset by an administrator. Use the temporary password below to log in:</p>

<table style="border-collapse:collapse;margin:16px 0;">
  <tr>
    <td style="padding:6px 12px;font-weight:600;color:#555;">Temporary Password</td>
    <td style="padding:6px 12px;font-family:monospace;letter-spacing:1px;">{temp_password}</td>
  </tr>
</table>

<p>You will be asked to change this password immediately after logging in.</p>

<p style="color:#888;font-size:13px;">If you did not expect this change, please contact HR immediately.</p>

<p>Regards,<br/><strong>HR Team — {company_name}</strong></p>"""


def seed_template(apps, schema_editor):
    EmailTemplate = apps.get_model('accounts', 'EmailTemplate')
    EmailTemplate.objects.get_or_create(
        name='password_reset_by_admin',
        defaults={
            'display_name':        'Password Reset by Admin',
            'description':         'Sent to an employee when HR/Admin resets their password.',
            'template_type':       'accounts',
            'subject':             'Your {company_name} Password Has Been Reset',
            'body':                PASSWORD_RESET_BY_ADMIN_BODY,
            'is_active':           True,
            'is_builtin':          False,
            'available_variables': ['employee_name', 'temp_password', 'company_name'],
        },
    )


def reverse_migration(apps, schema_editor):
    EmailTemplate = apps.get_model('accounts', 'EmailTemplate')
    EmailTemplate.objects.filter(name='password_reset_by_admin').delete()


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0126_seed_onboarding_edit_and_reset_password_permissions'),
    ]

    operations = [
        migrations.RunPython(seed_template, reverse_migration),
    ]
