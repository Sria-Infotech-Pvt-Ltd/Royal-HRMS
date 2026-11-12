"""
Training & Learning permissions, granted to the existing admin roles only.
Ordinary employees get none — My Learning needs no permission (own assignments).
Other roles (e.g. managers) receive them only if an admin grants them.
"""
from django.db import migrations

PERMISSIONS = [
    ('training', 'view',               'training.view'),
    ('training', 'create',             'training.create'),
    ('training', 'edit',               'training.edit'),
    ('training', 'delete',             'training.delete'),
    ('training', 'assign',             'training.assign'),
    ('training', 'view_all_progress',  'training.view_all_progress'),
    ('training', 'manage_assessments', 'training.manage_assessments'),
    ('training', 'view_reports',       'training.view_reports'),
]

ROLE_GRANTS = {
    'system_admin': [c for _, _, c in PERMISSIONS],
    'hr_admin':     [c for _, _, c in PERMISSIONS],
    # Branch admins run their own branch: view, assign and track — scoped to
    # their branch by the API — but don't build the company course catalogue.
    'branch_admin': ['training.view', 'training.assign', 'training.view_all_progress', 'training.view_reports'],
}


def seed(apps, schema_editor):
    Permission = apps.get_model('accounts', 'Permission')
    Role = apps.get_model('accounts', 'Role')
    RolePermission = apps.get_model('accounts', 'RolePermission')
    perms = {}
    for module, action, codename in PERMISSIONS:
        perms[codename], _ = Permission.objects.get_or_create(codename=codename,
                                                              defaults={'module': module, 'action': action})
    for role_name, codes in ROLE_GRANTS.items():
        role = Role.objects.filter(name=role_name).first()
        if role is None:
            continue
        for code in codes:
            RolePermission.objects.get_or_create(role=role, permission=perms[code])


def unseed(apps, schema_editor):
    Permission = apps.get_model('accounts', 'Permission')
    Permission.objects.filter(module='training').delete()


class Migration(migrations.Migration):

    dependencies = [
        ('training', '0001_initial'),
        ('accounts', '0103_employeecodesettings_id_format'),
    ]

    operations = [migrations.RunPython(seed, unseed)]
