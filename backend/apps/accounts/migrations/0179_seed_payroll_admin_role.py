from django.db import migrations

# Payroll Administrator — a dedicated role, deliberately NOT a variant of
# hr_admin/branch_admin, so payroll execution stays separated from people
# administration (maker-checker / segregation of duties). The same split is
# used by Keka (Payroll Admin is the only role that can run payroll), Zoho
# Payroll (payroll staff get read-only employee data) and Workday (payroll
# partner groups are separate from HR partner groups).
#
# GRANTED
#   - payroll.view / create / edit / export : run pay cycles, maintain salary
#       structures and per-employee pay, process payslips, ECR/bank files.
#   - employees.view + employees.view_sensitive + employees.export : read-only
#       access to the employee master (pay, PAN/Aadhaar/bank — every reveal is
#       audit-logged by EmployeeRevealSensitiveView).
#   - tax_declarations.approve : payroll reviews employees' tax declarations
#       (the ESS Tax tab routes submissions to "Payroll Operations").
#   - attendance.view/export, leave.view, expenses.view : read-only inputs
#       to the pay run (LOP days, reimbursements) — payroll must be able to
#       see them, not decide them.
#   - reports.view/export, documents.view : payroll reports and payslip docs.
#   - Employee self-service baseline (a payroll admin is also an employee):
#       own leave/expenses/documents/referrals/profile, org chart, announcements.
#
# WITHHELD (on purpose)
#   - employees.create/edit/delete/approve/confirm/reset_password,
#     onboarding.* : changing who is employed, or their master data, is HR's
#       job — a payroll admin who can also add employees can create ghost
#       employees and pay them.
#   - payroll.delete : destructive; stays with branch_admin / system_admin.
#   - leave.approve / expenses.approve / separation.approve : approving the
#       inputs that payroll then pays would remove the second pair of eyes.
#   - settings.* , audit.view : org-wide config / log review belong to a
#       party independent of payroll.
PAYROLL_ADMIN_CODENAMES = [
    # payroll execution
    'payroll.view', 'payroll.create', 'payroll.edit', 'payroll.export', 'payroll.view_own',
    'tax_declarations.approve',
    # read-only employee master
    'employees.view', 'employees.view_sensitive', 'employees.export',
    # read-only pay-run inputs
    'attendance.view', 'attendance.export', 'leave.view', 'expenses.view',
    # reporting
    'reports.view', 'reports.export', 'documents.view',
    # employee self-service baseline
    'employees.edit_own_profile', 'leave.create', 'expenses.create', 'documents.create',
    'referrals.view', 'referrals.create', 'wfh.view', 'org_chart.view',
    'announcements.view', 'assessments.view',
]


def seed_forward(apps, schema_editor):
    Role = apps.get_model('accounts', 'Role')
    Permission = apps.get_model('accounts', 'Permission')
    RolePermission = apps.get_model('accounts', 'RolePermission')

    role, _ = Role.objects.get_or_create(
        name='payroll_admin',
        defaults={
            'display_name': 'Payroll Admin',
            'is_active': True,
            'can_manage_team': False,
            'can_manage_branch': False,
            'is_system_role': True,
        },
    )
    for codename in PAYROLL_ADMIN_CODENAMES:
        permission = Permission.objects.filter(codename=codename).first()
        if permission is None:
            continue
        RolePermission.objects.get_or_create(role=role, permission=permission)


def seed_reverse(apps, schema_editor):
    Role = apps.get_model('accounts', 'Role')
    # Users on this role fall back to no role (FK is SET_NULL) rather than
    # being deleted — reversing the migration never removes an employee.
    Role.objects.filter(name='payroll_admin').delete()


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0178_add_external_api_key'),
    ]

    operations = [
        migrations.RunPython(seed_forward, seed_reverse),
    ]
