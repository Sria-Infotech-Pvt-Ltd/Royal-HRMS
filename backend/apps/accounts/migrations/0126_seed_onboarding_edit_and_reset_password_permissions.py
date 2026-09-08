from django.db import migrations


def seed_permissions(apps, schema_editor):
    Permission     = apps.get_model('accounts', 'Permission')
    Role           = apps.get_model('accounts', 'Role')
    RolePermission = apps.get_model('accounts', 'RolePermission')

    onboarding_edit_perm, _ = Permission.objects.get_or_create(
        codename='onboarding.edit',
        defaults={'module': 'onboarding', 'action': 'edit'},
    )
    reset_password_perm, _ = Permission.objects.get_or_create(
        codename='employees.reset_password',
        defaults={'module': 'employees', 'action': 'reset_password'},
    )

    # Same footprint as onboarding.approve / employees.edit today — both new
    # permissions extend capabilities those three roles already hold.
    for role_name in ('hr_admin', 'system_admin', 'branch_admin'):
        try:
            role = Role.objects.get(name=role_name)
            RolePermission.objects.get_or_create(role=role, permission=onboarding_edit_perm)
            RolePermission.objects.get_or_create(role=role, permission=reset_password_perm)
        except Role.DoesNotExist:
            pass


def reverse_migration(apps, schema_editor):
    Permission = apps.get_model('accounts', 'Permission')
    Permission.objects.filter(codename__in=['onboarding.edit', 'employees.reset_password']).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0125_seed_email_log_permissions'),
    ]

    operations = [
        migrations.RunPython(seed_permissions, reverse_migration),
    ]
