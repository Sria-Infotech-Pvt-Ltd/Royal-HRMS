"""
Remove attendance.create and payroll.view from the employee role.

attendance.create: every endpoint in the 'my attendance' section (punch, today,
stats, summary, calendar, correction) uses only IsAuthenticated — no codename
is ever checked. Keeping it on the employee role is misleading and may cause
the frontend to surface admin attendance UI elements for regular employees.

payroll.view: the payroll module is not yet implemented. When it is, employees
must only see their own payslip via a future 'my payroll' endpoint
(IsAuthenticated only), matching the pattern used in 'my attendance'. Granting
payroll.view now would give employees access to all-employee payroll records,
the same issue fixed for attendance in migration 0029.
"""
from django.db import migrations


REMOVE_FROM_EMPLOYEE = ['attendance.create', 'payroll.view']


def remove_permissions(apps, schema_editor):
    Role = apps.get_model('accounts', 'Role')
    Permission = apps.get_model('accounts', 'Permission')
    RolePermission = apps.get_model('accounts', 'RolePermission')

    try:
        employee_role = Role.objects.get(name='employee')
    except Role.DoesNotExist:
        return

    perms = Permission.objects.filter(codename__in=REMOVE_FROM_EMPLOYEE)
    RolePermission.objects.filter(role=employee_role, permission__in=perms).delete()


def restore_permissions(apps, schema_editor):
    Role = apps.get_model('accounts', 'Role')
    Permission = apps.get_model('accounts', 'Permission')
    RolePermission = apps.get_model('accounts', 'RolePermission')

    try:
        employee_role = Role.objects.get(name='employee')
    except Role.DoesNotExist:
        return

    for codename in REMOVE_FROM_EMPLOYEE:
        try:
            perm = Permission.objects.get(codename=codename)
            RolePermission.objects.get_or_create(role=employee_role, permission=perm)
        except Permission.DoesNotExist:
            pass


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0041_seed_departments_designations_permissions'),
    ]

    operations = [
        migrations.RunPython(remove_permissions, restore_permissions),
    ]
