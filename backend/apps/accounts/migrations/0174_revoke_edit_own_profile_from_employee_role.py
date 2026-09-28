"""
Revoke employees.edit_own_profile from the 'employee' role by default —
per explicit product decision: employees should NOT be able to change
their own profile photo / edit their own profile details unless HR
turns it back on for that role. All other roles (system_admin, hr_admin,
branch_admin, etc.) keep the permission granted from migration 0172,
since HR/admin editing their own record was never in question.

This only changes the 'employee' role's default — the permission itself
still exists and is still fully toggleable per role from Settings > Roles,
exactly like any other permission in this codebase.
"""
from django.db import migrations

CODENAME = 'employees.edit_own_profile'
ROLE_NAME = 'employee'


def revoke_forward(apps, schema_editor):
    Role = apps.get_model('accounts', 'Role')
    Permission = apps.get_model('accounts', 'Permission')
    RolePermission = apps.get_model('accounts', 'RolePermission')

    try:
        role = Role.objects.get(name=ROLE_NAME)
    except Role.DoesNotExist:
        return
    try:
        permission = Permission.objects.get(codename=CODENAME)
    except Permission.DoesNotExist:
        return
    RolePermission.objects.filter(role=role, permission=permission).delete()


def revoke_reverse(apps, schema_editor):
    Role = apps.get_model('accounts', 'Role')
    Permission = apps.get_model('accounts', 'Permission')
    RolePermission = apps.get_model('accounts', 'RolePermission')

    try:
        role = Role.objects.get(name=ROLE_NAME)
        permission = Permission.objects.get(codename=CODENAME)
    except (Role.DoesNotExist, Permission.DoesNotExist):
        return
    RolePermission.objects.get_or_create(role=role, permission=permission)


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0173_seed_dashboard_view_company_wide_permission'),
    ]

    operations = [
        migrations.RunPython(revoke_forward, revoke_reverse),
    ]
