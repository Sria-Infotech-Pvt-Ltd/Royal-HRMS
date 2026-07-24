"""
Grant payroll.edit to the hr role.

apps/payroll/views/payslips.py previously gated payslip mutation endpoints
(reimbursement/bonus updates, dispatch, query resolution) with a hardcoded
role-name check — `user.role.name in ('hr', 'system_admin')` — instead of a
permission codename. Replacing that check with `_has_perm(user,
'payroll.edit')` would silently lock out hr, since payroll.edit was only
ever granted to system_admin (payroll.view, payroll.create, payroll.delete,
and payroll.export show the same gap — out of scope here, only payroll.edit
is needed by the payslips.py endpoints being fixed).

This migration is depended on by two prior migrations that both claimed the
"0043" slot independently (0043_company_financial_year and
0043_seed_payroll_view_own_permission) — listing both as dependencies here
merges the two branches without a separate empty merge migration.
"""
from django.db import migrations

CODENAME = 'payroll.edit'
ROLE_NAME = 'hr'


def grant(apps, schema_editor):
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
    RolePermission.objects.get_or_create(role=role, permission=permission)


def revoke(apps, schema_editor):
    Role = apps.get_model('accounts', 'Role')
    Permission = apps.get_model('accounts', 'Permission')
    RolePermission = apps.get_model('accounts', 'RolePermission')

    try:
        role = Role.objects.get(name=ROLE_NAME)
        permission = Permission.objects.get(codename=CODENAME)
    except (Role.DoesNotExist, Permission.DoesNotExist):
        return
    RolePermission.objects.filter(role=role, permission=permission).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0043_company_financial_year'),
        ('accounts', '0043_seed_payroll_view_own_permission'),
    ]

    operations = [
        migrations.RunPython(grant, revoke),
    ]
