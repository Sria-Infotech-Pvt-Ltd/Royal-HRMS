"""
Revoke payroll.create/edit/delete from the HR role — 0053_flip_payroll_admin_hr
never actually took effect.

0053's documented intent was to move payroll execution to Branch Admin and
off HR entirely, granting branch_admin the three codenames and revoking them
from hr. The grant half worked (branch_admin is a real, stable role name),
but the revoke half did `Role.objects.filter(name='hr').first()` — the
tracked role is 'hr_admin' (0002_seed_roles_permissions), so on any
environment that only ran tracked migrations this silently matched nothing
and hr_admin kept full payroll.create/edit/delete, exactly like the earlier
'hr' vs 'hr_admin' bug fixed for facial_recognition.approve in
0119_fix_facial_recognition_approve_grants. Confirmed live: hr_admin still
holds all three codenames today.

Matches by name variant, not a single literal name, for the same reason as
0077_revoke_settings_edit_from_hr — role names have drifted in this data
outside of tracked migrations.
"""
from django.db import migrations

PAYROLL_RUN_CODENAMES = ['payroll.create', 'payroll.edit', 'payroll.delete']
HR_NAME_VARIANTS = {'hr', 'hr_admin'}


def forward(apps, schema_editor):
    Role = apps.get_model('accounts', 'Role')
    RolePermission = apps.get_model('accounts', 'RolePermission')

    hr_roles = Role.objects.filter(name__in=HR_NAME_VARIANTS)
    RolePermission.objects.filter(
        role__in=hr_roles, permission__codename__in=PAYROLL_RUN_CODENAMES,
    ).delete()


def reverse(apps, schema_editor):
    Role = apps.get_model('accounts', 'Role')
    Permission = apps.get_model('accounts', 'Permission')
    RolePermission = apps.get_model('accounts', 'RolePermission')

    for role in Role.objects.filter(name__in=HR_NAME_VARIANTS):
        for codename in PAYROLL_RUN_CODENAMES:
            permission = Permission.objects.filter(codename=codename).first()
            if permission:
                RolePermission.objects.get_or_create(role=role, permission=permission)


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0119_fix_facial_recognition_approve_grants'),
    ]

    operations = [
        migrations.RunPython(forward, reverse),
    ]
