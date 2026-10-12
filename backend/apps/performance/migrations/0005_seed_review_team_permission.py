from django.db import migrations

# performance.review_team - lets a Reporting Manager open the Performance
# workspace to assess their direct reports' appraisals. It only controls UI
# access (nav + route); the API itself authorises each action by "is this
# the employee's reporting manager" (or performance.manage_cycles for HR).
GRANTED_TO = ('manager',)


def seed(apps, schema_editor):
    Permission = apps.get_model('accounts', 'Permission')
    Role = apps.get_model('accounts', 'Role')
    RolePermission = apps.get_model('accounts', 'RolePermission')

    permission, _ = Permission.objects.get_or_create(
        codename='performance.review_team',
        defaults={'module': 'performance', 'action': 'review_team'},
    )
    for role_name in GRANTED_TO:
        role = Role.objects.filter(name=role_name).first()
        if role:
            RolePermission.objects.get_or_create(role=role, permission=permission)


def unseed(apps, schema_editor):
    apps.get_model('accounts', 'Permission').objects.filter(codename='performance.review_team').delete()


class Migration(migrations.Migration):

    dependencies = [
        ('performance', '0004_appraisal_workflow_fields'),
        ('accounts', '0181_seed_employees_raise_action_permission'),
    ]

    operations = [
        migrations.RunPython(seed, unseed),
    ]
