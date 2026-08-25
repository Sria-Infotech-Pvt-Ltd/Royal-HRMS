from django.db import migrations

# Same fragile-ordering bug as 0095_ensure_facial_recognition_approve_defaults,
# for the same reason: two earlier migrations (0052_seed_branch_admin_role and
# 0093_branch_admin_assessments_no_branches_mgmt) try to grant branch_admin
# the assessments.* permissions, but neither has an explicit dependency on
# assessments.0002_seed_permissions — the migration that actually creates
# those Permission rows. On a fresh company, whichever happens to run first
# in Django's cross-app migration order decides whether the grant silently
# no-ops (both were confirmed, via applied timestamps on a real fresh
# provision, to have run before assessments.0002 — so both should have
# no-opped). hr_admin/system_admin are unaffected — assessments.0002 grants
# to those two itself, in the same migration that creates the permissions,
# so there's no cross-app ordering risk for them. This migration explicitly
# depends on assessments.0002 and unconditionally (re-)grants branch_admin
# all four assessments permissions.
ASSESSMENT_CODENAMES = [
    'assessments.view',
    'assessments.create',
    'assessments.edit',
    'assessments.delete',
]


def apply_changes(apps, schema_editor):
    Role = apps.get_model('accounts', 'Role')
    Permission = apps.get_model('accounts', 'Permission')
    RolePermission = apps.get_model('accounts', 'RolePermission')

    branch_admin = Role.objects.filter(name='branch_admin').first()
    if not branch_admin:
        return
    for codename in ASSESSMENT_CODENAMES:
        permission = Permission.objects.filter(codename=codename).first()
        if permission:
            RolePermission.objects.get_or_create(role=branch_admin, permission=permission)


def revert_changes(apps, schema_editor):
    # No-op: 0093's own revert_changes already removes these grants from
    # branch_admin. Removing them again here would just be redundant.
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0095_ensure_facial_recognition_approve_defaults'),
        ('assessments', '0002_seed_permissions'),
    ]

    operations = [
        migrations.RunPython(apply_changes, revert_changes),
    ]
