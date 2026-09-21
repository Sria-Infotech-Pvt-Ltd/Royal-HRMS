"""
Add employees.confirm — gates the Confirmation action (probation ->
confirmed). Follows the same <module>.<verb> convention as employees.edit/
employees.delete and separation.approve, and is granted to the same roles
that already hold employees.edit (system_admin, hr_admin, branch_admin).
"""
from django.db import migrations

CODENAME = 'employees.confirm'
ROLE_NAMES = ('system_admin', 'hr_admin', 'branch_admin')


def seed_forward(apps, schema_editor):
    Role = apps.get_model('accounts', 'Role')
    Permission = apps.get_model('accounts', 'Permission')
    RolePermission = apps.get_model('accounts', 'RolePermission')

    permission, _ = Permission.objects.get_or_create(
        codename=CODENAME,
        defaults={'module': 'employees', 'action': 'confirm'},
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
        ('accounts', '0152_employment_status_confirmation'),
    ]

    operations = [
        migrations.RunPython(seed_forward, seed_reverse),
    ]
