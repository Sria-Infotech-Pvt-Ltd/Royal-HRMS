"""Payroll readiness: the ONE definition of "an employee is ready for payroll", used by Salary Setup, the Payroll
dashboard and the HR dashboard, so their numbers can never disagree.

An active employee is PAYROLL READY only when ALL of these hold:

  1. SALARY RECORD  - an active EmployeeSalaryConfig with annual_ctc > 0 whose effective date is today or earlier.
                      (A record that exists but starts in the future is "scheduled": it counts as configured, it is not
                      missing, but the employee is not payroll ready until it takes effect.)
  2. SALARY STRUCTURE - one resolves: the record's own structure, else the Company Code's structure, else the company
                      default structure (all of them active).
  3. BANK DETAILS   - account number AND IFSC code on the employee profile.

The salary record is the same record the hire wizard creates ("Set at hire") and the Basic pay dialog edits; nothing
else decides whether someone has a salary.
"""
from __future__ import annotations

import datetime
from dataclasses import dataclass, field

from django.contrib.auth import get_user_model
from django.db.models import Q
from django.utils import timezone

from apps.accounts.services_headcount import current_workforce
from apps.payroll.models import BranchPayrollConfig, EmployeeSalaryConfig, SalaryStructure

User = get_user_model()

PAYROLL_READY_REQUIREMENTS = (
    'An active salary record with annual CTC above 0, effective today or earlier',
    "A salary structure that resolves (the record's own, the Company Code's, or the company default)",
    'Bank account number and IFSC code on the employee profile',
)

BLOCKER_NO_SALARY = 'No salary record'
BLOCKER_NOT_EFFECTIVE = 'Salary record starts in the future'
BLOCKER_NO_STRUCTURE = 'No salary structure applies'
BLOCKER_NO_BANK = 'Bank account number or IFSC code missing'


def payroll_employees():
    """Employees payroll can ever apply to: active, with an employee code."""
    return current_workforce()


@dataclass
class ReadinessSnapshot:
    """Who is what, for one set of employees, as of one date. All sets hold employee primary keys."""
    employee_ids: set = field(default_factory=set)
    current_ids: set = field(default_factory=set)       # an active, already-effective salary record
    scheduled_ids: set = field(default_factory=set)     # an active salary record that starts in the future
    structure_ok_ids: set = field(default_factory=set)
    bank_ok_ids: set = field(default_factory=set)

    @property
    def configured_ids(self) -> set:
        return self.current_ids | self.scheduled_ids

    @property
    def missing_ids(self) -> set:
        return self.employee_ids - self.configured_ids

    @property
    def ready_ids(self) -> set:
        return self.current_ids & self.structure_ok_ids & self.bank_ok_ids

    def blockers_for(self, employee_pk) -> list[str]:
        blockers = []
        if employee_pk in self.scheduled_ids:
            blockers.append(BLOCKER_NOT_EFFECTIVE)
        elif employee_pk not in self.current_ids:
            blockers.append(BLOCKER_NO_SALARY)
        if employee_pk not in self.structure_ok_ids:
            blockers.append(BLOCKER_NO_STRUCTURE)
        if employee_pk not in self.bank_ok_ids:
            blockers.append(BLOCKER_NO_BANK)
        return blockers

    def summary(self) -> dict:
        total = len(self.employee_ids)
        ready = len(self.ready_ids)
        return {
            'total': total,
            'configured': len(self.configured_ids),
            'scheduled': len(self.scheduled_ids),
            'missing': len(self.missing_ids),
            'payroll_ready': ready,
            'blocked': total - ready,
            # An employee can appear under more than one reason.
            'blocked_by': {
                'no_salary_record': len(self.employee_ids - self.current_ids),
                'no_salary_structure': len(self.employee_ids - self.structure_ok_ids),
                'no_bank_details': len(self.employee_ids - self.bank_ok_ids),
            },
        }


def payroll_readiness(employees, today: datetime.date | None = None) -> ReadinessSnapshot:
    """The readiness of `employees` (a queryset of Users) as of `today`."""
    today = today or timezone.localdate()
    employee_ids = set(employees.values_list('pk', flat=True))

    active_records = EmployeeSalaryConfig.objects.filter(
        employee_id__in=employee_ids, is_active=True, annual_ctc__gt=0,
    )
    current_ids = set(active_records.filter(effective_from__lte=today).values_list('employee_id', flat=True))
    scheduled_ids = set(active_records.filter(effective_from__gt=today).values_list('employee_id', flat=True)) - current_ids

    bank_ok_ids = set(
        employees.exclude(Q(profile__account_number__isnull=True) | Q(profile__account_number=''))
        .exclude(profile__ifsc_code='').exclude(profile__ifsc_code__isnull=True)
        .values_list('pk', flat=True)
    )

    return ReadinessSnapshot(
        employee_ids=employee_ids, current_ids=current_ids, scheduled_ids=scheduled_ids,
        structure_ok_ids=_structure_ok_ids(employees, employee_ids),
        bank_ok_ids=bank_ok_ids,
    )


def _structure_ok_ids(employees, employee_ids: set) -> set:
    # A company default structure covers everyone who has no structure of their own.
    if SalaryStructure.objects.filter(is_default=True, is_active=True).exists():
        return set(employee_ids)
    own_structure = set(
        EmployeeSalaryConfig.objects.filter(
            employee_id__in=employee_ids, is_active=True, salary_structure__is_active=True,
        ).values_list('employee_id', flat=True)
    )
    branch_names = set(
        BranchPayrollConfig.objects.filter(salary_structure__is_active=True).values_list('branch__branch_name', flat=True)
    )
    in_structured_branch = set(employees.filter(branch__in=branch_names).values_list('pk', flat=True))
    return own_structure | in_structured_branch
