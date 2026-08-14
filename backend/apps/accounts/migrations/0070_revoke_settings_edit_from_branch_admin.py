"""
Revoke settings.edit from the branch_admin role.

0052_seed_branch_admin_role deliberately withheld settings.edit when creating
this role, documenting it as an implicit "bypass all branch scoping, treat as
global admin" flag used throughout the codebase (_has_perm('settings.edit')
in payroll/leave/expenses/attendance/recruitment/accounts). Despite that,
the live database has this permission attached to branch_admin (granted
2026-08-10, outside of any tracked migration — via Settings -> Roles), which
makes every branch_admin account see and act on every branch everywhere,
not just their own, contrary to the role's whole purpose.
"""
from django.db import migrations

CODENAME = 'settings.edit'
ROLE_NAME = 'branch_admin'


def remove_permission(apps, schema_editor):
    Role = apps.get_model('accounts', 'Role')
    Permission = apps.get_model('accounts', 'Permission')
    RolePermission = apps.get_model('accounts', 'RolePermission')

    try:
        role = Role.objects.get(name=ROLE_NAME)
    except Role.DoesNotExist:
        return
    perm = Permission.objects.filter(codename=CODENAME).first()
    if not perm:
        return
    RolePermission.objects.filter(role=role, permission=perm).delete()


def restore_permission(apps, schema_editor):
    Role = apps.get_model('accounts', 'Role')
    Permission = apps.get_model('accounts', 'Permission')
    RolePermission = apps.get_model('accounts', 'RolePermission')

    try:
        role = Role.objects.get(name=ROLE_NAME)
        perm = Permission.objects.get(codename=CODENAME)
    except (Role.DoesNotExist, Permission.DoesNotExist):
        return
    RolePermission.objects.get_or_create(role=role, permission=perm)


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0069_merge_20260813_1331'),
    ]

    operations = [
        migrations.RunPython(remove_permission, restore_permission),
    ]
