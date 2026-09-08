from django.db import migrations


def seed_email_log_permissions(apps, schema_editor):
    Permission     = apps.get_model('accounts', 'Permission')
    Role           = apps.get_model('accounts', 'Role')
    RolePermission = apps.get_model('accounts', 'RolePermission')

    view_perm, _ = Permission.objects.get_or_create(
        codename='email_logs.view',
        defaults={'module': 'email_logs', 'action': 'view'},
    )
    resend_perm, _ = Permission.objects.get_or_create(
        codename='email_logs.resend',
        defaults={'module': 'email_logs', 'action': 'resend'},
    )

    # Same footprint as audit.view today — read-only visibility into the
    # system-wide log for every ops-tier role.
    for role_name in ('hr_admin', 'system_admin', 'branch_admin'):
        try:
            role = Role.objects.get(name=role_name)
            RolePermission.objects.get_or_create(role=role, permission=view_perm)
        except Role.DoesNotExist:
            pass

    # Deliberately NOT branch_admin — EmailLog has no branch scoping, so a
    # branch_admin holding resend could resend any email company-wide, not
    # just their own branch's.
    for role_name in ('hr_admin', 'system_admin'):
        try:
            role = Role.objects.get(name=role_name)
            RolePermission.objects.get_or_create(role=role, permission=resend_perm)
        except Role.DoesNotExist:
            pass


def reverse_migration(apps, schema_editor):
    Permission = apps.get_model('accounts', 'Permission')
    Permission.objects.filter(codename__in=['email_logs.view', 'email_logs.resend']).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0124_emaillog'),
    ]

    operations = [
        migrations.RunPython(
            seed_email_log_permissions,
            reverse_migration,
        ),
    ]
