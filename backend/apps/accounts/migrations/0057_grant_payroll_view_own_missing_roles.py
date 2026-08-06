"""
Backfill payroll.view_own for any role that doesn't have it yet.

0043_seed_payroll_view_own_permission granted payroll.view_own to every role
that existed AT THAT TIME so all employees could see their own payslips. It's
a one-time data migration, so any role created afterwards — e.g. branch_admin
in 0050_seed_branch_admin_role, which lists payroll.view/export but not
payroll.view_own — never received it. Those users hit "You do not have
permission to view payslips." on MyPayslipsView / AcknowledgePayslipView /
PayslipQueryListView (all gated on payroll.view_own in
apps/payroll/views/payslips.py), even though viewing your own payslip isn't
meant to be restricted by role.

Re-running the same "grant to every role" pass (idempotent via
get_or_create) closes the gap for branch_admin now and any future role that
forgets to list it explicitly.
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
    # No-op: 0043's reverse already deletes the permission (and cascades its
    # RolePermission rows) when that migration is unwound.
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0056_user_profile_photo'),
    ]

    operations = [
        migrations.RunPython(seed_forward, seed_reverse),
    ]
