"""
Add separation.approve — gates approving/rejecting/deleting Separation Requests
in apps.hrms (views/separation.py), mirroring leave.approve's role.

Granted to every role that already holds leave.approve rather than a
hardcoded role-name list: leave.approve is exactly the set of "manager/HR
tier" roles in this codebase (manager, hr_admin, branch_admin as of this
migration), and role names have drifted from the original seed outside of
tracked migrations (see 0043_seed_payroll_view_own_permission), so this
grants to whatever roles actually match that shape today.
"""
from django.db import migrations

CODENAME = 'separation.approve'


def seed_forward(apps, schema_editor):
    Role = apps.get_model('accounts', 'Role')
    Permission = apps.get_model('accounts', 'Permission')
    RolePermission = apps.get_model('accounts', 'RolePermission')

    permission, _ = Permission.objects.get_or_create(
        codename=CODENAME,
        defaults={'module': 'separation', 'action': 'approve'},
    )
    leave_approve_role_ids = RolePermission.objects.filter(
        permission__codename='leave.approve'
    ).values_list('role_id', flat=True)
    for role in Role.objects.filter(id__in=leave_approve_role_ids):
        RolePermission.objects.get_or_create(role=role, permission=permission)


def seed_reverse(apps, schema_editor):
    Permission = apps.get_model('accounts', 'Permission')
    Permission.objects.filter(codename=CODENAME).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0062_employeeprofile_pan_number'),
    ]

    operations = [
        migrations.RunPython(seed_forward, seed_reverse),
    ]
