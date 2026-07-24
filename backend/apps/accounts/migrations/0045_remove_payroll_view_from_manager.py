"""
Remove payroll.view from the manager role.

Manager should only ever see their own payslip (payroll.view_own, granted to
every role by migration 0043_seed_payroll_view_own_permission) — never the
HR-only "Payroll" admin module. The original seed (0002_seed_roles_permissions)
granted payroll.view to a role named 'manager'; migration
0042_clean_employee_role_permissions later did the equivalent cleanup for
'employee' but nothing was ever done for manager.

Verified against the live database before writing this migration (per an
explicit ask not to hardcode a stale role name): the role's `name` is
currently 'manager__team_lead', not 'manager' — it was renamed via
Settings -> Roles outside of any tracked migration, matching the drift
already called out in 0043_seed_payroll_view_own_permission's docstring.
Targeting 'manager' here would silently no-op.
"""
from django.db import migrations

CODENAME = 'payroll.view'
ROLE_NAME = 'manager__team_lead'


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
        ('accounts', '0044_grant_payroll_edit_to_hr'),
    ]

    operations = [
        migrations.RunPython(remove_permission, restore_permission),
    ]
