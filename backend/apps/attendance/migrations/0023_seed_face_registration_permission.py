from django.db import migrations


def seed_face_registration_permission(apps, schema_editor):
    Permission     = apps.get_model('accounts', 'Permission')
    Role           = apps.get_model('accounts', 'Role')
    RolePermission = apps.get_model('accounts', 'RolePermission')

    approve_perm, _ = Permission.objects.get_or_create(
        codename='facial_recognition.approve',
        defaults={'module': 'facial_recognition', 'action': 'approve'},
    )

    for role_name in ('hr', 'system_admin'):
        try:
            role = Role.objects.get(name=role_name)
            RolePermission.objects.get_or_create(role=role, permission=approve_perm)
        except Role.DoesNotExist:
            pass


def reverse_migration(apps, schema_editor):
    Permission = apps.get_model('accounts', 'Permission')
    Permission.objects.filter(codename='facial_recognition.approve').delete()


class Migration(migrations.Migration):

    dependencies = [
        ('attendance', '0022_face_registration_request'),
        ('accounts',   '0055_phase4_index_review'),
    ]

    operations = [
        migrations.RunPython(seed_face_registration_permission, reverse_migration),
    ]
