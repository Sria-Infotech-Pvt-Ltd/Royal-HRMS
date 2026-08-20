"""
Revoke settings.edit from the HR role.

Same bug as 0070_revoke_settings_edit_from_branch_admin, for the same reason:
settings.edit is this codebase's implicit "bypass every branch/assignment
scope, act company-wide" flag (core/permissions.py has_perm), which HR was
never supposed to carry — HR is meant to be scoped to specifically assigned
employees only (see the branch_admin docstring in 0052_seed_branch_admin_role,
which explicitly contrasts itself with "HR (scoped to specifically assigned
employees)"). With settings.edit still attached, HR has had the same
unrestricted, company-wide access as System Admin in every scoping check
across leave, attendance, payroll, and settings.

Matches by name variant, not a single literal name, because role names have
already drifted in this data outside of tracked migrations (see 0043's note:
'hr_admin' -> 'hr').
"""
from django.db import migrations

CODENAME = 'settings.edit'
HR_NAME_VARIANTS = {'hr', 'hr_admin'}


def remove_permission(apps, schema_editor):
    Role = apps.get_model('accounts', 'Role')
    Permission = apps.get_model('accounts', 'Permission')
    RolePermission = apps.get_model('accounts', 'RolePermission')

    perm = Permission.objects.filter(codename=CODENAME).first()
    if not perm:
        return
    hr_roles = Role.objects.filter(name__in=HR_NAME_VARIANTS)
    RolePermission.objects.filter(role__in=hr_roles, permission=perm).delete()


def restore_permission(apps, schema_editor):
    Role = apps.get_model('accounts', 'Role')
    Permission = apps.get_model('accounts', 'Permission')
    RolePermission = apps.get_model('accounts', 'RolePermission')

    try:
        perm = Permission.objects.get(codename=CODENAME)
    except Permission.DoesNotExist:
        return
    for role in Role.objects.filter(name__in=HR_NAME_VARIANTS):
        RolePermission.objects.get_or_create(role=role, permission=perm)


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0076_mark_system_roles'),
    ]

    operations = [
        migrations.RunPython(remove_permission, restore_permission),
    ]
