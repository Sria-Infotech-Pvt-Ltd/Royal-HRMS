"""
Revoke employees.reset_password from the plain 'employee' role.

Migration 0126 grants this permission to hr_admin / system_admin / branch_admin
only ("same footprint as employees.edit"). The 'employee' role was nevertheless
found holding it in a live database — which let ANY employee reset another
employee's password in their branch (and force them off every session). Nothing
in this repository's migrations grants it to 'employee', so the grant came from
data, not code; this puts every environment back on the documented footprint.
It is still toggleable per role from Settings > Roles for anyone who really
wants it, and the views now also require employees.edit (see
views_reset_password._can_manage_accounts), so a stray grant is not enough.
"""
from django.db import migrations

CODENAME = 'employees.reset_password'
ROLE_NAME = 'employee'


def revoke(apps, schema_editor):
    RolePermission = apps.get_model('accounts', 'RolePermission')
    RolePermission.objects.filter(role__name=ROLE_NAME, permission__codename=CODENAME).delete()


def restore(apps, schema_editor):
    Role = apps.get_model('accounts', 'Role')
    Permission = apps.get_model('accounts', 'Permission')
    RolePermission = apps.get_model('accounts', 'RolePermission')
    role = Role.objects.filter(name=ROLE_NAME).first()
    permission = Permission.objects.filter(codename=CODENAME).first()
    if role and permission:
        RolePermission.objects.get_or_create(role=role, permission=permission)


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0181_seed_employees_raise_action_permission'),
    ]

    operations = [
        migrations.RunPython(revoke, restore),
    ]
