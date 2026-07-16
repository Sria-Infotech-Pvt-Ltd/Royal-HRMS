from django.db import migrations


def seed_expense_permissions(apps, schema_editor):
    Permission     = apps.get_model('accounts', 'Permission')
    Role           = apps.get_model('accounts', 'Role')
    RolePermission = apps.get_model('accounts', 'RolePermission')

    view_perm, _ = Permission.objects.get_or_create(
        codename='expenses.view',
        defaults={'module': 'expenses', 'action': 'view'},
    )
    approve_perm, _ = Permission.objects.get_or_create(
        codename='expenses.approve',
        defaults={'module': 'expenses', 'action': 'approve'},
    )

    for role_name in ('employee', 'hr_admin', 'system_admin'):
        try:
            role = Role.objects.get(name=role_name)
            RolePermission.objects.get_or_create(role=role, permission=view_perm)
        except Role.DoesNotExist:
            pass

    for role_name in ('hr_admin', 'system_admin'):
        try:
            role = Role.objects.get(name=role_name)
            RolePermission.objects.get_or_create(role=role, permission=approve_perm)
        except Role.DoesNotExist:
            pass


def reverse_migration(apps, schema_editor):
    Permission = apps.get_model('accounts', 'Permission')
    Permission.objects.filter(codename__in=['expenses.view', 'expenses.approve']).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('hrms',     '0001_initial'),
        ('accounts', '0023_onboarding_permission_and_portal_template'),
    ]

    operations = [
        migrations.RunPython(seed_expense_permissions, reverse_migration),
    ]
