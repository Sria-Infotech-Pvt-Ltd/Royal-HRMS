from django.db import migrations

DEPT_PERMISSIONS = [
    ('departments', 'view',   'departments.view'),
    ('departments', 'create', 'departments.create'),
    ('departments', 'edit',   'departments.edit'),
    ('departments', 'delete', 'departments.delete'),
]

DESIG_PERMISSIONS = [
    ('designations', 'view',   'designations.view'),
    ('designations', 'create', 'designations.create'),
    ('designations', 'edit',   'designations.edit'),
    ('designations', 'delete', 'designations.delete'),
]

ALL_NEW = DEPT_PERMISSIONS + DESIG_PERMISSIONS

# Which roles get which codenames
ROLE_GRANTS = {
    'hr_admin':     [p[2] for p in ALL_NEW],           # full access
    'system_admin': [p[2] for p in ALL_NEW],           # full access
    'manager':      ['departments.view', 'designations.view'],  # read-only
}


def seed_forward(apps, schema_editor):
    Permission    = apps.get_model('accounts', 'Permission')
    Role          = apps.get_model('accounts', 'Role')
    RolePermission = apps.get_model('accounts', 'RolePermission')

    # 1. Insert permission rows (idempotent)
    perm_map = {}
    for module, action, codename in ALL_NEW:
        perm, _ = Permission.objects.get_or_create(
            codename=codename,
            defaults={'module': module, 'action': action},
        )
        perm_map[codename] = perm

    # 2. Assign to roles
    for role_name, codenames in ROLE_GRANTS.items():
        try:
            role = Role.objects.get(name=role_name)
        except Role.DoesNotExist:
            continue
        for codename in codenames:
            RolePermission.objects.get_or_create(
                role=role,
                permission=perm_map[codename],
            )


def seed_reverse(apps, schema_editor):
    Permission = apps.get_model('accounts', 'Permission')
    Permission.objects.filter(
        codename__in=[p[2] for p in ALL_NEW]
    ).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0040_user_onboarding_rejected'),
    ]

    operations = [
        migrations.RunPython(seed_forward, seed_reverse),
    ]
