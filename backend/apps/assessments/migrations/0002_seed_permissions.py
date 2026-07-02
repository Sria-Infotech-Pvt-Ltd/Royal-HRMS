"""
Seed assessments permissions and assign them to hr_admin and system_admin roles.
"""
from django.db import migrations

ASSESSMENT_PERMISSIONS = [
    ('assessments', 'view',   'assessments.view'),
    ('assessments', 'create', 'assessments.create'),
    ('assessments', 'edit',   'assessments.edit'),
    ('assessments', 'delete', 'assessments.delete'),
]

ROLES_WITH_FULL_ACCESS = ('hr_admin', 'system_admin')


def seed_permissions(apps, schema_editor):
    Permission    = apps.get_model('accounts', 'Permission')
    Role          = apps.get_model('accounts', 'Role')
    RolePermission = apps.get_model('accounts', 'RolePermission')

    permissions = []
    for module, action, codename in ASSESSMENT_PERMISSIONS:
        perm, _ = Permission.objects.get_or_create(
            codename=codename,
            defaults={'module': module, 'action': action},
        )
        permissions.append(perm)

    for role_name in ROLES_WITH_FULL_ACCESS:
        try:
            role = Role.objects.get(name=role_name)
        except Role.DoesNotExist:
            continue
        for perm in permissions:
            RolePermission.objects.get_or_create(role=role, permission=perm)


def remove_permissions(apps, schema_editor):
    Permission = apps.get_model('accounts', 'Permission')
    Permission.objects.filter(module='assessments').delete()


class Migration(migrations.Migration):

    dependencies = [
        ('assessments', '0001_initial'),
        ('accounts', '0032_user_assessment_status'),
    ]

    operations = [
        migrations.RunPython(seed_permissions, remove_permissions),
    ]
