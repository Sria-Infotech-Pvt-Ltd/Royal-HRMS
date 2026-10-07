"""
Phase 4 Task B.3/D.1 — backfill the new explicit Role attributes from
today's actual data, so the 4 hardcoded-role-name call sites just
switched to reading these attributes keep behaving EXACTLY as before
(Rule 3 — "access must not change"):

- is_full_access: every role that currently holds the 'settings.edit'
  permission (Task D.1's own rule — NOT just "the role literally named
  system_admin", since that's the actual authoritative behaviour
  core.permissions.has_perm() already grants full access by today).
- is_default_employee_role: the role literally named 'employee' (the
  exact two call sites being replaced only ever looked for that name).
- exclude_from_payroll: the role literally named 'system_admin' (the
  exact two payroll call sites being replaced only ever excluded that name).

Counts only are logged (no personal data) — verification output goes in
PHASE4_REPORT.md.
"""
from django.db import migrations


def backfill(apps, schema_editor):
    Role = apps.get_model('accounts', 'Role')
    Permission = apps.get_model('accounts', 'Permission')
    RolePermission = apps.get_model('accounts', 'RolePermission')

    settings_edit = Permission.objects.filter(codename='settings.edit').first()
    full_access_role_ids = set()
    if settings_edit is not None:
        full_access_role_ids = set(
            RolePermission.objects.filter(permission=settings_edit).values_list('role_id', flat=True)
        )
    if full_access_role_ids:
        Role.objects.filter(id__in=full_access_role_ids).update(is_full_access=True)

    employee_updated = Role.objects.filter(name='employee').update(is_default_employee_role=True)
    system_admin_updated = Role.objects.filter(name='system_admin').update(exclude_from_payroll=True)

    print(
        f'Phase 4 role-attribute backfill: is_full_access set on {len(full_access_role_ids)} role(s), '
        f'is_default_employee_role set on {employee_updated} role(s), '
        f'exclude_from_payroll set on {system_admin_updated} role(s).'
    )


def unbackfill(apps, schema_editor):
    Role = apps.get_model('accounts', 'Role')
    Role.objects.all().update(
        is_full_access=False, is_default_employee_role=False, exclude_from_payroll=False,
    )


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0180_phase4_role_permission_attributes'),
    ]

    operations = [
        migrations.RunPython(backfill, unbackfill),
    ]
