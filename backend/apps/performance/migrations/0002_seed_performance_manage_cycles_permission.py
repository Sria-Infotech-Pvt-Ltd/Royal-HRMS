"""
Add performance.manage_cycles — gates creating/closing review cycles and the
HR-wide review queue. Same <module>.<verb> convention as employees.confirm/
hr_help.respond/tax_declarations.approve, granted to the same roles.
"""
from django.db import migrations

CODENAME = 'performance.manage_cycles'
ROLE_NAMES = ('system_admin', 'hr_admin', 'branch_admin')


def seed_forward(apps, schema_editor):
    Role = apps.get_model('accounts', 'Role')
    Permission = apps.get_model('accounts', 'Permission')
    RolePermission = apps.get_model('accounts', 'RolePermission')

    permission, _ = Permission.objects.get_or_create(
        codename=CODENAME,
        defaults={'module': 'performance', 'action': 'manage_cycles'},
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
        ('performance', '0001_initial'),
        ('accounts', '0153_seed_employees_confirm_permission'),
    ]

    operations = [
        migrations.RunPython(seed_forward, seed_reverse),
    ]
