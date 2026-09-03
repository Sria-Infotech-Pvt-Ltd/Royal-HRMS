from django.db import migrations

# Backfill for two stacked bugs that both meant hr_admin/branch_admin never
# actually got facial_recognition.approve, despite two earlier migrations
# each having *intended* to grant it:
#
# 1. attendance.0023_seed_face_registration_permission tried to grant it to
#    a role named 'hr' — there is no such role (the real name is
#    'hr_admin') — so that half of it silently no-op'd via its own
#    try/except Role.DoesNotExist.
# 2. accounts.0094_add_facial_recognition_approve tried to grant it to
#    'hr_admin' and 'branch_admin', but only declared a dependency on an
#    earlier *accounts* migration, not on attendance.0023 (the migration
#    that actually creates the Permission row) — so on a fresh install
#    where Django's migration graph happened to run 0094 first, the
#    Permission row didn't exist yet and 0094's own `if not permission:
#    return` guard silently no-op'd too.
#
# Both migrations already ran in every existing environment and are not
# re-run by fixing them retroactively (and per policy, an already-shipped
# migration is never edited in place) — this is a new, idempotent
# migration that depends on attendance.0023 explicitly, so the Permission
# row is guaranteed to exist by the time this runs on any environment,
# including a brand new one applying every migration from scratch.
TARGET_ROLES = ['hr_admin', 'branch_admin', 'system_admin']
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
    # No-op reverse — accounts.0094's own revert already removes this grant
    # for hr_admin/branch_admin, and system_admin having it predates all of
    # this, so there's nothing this migration should undo on its own.
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0118_widen_company_director_din'),
        ('attendance', '0023_seed_face_registration_permission'),
    ]

    operations = [
        migrations.RunPython(apply_changes, revert_changes),
    ]
