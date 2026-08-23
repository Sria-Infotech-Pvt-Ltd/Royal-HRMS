from django.db import migrations

# The Manager role's default permission set (seeded in
# 0002_seed_roles_permissions.py) originally included the full recruitment.*
# set and payroll.view, giving every manager access to Interview List,
# Review & Onboarding, and Payroll. Product decision: managers don't run
# recruitment or view payroll — those stay HR/System Admin only. Removing
# these codenames here (rather than editing the already-applied 0002
# migration) drops the corresponding nav items for every existing manager,
# since proxy.ts and navConfig.ts gate those pages on exactly these
# permissions.
REMOVED_CODENAMES = [
    'recruitment.view',
    'recruitment.create',
    'recruitment.edit',
    'recruitment.delete',
    'recruitment.approve',
    'payroll.view',
]


def remove_manager_permissions(apps, schema_editor):
    Role = apps.get_model('accounts', 'Role')
    RolePermission = apps.get_model('accounts', 'RolePermission')

    manager_role = Role.objects.filter(name='manager').first()
    if not manager_role:
        return

    RolePermission.objects.filter(
        role=manager_role,
        permission__codename__in=REMOVED_CODENAMES,
    ).delete()


def restore_manager_permissions(apps, schema_editor):
    Role = apps.get_model('accounts', 'Role')
    Permission = apps.get_model('accounts', 'Permission')
    RolePermission = apps.get_model('accounts', 'RolePermission')

    manager_role = Role.objects.filter(name='manager').first()
    if not manager_role:
        return

    for codename in REMOVED_CODENAMES:
        permission = Permission.objects.filter(codename=codename).first()
        if permission:
            RolePermission.objects.get_or_create(role=manager_role, permission=permission)


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0091_remove_company_brand_color'),
    ]

    operations = [
        migrations.RunPython(remove_manager_permissions, restore_manager_permissions),
    ]
