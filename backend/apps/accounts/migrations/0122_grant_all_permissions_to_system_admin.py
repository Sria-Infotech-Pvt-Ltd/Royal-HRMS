"""
Grant every current permission to system_admin.

Per 0002_seed_roles_permissions, system_admin was deliberately seeded with
only a narrow subset (settings/audit/reports/employee-CRUD, view-only
elsewhere) — hr_admin, not system_admin, was the role built to hold every
permission. Real full ("can do literally everything") access was meant to
come from the separate Django is_superuser flag, not from the system_admin
role's own grants — confirmed live: the one system_admin account in this
database only works fully because it also happens to have is_superuser=True
set, not because of anything this role actually grants.

That's a mismatch with how "System Admin" reads to anyone creating a new
account through the normal role-assignment UI (which has no way to also set
is_superuser) — they'd reasonably expect the role name to mean full access.
This migration makes it actually true: grants every permission that exists
today to system_admin, the same way hr_admin already has everything.

Deliberately NOT reversed to remove permissions — reverting this migration
should not silently downgrade a role occupied by real, in-use accounts.
"""
from django.db import migrations


def grant_all(apps, schema_editor):
    Role = apps.get_model('accounts', 'Role')
    Permission = apps.get_model('accounts', 'Permission')
    RolePermission = apps.get_model('accounts', 'RolePermission')

    role = Role.objects.filter(name='system_admin').first()
    if not role:
        return
    for permission in Permission.objects.all():
        RolePermission.objects.get_or_create(role=role, permission=permission)


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0121_encrypt_company_pii'),
    ]

    operations = [
        migrations.RunPython(grant_all, migrations.RunPython.noop),
    ]
