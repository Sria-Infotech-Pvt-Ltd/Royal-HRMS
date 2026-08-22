"""
Add org_chart.view — a distinct, low-sensitivity permission for the read-only
Organisation Chart page, separate from employees.view (browse/manage the
full employee list, admin-tier only).

Industry-standard org-chart behavior: it's company-directory information,
not employee-management data, so every employee sees it by default,
regardless of role. Granted to every existing role for that reason — same
pattern as 0043_seed_payroll_view_own_permission (payroll.view_own) — rather
than a hardcoded role-name list, since role names have drifted from the
original seed outside of tracked migrations.
"""
from django.db import migrations

CODENAME = 'org_chart.view'


def seed_forward(apps, schema_editor):
    Role = apps.get_model('accounts', 'Role')
    Permission = apps.get_model('accounts', 'Permission')
    RolePermission = apps.get_model('accounts', 'RolePermission')

    permission, _ = Permission.objects.get_or_create(
        codename=CODENAME,
        defaults={'module': 'org_chart', 'action': 'view'},
    )
    for role in Role.objects.all():
        RolePermission.objects.get_or_create(role=role, permission=permission)


def seed_reverse(apps, schema_editor):
    Permission = apps.get_model('accounts', 'Permission')
    Permission.objects.filter(codename=CODENAME).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0085_merge_20260820_2222'),
    ]

    operations = [
        migrations.RunPython(seed_forward, seed_reverse),
    ]
