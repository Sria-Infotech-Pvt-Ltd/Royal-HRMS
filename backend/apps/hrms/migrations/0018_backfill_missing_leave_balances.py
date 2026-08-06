"""
Backfill LeaveBalance rows for active employees who have none for the
current year.

apps/hrms/views/leave.py's _allocate_leaves_for_employee() only runs when an
employee is created through EmployeeListCreateView.post() (accounts/views.py)
or candidate->employee conversion. accounts/migrations/0003_seed_demo_users.py
inserts User rows directly (as every seed migration does) and — for
system_admin specifically — EmployeeListCreateView.post() explicitly refuses
to create that role at all ("system_admin cannot be assigned via employee
creation"), so a system_admin account can never go through the normal
allocation path. The result: LeaveRequestListCreateView.post() rejects their
apply-leave attempts with "No leave balance found ... Contact HR." even
though nothing about their role should block them from taking leave.

This replicates _allocate_leaves_for_employee()'s pro-rata eligibility rules
(idempotent via get_or_create) for any active, non-portal employee with zero
LeaveBalance rows this year — covering system_admin now and any other
account that reached this state outside the normal creation flow.
"""
from decimal import Decimal

from django.db import migrations
from django.utils import timezone


def seed_forward(apps, schema_editor):
    User = apps.get_model('accounts', 'User')
    EmployeeProfile = apps.get_model('accounts', 'EmployeeProfile')
    LeavePolicy = apps.get_model('hrms', 'LeavePolicy')
    LeaveBalance = apps.get_model('hrms', 'LeaveBalance')

    today = timezone.localdate()
    year = today.year

    policies = list(LeavePolicy.objects.filter(is_active=True))
    if not policies:
        return

    employees = User.objects.filter(is_active=True).exclude(employee_id='')
    created_total = 0

    for employee in employees:
        if LeaveBalance.objects.filter(employee=employee, year=year).exists():
            continue

        joining_date = employee.date_of_joining or today
        remaining_months = 13 - joining_date.month

        profile = EmployeeProfile.objects.filter(user=employee).first()
        emp_gender = (profile.gender or 'all') if profile else 'all'

        for policy in policies:
            if policy.minimum_service_period > 0:
                continue
            if policy.applicable_branches and (
                not employee.branch or employee.branch not in policy.applicable_branches
            ):
                continue
            if policy.applicable_departments and (
                not employee.department or employee.department not in policy.applicable_departments
            ):
                continue
            if policy.applicable_designations and (
                not employee.designation or employee.designation not in policy.applicable_designations
            ):
                continue
            if policy.applicable_gender not in ('', 'all') and emp_gender != policy.applicable_gender:
                continue

            raw = float(policy.annual_days) * remaining_months / 12
            prorata = Decimal(str(round(raw * 2) / 2))

            _, created = LeaveBalance.objects.get_or_create(
                employee=employee,
                leave_type=policy.leave_type,
                year=year,
                defaults={'total_days': prorata, 'carried_forward': Decimal('0')},
            )
            if created:
                created_total += 1


def seed_reverse(apps, schema_editor):
    # No-op: this is a backfill for accounts that were missing balances
    # through no fault of their own — reversing would re-break them.
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('hrms', '0017_seed_expense_email_templates'),
        ('accounts', '0053_grant_payroll_view_own_missing_roles'),
    ]

    operations = [
        migrations.RunPython(seed_forward, seed_reverse),
    ]
