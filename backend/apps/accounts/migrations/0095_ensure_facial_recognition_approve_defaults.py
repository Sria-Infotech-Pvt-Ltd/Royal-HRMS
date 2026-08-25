from django.db import migrations

# Belt-and-braces follow-up to 0094_add_facial_recognition_approve: that
# migration only grants facial_recognition.approve if the permission row
# already exists, but has no explicit dependency on
# attendance.0023_seed_face_registration_permission (the migration that
# actually creates it) — so on a fresh company, whichever of the two
# happens to run first in Django's cross-app migration order decides
# whether the grant silently no-ops. This migration explicitly depends on
# both, get_or_creates the permission itself as a safety net, and
# unconditionally ensures all three roles that should default to holding
# it — system_admin, hr_admin, branch_admin — actually do. Also fixes
# 0023's role-name bug: it grants to a role literally named 'hr', which
# has never existed (the role has always been 'hr_admin' since
# accounts.0002_seed_roles_permissions).
TARGET_ROLES = ['system_admin', 'hr_admin', 'branch_admin']
CODENAME = 'facial_recognition.approve'


def apply_changes(apps, schema_editor):
    Role = apps.get_model('accounts', 'Role')
    Permission = apps.get_model('accounts', 'Permission')
    RolePermission = apps.get_model('accounts', 'RolePermission')

    permission, _ = Permission.objects.get_or_create(
        codename=CODENAME,
        defaults={'module': 'facial_recognition', 'action': 'approve'},
    )
    for role_name in TARGET_ROLES:
        role = Role.objects.filter(name=role_name).first()
        if role:
            RolePermission.objects.get_or_create(role=role, permission=permission)


def revert_changes(apps, schema_editor):
    # Reverts only the branch_admin grant this migration is actually
    # responsible for adding on top of 0094 — hr_admin/system_admin grants
    # are 0094's own responsibility and stay under its revert_changes.
    Role = apps.get_model('accounts', 'Role')
    RolePermission = apps.get_model('accounts', 'RolePermission')

    branch_admin = Role.objects.filter(name='branch_admin').first()
    if branch_admin:
        RolePermission.objects.filter(role=branch_admin, permission__codename=CODENAME).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0094_add_facial_recognition_approve'),
        ('attendance', '0023_seed_face_registration_permission'),
    ]

    operations = [
        migrations.RunPython(apply_changes, revert_changes),
    ]
