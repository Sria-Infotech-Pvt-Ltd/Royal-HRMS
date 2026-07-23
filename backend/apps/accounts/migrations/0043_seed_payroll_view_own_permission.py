"""
Add payroll.view_own — a distinct permission for viewing one's own payslips,
separate from payroll.view (view every employee's payroll records, HR-only).

Granted to every existing role by default so every authenticated user can see
their own payslips regardless of role, without also granting visibility into
the HR "Payroll" admin page which still requires payroll.view. Role names
have drifted from the original seed (e.g. 'hr_admin' -> 'hr') outside of
tracked migrations, so this grants to whatever roles actually exist rather
than a hardcoded name list.
"""
from django.db import migrations

CODENAME = 'payroll.view_own'


def seed_forward(apps, schema_editor):
    Role = apps.get_model('accounts', 'Role')
    Permission = apps.get_model('accounts', 'Permission')
    RolePermission = apps.get_model('accounts', 'RolePermission')

    permission, _ = Permission.objects.get_or_create(
        codename=CODENAME,
        defaults={'module': 'payroll', 'action': 'view_own'},
    )
    for role in Role.objects.all():
        RolePermission.objects.get_or_create(role=role, permission=permission)


def seed_reverse(apps, schema_editor):
    Permission = apps.get_model('accounts', 'Permission')
    Permission.objects.filter(codename=CODENAME).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0042_clean_employee_role_permissions'),
    ]

    operations = [
        migrations.RunPython(seed_forward, seed_reverse),
    ]
