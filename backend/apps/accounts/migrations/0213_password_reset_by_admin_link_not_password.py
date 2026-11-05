from django.db import migrations


NEW_BODY = """<p>Dear {employee_name},</p>

<p>Your password has been reset by an administrator. Click the link below to set a new password:</p>

<p style="text-align:center;margin:28px 0;">
  <a href="{reset_link}" style="background:#4f46e5;color:#fff;padding:12px 28px;
  border-radius:6px;text-decoration:none;font-weight:bold;display:inline-block;">
  Set Your New Password</a>
</p>

<p>This link is valid for <strong>24 hours</strong> and can only be used once. Your previous password no
longer works.</p>

<p style="color:#888;font-size:13px;">If you did not expect this change, please contact HR immediately.</p>

<p>Regards,<br/><strong>HR Team — {company_name}</strong></p>"""

OLD_BODY = """<p>Dear {employee_name},</p>

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


def forwards(apps, schema_editor):
    EmailTemplate = apps.get_model('accounts', 'EmailTemplate')
    EmailTemplate.objects.filter(name='password_reset_by_admin').update(
        body=NEW_BODY,
        available_variables=['employee_name', 'reset_link', 'company_name'],
    )


def backwards(apps, schema_editor):
    EmailTemplate = apps.get_model('accounts', 'EmailTemplate')
    EmailTemplate.objects.filter(name='password_reset_by_admin').update(
        body=OLD_BODY,
        available_variables=['employee_name', 'temp_password', 'company_name'],
    )


class Migration(migrations.Migration):
    """The admin-reset email used to put a raw temporary password in the
    message body — a real plaintext-credential channel. Converts it to the
    same single-use-link pattern as the onboarding invite email (see
    apps.accounts.utils.send_activation_invite / _reset_link): the employee
    clicks through and sets their own password, nobody but them ever sees it."""

    dependencies = [
        ('accounts', '0212_repair_employee_code_series_columns'),
    ]

    operations = [
        migrations.RunPython(forwards, backwards),
    ]
