"""
Add employees.view_sensitive — gates viewing unmasked PAN/Aadhaar/bank
account details on an employee's record, separate from employees.view
(see the record at all) and employees.edit (change those fields). Granted
to the same roles that already hold payroll.view (system_admin, hr_admin,
branch_admin) — the roles this app already treats as "can see sensitive
employee data" — not to employee/manager.
"""
from django.db import migrations

CODENAME = 'employees.view_sensitive'
ROLE_NAMES = ('system_admin', 'hr_admin', 'branch_admin')


def seed_forward(apps, schema_editor):
    Role = apps.get_model('accounts', 'Role')
    Permission = apps.get_model('accounts', 'Permission')
    RolePermission = apps.get_model('accounts', 'RolePermission')

    permission, _ = Permission.objects.get_or_create(
        codename=CODENAME,
        defaults={'module': 'employees', 'action': 'view_sensitive'},
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
        ('accounts', '0147_seed_education_experience_field_config'),
    ]

    operations = [
        migrations.RunPython(seed_forward, seed_reverse),
    ]
