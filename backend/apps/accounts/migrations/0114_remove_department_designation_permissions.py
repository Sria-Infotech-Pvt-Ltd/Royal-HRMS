from django.db import migrations

_CODENAMES = [
    'departments.view', 'departments.create', 'departments.edit', 'departments.delete',
    'designations.view', 'designations.create', 'designations.edit', 'designations.delete',
]


def remove_permissions(apps, schema_editor):
    """The Department/Designation CRUD screens these permissions gated are
    gone (Stage 6) — drop the seeded rows; RolePermission grants pointing
    at them cascade automatically (on_delete=CASCADE)."""
    Permission = apps.get_model('accounts', 'Permission')
    Permission.objects.filter(codename__in=_CODENAMES).delete()


def noop_reverse(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0113_backfill_orgunit_is_department_level"),
    ]

    operations = [
        migrations.RunPython(remove_permissions, noop_reverse),
    ]
