"""
Phase 9B Task E — privacy.manage_dsr gates the HR-side DSR queue
(list/fulfil/reject). Follows the same <module>.<verb> convention and the
same role grant set as hr_help.respond.
"""
from django.db import migrations

CODENAME = 'privacy.manage_dsr'
ROLE_NAMES = ('system_admin', 'hr_admin', 'branch_admin')


def seed_forward(apps, schema_editor):
    Role = apps.get_model('accounts', 'Role')
    Permission = apps.get_model('accounts', 'Permission')
    RolePermission = apps.get_model('accounts', 'RolePermission')

    permission, _ = Permission.objects.get_or_create(
        codename=CODENAME,
        defaults={'module': 'privacy', 'action': 'manage_dsr'},
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
        ('platform_core', '0018_datasubjectrequest'),
        ('accounts', '0185_assetdepreciationrule_assetrequest'),
    ]

    operations = [
        migrations.RunPython(seed_forward, seed_reverse),
    ]
