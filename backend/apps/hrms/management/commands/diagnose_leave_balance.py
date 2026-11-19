"""Why does this employee have no leave balance? Shows, for every active leave policy, whether they have a balance this year and, when not,
the plain reason (their branch, department, designation, gender or service period does not match the policy). With --allocate it
also gives them the balances they should have, the same way hiring does.

    python manage.py diagnose_leave_balance kavya@example.com
    python manage.py diagnose_leave_balance 10000042 --allocate

Read-only unless --allocate is given. Allocating never changes a balance that already exists: it only creates the missing ones.
"""
from __future__ import annotations

from datetime import date

from django.core.management.base import BaseCommand, CommandError
from django.db.models import Q

from apps.accounts.models import User
from apps.accounts.services_approval import resolve_employee_department_name
from apps.hrms.models import LeaveBalance, LeavePolicy
from apps.hrms.views.leave_shared import _allocate_leaves_for_employee, new_joiner_skip_reason


class Command(BaseCommand):
    help = 'Explain why an employee has (or has no) leave balance this year; --allocate creates the missing ones.'

    def add_arguments(self, parser):
        parser.add_argument('employee', help='The employee\'s email address or employee ID.')
        parser.add_argument('--allocate', action='store_true', help='Create the balances that are missing (existing ones are never changed).')

    def handle(self, *args, **options):
        key = options['employee'].strip()
        matches = list(User.objects.filter(Q(email__iexact=key) | Q(employee_id=key)).only('id', 'email', 'employee_id', 'is_active')[:2])
        if not matches:
            raise CommandError(f'No employee has the email or employee ID "{key}".')
        employee = User.objects.get(pk=matches[0].pk)
        year = date.today().year

        self.stdout.write(f'Employee {employee.employee_id}: branch "{employee.branch or ""}", department "{resolve_employee_department_name(employee) or ""}", '
                          f'designation "{employee.designation or ""}", joined {employee.date_of_joining}, active={employee.is_active}')
        if not employee.is_active:
            self.stdout.write(self.style.WARNING('This employee is not active, so they cannot apply for leave.'))

        have = {row.leave_type: row for row in LeaveBalance.objects.filter(employee=employee, year=year)}
        dept = resolve_employee_department_name(employee)
        missing = 0
        for policy in LeavePolicy.objects.filter(is_active=True).order_by('leave_type'):
            row = have.get(policy.leave_type)
            if row is not None:
                available = row.total_days + row.carried_forward - row.used_days
                self.stdout.write(f'  {policy.leave_type:<12} {year}: total {row.total_days}, carried {row.carried_forward}, used {row.used_days}  ->  {available} available')
                continue
            missing += 1
            reason = new_joiner_skip_reason(employee, policy, dept)
            if reason:
                self.stdout.write(self.style.WARNING(f'  {policy.leave_type:<12} {year}: NO balance. Why: {reason}'))
            else:
                self.stdout.write(self.style.ERROR(f'  {policy.leave_type:<12} {year}: NO balance, and nothing in the policy rules explains it (it should have been created at hiring).'))

        if not missing:
            self.stdout.write(self.style.SUCCESS('Every active policy already has a balance for this year.'))
        if options['allocate']:
            created = _allocate_leaves_for_employee(employee, employee.date_of_joining)
            self.stdout.write(self.style.SUCCESS(f'Allocated {created} missing balance(s).') if created else 'Nothing to allocate: no policy applies to them without a rule change.')
        elif missing:
            self.stdout.write('Run again with --allocate to create the balances that policies allow.')
