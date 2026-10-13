from django.db import migrations

# employees.raise_action — lets a Reporting Manager RAISE a Promotion / Org
# assignment / Pay change / Confirmation for a direct report. It never applies
# anything by itself: the request waits for the approvers on its route (see
# apps.accounts.services_personnel_actions). Roles that already hold
# employees.edit apply these actions directly and do not need it.
GRANTED_TO = ('manager',)


def seed(apps, schema_editor):
    Permission     = apps.get_model('accounts', 'Permission')
    Role           = apps.get_model('accounts', 'Role')
    RolePermission = apps.get_model('accounts', 'RolePermission')

    permission, _ = Permission.objects.get_or_create(
        codename='employees.raise_action',
        defaults={'module': 'employees', 'action': 'raise_action'},
    )
    for role_name in GRANTED_TO:
        role = Role.objects.filter(name=role_name).first()
        if role:
            RolePermission.objects.get_or_create(role=role, permission=permission)


def unseed(apps, schema_editor):
    apps.get_model('accounts', 'Permission').objects.filter(codename='employees.raise_action').delete()


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0180_personnel_action_request'),
    ]

    operations = [
        migrations.RunPython(seed, unseed),
    ]
