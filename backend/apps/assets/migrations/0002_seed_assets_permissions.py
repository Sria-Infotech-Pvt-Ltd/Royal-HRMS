from django.db import migrations

ASSET_PERMISSIONS = [
    ('assets', 'view',   'assets.view'),
    ('assets', 'create', 'assets.create'),
    ('assets', 'edit',   'assets.edit'),
    ('assets', 'delete', 'assets.delete'),
]

# Which roles get which codenames — mirrors accounts.0041's own
# departments/designations grant shape: full CRUD for hr_admin/system_admin,
# view-only for manager. Adjustable afterward via Settings -> Permissions.
ROLE_GRANTS = {
    'hr_admin':     [p[2] for p in ASSET_PERMISSIONS],  # full access
    'system_admin': [p[2] for p in ASSET_PERMISSIONS],  # full access
    'manager':      ['assets.view'],                    # read-only
}


def seed_forward(apps, schema_editor):
    Permission     = apps.get_model('accounts', 'Permission')
    Role           = apps.get_model('accounts', 'Role')
    RolePermission = apps.get_model('accounts', 'RolePermission')

    perm_map = {}
    for module, action, codename in ASSET_PERMISSIONS:
        perm, _ = Permission.objects.get_or_create(
            codename=codename,
            defaults={'module': module, 'action': action},
        )
        perm_map[codename] = perm

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
        codename__in=[p[2] for p in ASSET_PERMISSIONS]
    ).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('assets', '0001_initial'),
        ('accounts', '0099_smtpsettings_provider'),
    ]

    operations = [
        migrations.RunPython(seed_forward, seed_reverse),
    ]
