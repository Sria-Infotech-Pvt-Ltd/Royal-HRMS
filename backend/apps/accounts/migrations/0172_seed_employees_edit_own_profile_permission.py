"""
Add employees.edit_own_profile — gates whether a user may edit their own
profile details (MyProfileView.patch) and their own profile photo
(ProfilePhotoView). Granted to every existing role by default so current
behavior is unchanged; HR can then revoke it from a specific role (e.g.
employee) to lock down self-service editing for that role only. Does not
affect HR/admin editing someone ELSE's record (unrelated, already-gated
endpoints), and does not affect onboarding-step saving (a required,
HR-mandated one-time flow, not something a permission should be able to
block).
"""
from django.db import migrations

CODENAME = 'employees.edit_own_profile'


def seed_forward(apps, schema_editor):
    Role = apps.get_model('accounts', 'Role')
    Permission = apps.get_model('accounts', 'Permission')
    RolePermission = apps.get_model('accounts', 'RolePermission')

    permission, _ = Permission.objects.get_or_create(
        codename=CODENAME,
        defaults={'module': 'employees', 'action': 'edit_own_profile'},
    )
    for role in Role.objects.all():
        RolePermission.objects.get_or_create(role=role, permission=permission)


def seed_reverse(apps, schema_editor):
    Permission = apps.get_model('accounts', 'Permission')
    Permission.objects.filter(codename=CODENAME).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0171_employeeprofile_bank_change_requested_at_and_more'),
    ]

    operations = [
        migrations.RunPython(seed_forward, seed_reverse),
    ]
