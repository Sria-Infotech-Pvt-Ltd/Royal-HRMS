"""
Add hr_help.respond — gates the HR-side queue for HRHelpRequest (list all
requests, respond, change status). Follows the same <module>.<verb>
convention as employees.confirm/employees.view_sensitive, granted to the
same roles that already hold those (system_admin, hr_admin, branch_admin).
"""
from django.db import migrations

CODENAME = 'hr_help.respond'
ROLE_NAMES = ('system_admin', 'hr_admin', 'branch_admin')


def seed_forward(apps, schema_editor):
    Role = apps.get_model('accounts', 'Role')
    Permission = apps.get_model('accounts', 'Permission')
    RolePermission = apps.get_model('accounts', 'RolePermission')

    permission, _ = Permission.objects.get_or_create(
        codename=CODENAME,
        defaults={'module': 'hr_help', 'action': 'respond'},
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
        ('hrms', '0032_hr_help_request'),
        ('accounts', '0153_seed_employees_confirm_permission'),
    ]

    operations = [
        migrations.RunPython(seed_forward, seed_reverse),
    ]
