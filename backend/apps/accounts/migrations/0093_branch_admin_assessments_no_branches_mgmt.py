from django.db import migrations

# Two related default-role corrections, requested together:
#  1. Branch Admin was missing the Assessments module entirely (no view/
#     create/edit/delete) even though HR Admin has full access — an
#     oversight, not a deliberate restriction.
#  2. Branch Admin and HR Admin can both currently create/edit/delete the
#     company's Branch records — a company-wide structural action that
#     should be System Admin only. "Branch Admin" is scoped to managing
#     people/operations within their own assigned branch (via
#     can_manage_branch), not to administering the list of branches itself.
ASSESSMENT_CODENAMES = [
    'assessments.view',
    'assessments.create',
    'assessments.edit',
    'assessments.delete',
]

BRANCH_MGMT_CODENAMES = [
    'branches.view',
    'branches.create',
    'branches.edit',
    'branches.delete',
]


def apply_changes(apps, schema_editor):
    Role = apps.get_model('accounts', 'Role')
    Permission = apps.get_model('accounts', 'Permission')
    RolePermission = apps.get_model('accounts', 'RolePermission')

    branch_admin = Role.objects.filter(name='branch_admin').first()
    hr_admin = Role.objects.filter(name='hr_admin').first()

    if branch_admin:
        for codename in ASSESSMENT_CODENAMES:
            permission = Permission.objects.filter(codename=codename).first()
            if permission:
                RolePermission.objects.get_or_create(role=branch_admin, permission=permission)
        RolePermission.objects.filter(
            role=branch_admin, permission__codename__in=BRANCH_MGMT_CODENAMES,
        ).delete()

    if hr_admin:
        for codename in ASSESSMENT_CODENAMES:
            permission = Permission.objects.filter(codename=codename).first()
            if permission:
                RolePermission.objects.get_or_create(role=hr_admin, permission=permission)
        RolePermission.objects.filter(
            role=hr_admin, permission__codename__in=BRANCH_MGMT_CODENAMES,
        ).delete()


def revert_changes(apps, schema_editor):
    Role = apps.get_model('accounts', 'Role')
    Permission = apps.get_model('accounts', 'Permission')
    RolePermission = apps.get_model('accounts', 'RolePermission')

    branch_admin = Role.objects.filter(name='branch_admin').first()
    hr_admin = Role.objects.filter(name='hr_admin').first()

    if branch_admin:
        RolePermission.objects.filter(
            role=branch_admin, permission__codename__in=ASSESSMENT_CODENAMES,
        ).delete()
        permission = Permission.objects.filter(codename='branches.view').first()
        if permission:
            RolePermission.objects.get_or_create(role=branch_admin, permission=permission)

    if hr_admin:
        RolePermission.objects.filter(
            role=hr_admin, permission__codename__in=ASSESSMENT_CODENAMES,
        ).delete()
        for codename in BRANCH_MGMT_CODENAMES:
            permission = Permission.objects.filter(codename=codename).first()
            if permission:
                RolePermission.objects.get_or_create(role=hr_admin, permission=permission)


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0092_remove_manager_recruitment_and_payroll_perms'),
    ]

    operations = [
        migrations.RunPython(apply_changes, revert_changes),
    ]
