from django.db import migrations


PORTAL_INVITE_BODY = """<p>Dear {candidate_name},</p>

<p>Congratulations! We are pleased to inform you that you have been selected for the position of <strong>{position}</strong> at <strong>{company_name}</strong>.</p>

<p>Please use the following credentials to access your onboarding portal and complete your profile:</p>

<table style="border-collapse:collapse;margin:16px 0;">
  <tr>
    <td style="padding:6px 12px;font-weight:600;color:#555;">Portal URL</td>
    <td style="padding:6px 12px;">{portal_url}</td>
  </tr>
  <tr>
    <td style="padding:6px 12px;font-weight:600;color:#555;">Login Email</td>
    <td style="padding:6px 12px;">{login_email}</td>
  </tr>
  <tr>
    <td style="padding:6px 12px;font-weight:600;color:#555;">Temporary Password</td>
    <td style="padding:6px 12px;font-family:monospace;letter-spacing:1px;">{temp_password}</td>
  </tr>
</table>

<p>Once you log in, you will be guided through a short onboarding wizard where you can fill in your personal, educational, and bank details and upload required documents.</p>

<p><strong>Please complete your profile at the earliest so HR can process your joining formalities.</strong></p>

<p style="color:#888;font-size:13px;">If you did not expect this email, please ignore it or contact HR immediately.</p>

<p>Warm regards,<br/><strong>HR Team — {company_name}</strong></p>"""


def seed_onboarding_permission_and_template(apps, schema_editor):
    Permission    = apps.get_model('accounts', 'Permission')
    Role          = apps.get_model('accounts', 'Role')
    RolePermission = apps.get_model('accounts', 'RolePermission')
    EmailTemplate = apps.get_model('accounts', 'EmailTemplate')

    # 1. Create onboarding.approve permission
    perm, _ = Permission.objects.get_or_create(
        codename='onboarding.approve',
        defaults={'module': 'onboarding', 'action': 'approve'},
    )

    # 2. Assign to hr_admin and system_admin
    for role_name in ('hr_admin', 'system_admin'):
        try:
            role = Role.objects.get(name=role_name)
            RolePermission.objects.get_or_create(role=role, permission=perm)
        except Role.DoesNotExist:
            pass

    # 3. Create portal_invite email template if it doesn't exist
    EmailTemplate.objects.get_or_create(
        name='portal_invite',
        defaults={
            'display_name':        'Portal Login Invitation',
            'description':         'Sent to selected candidates with their portal login credentials.',
            'template_type':       'recruitment',
            'subject':             'Your Onboarding Portal Access — {company_name}',
            'body':                PORTAL_INVITE_BODY,
            'is_active':           True,
            'is_builtin':          False,
            'available_variables': [
                'candidate_name', 'position', 'company_name',
                'login_email', 'temp_password', 'portal_url',
            ],
        },
    )


def reverse_migration(apps, schema_editor):
    Permission    = apps.get_model('accounts', 'Permission')
    EmailTemplate = apps.get_model('accounts', 'EmailTemplate')
    Permission.objects.filter(codename='onboarding.approve').delete()
    EmailTemplate.objects.filter(name='portal_invite').delete()


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0022_seed_system_admin_onboarding'),
    ]

    operations = [
        migrations.RunPython(
            seed_onboarding_permission_and_template,
            reverse_migration,
        ),
    ]
