from django.db import migrations

# leave.record — lets HR RECORD leave on an employee's behalf from the Employee Directory's Leave dialog.
# Unlike an employee's own application there is no approval step: the leave is final, the balance is
# deducted and attendance is marked on-leave at once (apps.hrms.views.leave_record). So it is granted only
# to the roles that administer people, and the view also refuses to record leave for yourself.
GRANTED_TO = ('hr_admin', 'system_admin', 'branch_admin')


def seed(apps, schema_editor):
    Permission     = apps.get_model('accounts', 'Permission')
    Role           = apps.get_model('accounts', 'Role')
    RolePermission = apps.get_model('accounts', 'RolePermission')

    permission, _ = Permission.objects.get_or_create(
        codename='leave.record',
        defaults={'module': 'leave', 'action': 'record'},
    )
    for role_name in GRANTED_TO:
        role = Role.objects.filter(name=role_name).first()
        if role:
            RolePermission.objects.get_or_create(role=role, permission=permission)


def unseed(apps, schema_editor):
    apps.get_model('accounts', 'Permission').objects.filter(codename='leave.record').delete()


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0182_revoke_reset_password_from_employee_role'),
    ]

    operations = [
        migrations.RunPython(seed, unseed),
    ]
