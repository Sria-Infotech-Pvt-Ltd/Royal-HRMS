"""
Seed the email template for the self-service password-reset confirmation
(ResetPasswordView._reset). Previously this only created an in-app
Notification — a genuine security-relevant event (password just changed)
never reached the user's inbox, only the in-app feed they may not check.
"""
from django.db import migrations

_TEMPLATES = [
    {
        'name':         'password_reset_confirmation',
        'display_name': 'Password Reset Confirmation',
        'description':  'Sent to a user immediately after they successfully reset their own password.',
        'template_type': 'notification',
        'subject':      'Your password was just reset',
        'body': (
            '<p>Dear {employee_name},</p>'
            '<p>Your password was just reset successfully.</p>'
            '<p style="color:#b91c1c;">If you did not request this change, contact your HR '
            'representative immediately.</p>'
            '<p>Warm regards,<br/><strong>HR Team — {company_name}</strong></p>'
        ),
        'is_active':  True,
        'is_builtin': True,
        'available_variables': ['employee_name', 'company_name'],
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
        ('accounts', '0097_auditlog_user_created_idx'),
    ]

    operations = [
        migrations.RunPython(seed_templates, remove_templates),
    ]
