"""
Add tax_declarations.approve — gates HR review/approval of an employee's
submitted tax regime declaration. Same <module>.<verb> convention as
employees.confirm/hr_help.respond, granted to the same roles.
"""
from django.db import migrations

CODENAME = 'tax_declarations.approve'
ROLE_NAMES = ('system_admin', 'hr_admin', 'branch_admin')


def seed_forward(apps, schema_editor):
    Role = apps.get_model('accounts', 'Role')
    Permission = apps.get_model('accounts', 'Permission')
    RolePermission = apps.get_model('accounts', 'RolePermission')

    permission, _ = Permission.objects.get_or_create(
        codename=CODENAME,
        defaults={'module': 'tax_declarations', 'action': 'approve'},
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
        ('payroll', '0020_employee_tax_declaration'),
        ('accounts', '0153_seed_employees_confirm_permission'),
    ]

    operations = [
        migrations.RunPython(seed_forward, seed_reverse),
    ]
