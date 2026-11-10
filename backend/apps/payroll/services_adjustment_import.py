"""
Payroll → Adjustments → Bulk Import (one-time additions, deductions and
arrears for one payroll month).

Columns: Employee Code, Type, Label, Amount. Same file reading, preview and
confirmation pattern as the salary structure import (services_structure_import):
the preview saves nothing, the confirm request re-reads and re-validates the
whole file, and nothing is saved if any row has an error.

Refused rows:
  * employee code missing, unknown, inactive, matching more than one
    employee, or outside the importer's branch;
  * type / label / amount invalid;
  * the same adjustment twice in the file, or one already saved for the month;
  * the month's payroll for the employee's branch is already sent or paid
    (or being processed). A month already calculated but not sent is
    accepted with a warning: re-run the calculation to apply it.
"""
from __future__ import annotations

from collections import defaultdict
from datetime import date
from decimal import Decimal, InvalidOperation

from django.db import transaction
from django.db.models.functions import Upper

from apps.accounts.models import User
from apps.payroll.models import PayrollAdjustment, PayrollCycle

HEADERS = ['Employee Code', 'Type', 'Label', 'Amount']
SAMPLE_ROWS = [
    ['EMP001', 'addition', 'Festival Bonus', '5000'],
    ['EMP002', 'deduction', 'Salary Advance Recovery', '2000'],
    ['EMP003', 'arrear', 'March Arrear', '3500'],
]
COLUMNS = {
    'employee code': 'employee_code', 'employee_code': 'employee_code', 'employee id': 'employee_code',
    'employee_id': 'employee_code', 'emp id': 'employee_code', 'emp code': 'employee_code',
    'type': 'type', 'adjustment type': 'type',
    'label': 'label', 'description': 'label',
    'amount': 'amount',
}
REQUIRED = {'employee_code': 'Employee Code', 'type': 'Type', 'label': 'Label', 'amount': 'Amount'}

_TYPES = {PayrollAdjustment.ADDITION, PayrollAdjustment.DEDUCTION, PayrollAdjustment.ARREAR}
_MAX_AMOUNT = Decimal('100000000')          # amount is max_digits=10, decimal_places=2
# Payslips already sent to employees or paid: their adjustments can't change.
_LOCKED = (PayrollCycle.STATUS_PROCESSING, PayrollCycle.STATUS_QUERY_WINDOW_OPEN,
           PayrollCycle.STATUS_PAID, PayrollCycle.STATUS_CLOSED)

CREATE, ERROR = 'create', 'error'


def _amount(raw: str) -> tuple[Decimal | None, str | None]:
    try:
        value = Decimal(raw.replace(',', '').strip())
        if not value.is_finite():
            raise InvalidOperation
    except (InvalidOperation, ValueError):
        return None, f'Amount: "{raw}" is not a number.' if raw else 'Amount: required.'
    if value <= 0:
        return None, 'Amount: must be more than 0.'
    if value != value.quantize(Decimal('0.01')):
        return None, 'Amount: use at most 2 decimal places.'
    if value >= _MAX_AMOUNT:
        return None, 'Amount: too large.'
    return value, None


def _cycles_for(month: date) -> dict:
    """{branch name or None (company-wide): [statuses]} for the month's non-cancelled cycles."""
    out = defaultdict(list)
    for status, branch in (PayrollCycle.objects
                           .filter(cycle_start__year=month.year, cycle_start__month=month.month)
                           .exclude(status=PayrollCycle.STATUS_CANCELLED)
                           .values_list('status', 'branch__branch_name')):
        out[branch].append(status)
    return out


def plan(rows: list[dict], *, month: date, in_scope) -> list[dict]:
    """in_scope(employee) -> bool: the importer's branch scope."""
    month_label = month.strftime('%B %Y')
    codes = [(r.get('employee_code') or '').strip().upper() for r in rows]
    matches = defaultdict(list)
    for u in User.objects.annotate(u=Upper('employee_id')).filter(u__in=[c for c in codes if c]):
        matches[u.employee_id.upper()].append(u)
    existing = {
        (a.employee_id, a.type, a.label.strip().lower(), a.amount)
        for a in PayrollAdjustment.objects.filter(month=month)
    }
    cycles = _cycles_for(month)
    seen: dict = {}

    out = []
    for idx, (row, code) in enumerate(zip(rows, codes), start=2):
        p = {'row': idx, 'employee_code': (row.get('employee_code') or '').strip(), 'name': '',
             'type': (row.get('type') or '').strip().lower(), 'label': ' '.join((row.get('label') or '').split()),
             'amount': (row.get('amount') or '').strip(), 'status': ERROR, 'message': ''}
        out.append(p)
        problems = []
        employee = None
        if not code:
            problems.append('Employee Code: required.')
        else:
            found = matches.get(code, [])
            if len(found) > 1:
                problems.append(f'Employee Code: "{p["employee_code"]}" matches more than one employee — '
                                'fix the employee records first.')
            elif not found or not in_scope(found[0]):
                problems.append(f'Employee Code: "{p["employee_code"]}" doesn\'t match any employee you can manage.')
            elif not found[0].is_active:
                problems.append(f'Employee Code: "{p["employee_code"]}" is an inactive employee.')
            else:
                employee = found[0]
                p.update(employee_code=employee.employee_id, name=employee.full_name)
        if p['type'] not in _TYPES:
            problems.append(f'Type: must be addition, deduction or arrear (got "{p["type"]}").' if p['type']
                            else 'Type: required.')
        if not p['label']:
            problems.append('Label: required.')
        elif len(p['label']) > 200:
            problems.append('Label: at most 200 characters.')
        amount, problem = _amount(p['amount'])
        if problem:
            problems.append(problem)

        if not problems:
            key = (employee.pk, p['type'], p['label'].lower(), amount)
            if key in seen:
                problems.append(f'Same adjustment as row {seen[key]} — keep one row.')
            elif key in existing:
                problems.append(f'This adjustment is already saved for {month_label} — delete it first '
                                'if it really should be added twice.')
            seen.setdefault(key, idx)
        if employee is not None and not problems:
            statuses = cycles.get(employee.branch, []) + cycles.get(None, [])
            if any(s in _LOCKED for s in statuses):
                problems.append(f'{month_label} payroll is already sent to employees or paid — '
                                'adjustments can no longer be added for this month.')
            elif PayrollCycle.STATUS_PAYSLIPS_GENERATED in statuses:
                p['message'] = (f'{month_label} payroll is already calculated — run the calculation again '
                                'to apply this adjustment.')

        if problems:
            p['message'] = ' '.join(problems)
            continue
        p.update(status=CREATE, amount=str(amount), _employee=employee, _amount=amount)
    return out


def summarise(rows: list[dict]) -> dict:
    return {
        CREATE: sum(r['status'] == CREATE for r in rows),
        ERROR: sum(r['status'] == ERROR for r in rows),
        'warnings': sum(r['status'] == CREATE and bool(r['message']) for r in rows),
        'total': len(rows),
    }


def public(rows: list[dict]) -> list[dict]:
    return [{k: v for k, v in r.items() if not k.startswith('_')} for r in rows]


@transaction.atomic
def apply(rows: list[dict], *, month: date, user) -> int:
    """Saves every row of a plan that has no errors (the caller checks that)."""
    created = PayrollAdjustment.objects.bulk_create([
        PayrollAdjustment(employee=r['_employee'], month=month, type=r['type'], label=r['label'],
                          amount=r['_amount'], created_by=user)
        for r in rows if r['status'] == CREATE
    ])
    for r in rows:
        if r['status'] == CREATE:
            r['status'] = 'created'
    return len(created)
