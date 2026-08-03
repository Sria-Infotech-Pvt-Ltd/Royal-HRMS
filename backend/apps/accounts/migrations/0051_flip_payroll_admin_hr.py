from django.db import migrations

# Payroll execution moves to Branch Admin (the person running the branch),
# off HR (routine people-ops). HR keeps payroll.view/export/view_own —
# read access only, same as Branch Admin now loses on the reverse side.
PAYROLL_RUN_CODENAMES = ['payroll.create', 'payroll.edit', 'payroll.delete']


def forward(apps, schema_editor):
    Role = apps.get_model('accounts', 'Role')
    Permission = apps.get_model('accounts', 'Permission')
    RolePermission = apps.get_model('accounts', 'RolePermission')

    branch_admin = Role.objects.filter(name='branch_admin').first()
    hr = Role.objects.filter(name='hr').first()

    if branch_admin:
        for codename in PAYROLL_RUN_CODENAMES:
            permission = Permission.objects.filter(codename=codename).first()
            if permission:
                RolePermission.objects.get_or_create(role=branch_admin, permission=permission)

    if hr:
        RolePermission.objects.filter(
            role=hr, permission__codename__in=PAYROLL_RUN_CODENAMES,
        ).delete()


def reverse(apps, schema_editor):
    Role = apps.get_model('accounts', 'Role')
    Permission = apps.get_model('accounts', 'Permission')
    RolePermission = apps.get_model('accounts', 'RolePermission')

    branch_admin = Role.objects.filter(name='branch_admin').first()
    hr = Role.objects.filter(name='hr').first()

    if branch_admin:
        RolePermission.objects.filter(
            role=branch_admin, permission__codename__in=PAYROLL_RUN_CODENAMES,
        ).delete()

    if hr:
        for codename in PAYROLL_RUN_CODENAMES:
            permission = Permission.objects.filter(codename=codename).first()
            if permission:
                RolePermission.objects.get_or_create(role=hr, permission=permission)


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0050_seed_branch_admin_role'),
    ]

    operations = [
        migrations.RunPython(forward, reverse),
    ]
