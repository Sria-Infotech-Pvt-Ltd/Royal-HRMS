"""
Seeds a new org_structure.backdate permission — required to edit or delete
a PAST or CURRENT placement (org_structure.edit alone only covers creating
new placements and cancelling a future/scheduled one). Tenure, gratuity
eligibility, and payroll all depend on placement dates, so touching
history needs its own, narrower permission plus an audit trail, not a free
edit under the general edit permission.

Same "piggyback on an existing, currently-real permission grant" pattern
0101_seed_org_structure_permissions_and_jobs.py already used for
org_structure.{create,edit,delete} — granted here to whichever roles
currently hold org_structure.edit, not hardcoded role names.
"""
from django.db import migrations

BACKDATE_PERMISSION = ('org_structure', 'backdate', 'org_structure.backdate')


def seed_forward(apps, schema_editor):
    Permission     = apps.get_model('accounts', 'Permission')
    RolePermission = apps.get_model('accounts', 'RolePermission')

    module, action, codename = BACKDATE_PERMISSION
    perm, _ = Permission.objects.get_or_create(
        codename=codename, defaults={'module': module, 'action': action},
    )

    edit_role_ids = set(
        RolePermission.objects
        .filter(permission__codename='org_structure.edit')
        .values_list('role_id', flat=True)
    )
    for role_id in edit_role_ids:
        RolePermission.objects.get_or_create(role_id=role_id, permission=perm)


def seed_reverse(apps, schema_editor):
    Permission = apps.get_model('accounts', 'Permission')
    Permission.objects.filter(codename=BACKDATE_PERMISSION[2]).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0107_remove_position_holder'),
    ]

    operations = [
        migrations.RunPython(seed_forward, seed_reverse),
    ]
