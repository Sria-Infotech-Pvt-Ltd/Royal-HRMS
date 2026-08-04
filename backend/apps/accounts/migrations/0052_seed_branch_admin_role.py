from django.db import migrations

# Every operational module gets full View+CRUD+Approve — Branch Admin is meant
# to run their branch end-to-end, unlike HR (scoped to specifically assigned
# employees) or a manager (scoped to direct reports).
#
# Deliberately withheld:
#   - settings.edit   — wired throughout the codebase as an implicit "bypass
#                        all branch scoping, treat as global admin" flag (see
#                        _has_perm('settings.edit') across leave/expenses/
#                        attendance/recruitment/accounts). Granting it here
#                        would make Branch Admin org-wide, not branch-scoped.
#   - branches.create/edit/delete — branch record management isn't yet scoped
#                        to "only your own branch" in code (any holder can
#                        currently edit any branch), so this is deferred until
#                        that scoping is built. branches.view only for now.
#   - payroll.create/edit/delete — running payroll is a money-moving action;
#                        default to view/export only. Revisit if Branch Admin
#                        should actually execute payroll runs.
BRANCH_ADMIN_CODENAMES = [
    'employees.view', 'employees.create', 'employees.edit', 'employees.delete',
    'employees.approve', 'employees.export',
    'leave.view', 'leave.create', 'leave.edit', 'leave.delete', 'leave.approve',
    'expenses.view', 'expenses.create', 'expenses.edit', 'expenses.delete', 'expenses.approve',
    'attendance.view', 'attendance.create', 'attendance.edit', 'attendance.delete', 'attendance.export',
    'recruitment.view', 'recruitment.create', 'recruitment.edit', 'recruitment.delete', 'recruitment.approve',
    'documents.view', 'documents.create', 'documents.edit', 'documents.delete',
    'onboarding.approve',
    'referrals.view', 'referrals.create',
    'announcements.view', 'announcements.create', 'announcements.edit', 'announcements.delete',
    'departments.view', 'departments.create', 'departments.edit', 'departments.delete',
    'designations.view', 'designations.create', 'designations.edit', 'designations.delete',
    'assessments.view', 'assessments.create', 'assessments.edit', 'assessments.delete',
    'reports.view', 'reports.export',
    'audit.view',
    'payroll.view', 'payroll.export',
    'branches.view',
    'settings.view',
]


def seed_forward(apps, schema_editor):
    Role = apps.get_model('accounts', 'Role')
    Permission = apps.get_model('accounts', 'Permission')
    RolePermission = apps.get_model('accounts', 'RolePermission')

    role, _ = Role.objects.get_or_create(
        name='branch_admin',
        defaults={
            'display_name': 'Branch Admin',
            'is_active': True,
            'can_manage_team': False,
            'can_manage_branch': True,
        },
    )
    # get_or_create above only sets can_manage_branch on first creation — force
    # it true on re-run too, in case the role already existed from a partial apply.
    if not role.can_manage_branch:
        role.can_manage_branch = True
        role.save(update_fields=['can_manage_branch'])

    for codename in BRANCH_ADMIN_CODENAMES:
        try:
            permission = Permission.objects.get(codename=codename)
        except Permission.DoesNotExist:
            continue
        RolePermission.objects.get_or_create(role=role, permission=permission)


def seed_reverse(apps, schema_editor):
    Role = apps.get_model('accounts', 'Role')
    Role.objects.filter(name='branch_admin').delete()


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0051_role_can_manage_branch'),
    ]

    operations = [
        migrations.RunPython(seed_forward, seed_reverse),
    ]
