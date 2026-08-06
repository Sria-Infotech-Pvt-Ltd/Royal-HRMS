"""
Grant recruitment.view to the system_admin role.

0002_seed_roles_permissions.py gave system_admin view-level access to every
other operational module it doesn't directly run day-to-day (attendance.view,
leave.view, payroll.view, expenses.view, announcements, documents) but never
included any recruitment.* codename. apps/recruitment/views.py's _has_perm()
only bypasses the check for Django's is_superuser flag — unlike every other
app's _has_perm, it has no "system_admin role name" bypass — so a system_admin
account without is_superuser=True (e.g. the demo sysadmin@royal.com seeded by
0003_seed_demo_users.py) gets a flat 403 on every recruitment endpoint,
including the Interview List page and its status filter tabs
(All/Pending/Selected/Rejected).

Granting recruitment.view closes the gap the same way it's already closed for
every other module, without giving system_admin the create/edit/delete/
approve rights that stay with HR/managers who actually run recruitment.
"""
from django.db import migrations

CODENAME = 'recruitment.view'


def seed_forward(apps, schema_editor):
    Role = apps.get_model('accounts', 'Role')
    Permission = apps.get_model('accounts', 'Permission')
    RolePermission = apps.get_model('accounts', 'RolePermission')

    try:
        role = Role.objects.get(name='system_admin')
        permission = Permission.objects.get(codename=CODENAME)
    except (Role.DoesNotExist, Permission.DoesNotExist):
        return

    RolePermission.objects.get_or_create(role=role, permission=permission)


def seed_reverse(apps, schema_editor):
    Role = apps.get_model('accounts', 'Role')
    Permission = apps.get_model('accounts', 'Permission')
    RolePermission = apps.get_model('accounts', 'RolePermission')

    try:
        role = Role.objects.get(name='system_admin')
        permission = Permission.objects.get(codename=CODENAME)
    except (Role.DoesNotExist, Permission.DoesNotExist):
        return
    RolePermission.objects.filter(role=role, permission=permission).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0057_grant_payroll_view_own_missing_roles'),
    ]

    operations = [
        migrations.RunPython(seed_forward, seed_reverse),
    ]
