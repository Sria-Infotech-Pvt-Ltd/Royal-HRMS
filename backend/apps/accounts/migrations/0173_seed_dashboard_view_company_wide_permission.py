"""
Add dashboard.view_company_wide — replaces a hardcoded role-name check
(user.role.name == 'system_admin') in apps/dashboard/views/overview.py's
_hr_dashboard_branch(), which decides whether the HR dashboard shows
company-wide totals or is scoped to the user's own branch.

Deliberately its own new permission rather than reusing settings.edit —
settings.edit is also granted to hr_admin/branch_admin (see
0002_seed_roles_permissions), which would leak company-wide totals to
branch-scoped HR users if used for this check. Granted only to
system_admin, matching the exact behavior the hardcoded check produced
today — a pure mechanical replacement, no behavior change.
"""
from django.db import migrations

CODENAME = 'dashboard.view_company_wide'
ROLE_NAMES = ('system_admin',)


def seed_forward(apps, schema_editor):
    Role = apps.get_model('accounts', 'Role')
    Permission = apps.get_model('accounts', 'Permission')
    RolePermission = apps.get_model('accounts', 'RolePermission')

    permission, _ = Permission.objects.get_or_create(
        codename=CODENAME,
        defaults={'module': 'dashboard', 'action': 'view_company_wide'},
    )
    for role_name in ROLE_NAMES:
        try:
            role = Role.objects.get(name=role_name)
        except Role.DoesNotExist:
            continue
        RolePermission.objects.get_or_create(role=role, permission=permission)


def seed_reverse(apps, schema_editor):
    Permission = apps.get_model('accounts', 'Permission')
    Permission.objects.filter(codename=CODENAME).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0172_seed_employees_edit_own_profile_permission'),
    ]

    operations = [
        migrations.RunPython(seed_forward, seed_reverse),
    ]
