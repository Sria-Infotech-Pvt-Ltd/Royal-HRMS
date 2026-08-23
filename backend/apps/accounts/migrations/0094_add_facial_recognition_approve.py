from django.db import migrations

# facial_recognition.approve (gates the "Face ID Registrations" review page)
# was granted to system_admin only — HR Admin and Branch Admin had no way to
# review/approve an employee's face ID registration at all. Reviewing an
# employee's own registration is squarely an HR/branch-management task, not
# a superuser-only one, so this extends it to both roles.
TARGET_ROLES = ['hr_admin', 'branch_admin']
CODENAME = 'facial_recognition.approve'


def apply_changes(apps, schema_editor):
    Role = apps.get_model('accounts', 'Role')
    Permission = apps.get_model('accounts', 'Permission')
    RolePermission = apps.get_model('accounts', 'RolePermission')

    permission = Permission.objects.filter(codename=CODENAME).first()
    if not permission:
        return
    for role_name in TARGET_ROLES:
        role = Role.objects.filter(name=role_name).first()
        if role:
            RolePermission.objects.get_or_create(role=role, permission=permission)


def revert_changes(apps, schema_editor):
    Role = apps.get_model('accounts', 'Role')
    RolePermission = apps.get_model('accounts', 'RolePermission')

    for role_name in TARGET_ROLES:
        role = Role.objects.filter(name=role_name).first()
        if role:
            RolePermission.objects.filter(role=role, permission__codename=CODENAME).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0093_branch_admin_assessments_no_branches_mgmt'),
    ]

    operations = [
        migrations.RunPython(apply_changes, revert_changes),
    ]
