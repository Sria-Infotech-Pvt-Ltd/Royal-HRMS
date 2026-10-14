"""
Monthly Leave Management (Settings → Leave Management) — bulk import of
employee-wise monthly leave credits.

The preview and the confirmed import run the same plan_import() validation;
confirmed rows are applied only through set_monthly_credit(), the same path
manual entry uses, so there is one set of business rules and one balance
(LeaveBalance) for every leave screen to read.
"""
from __future__ import annotations

from decimal import Decimal

from .models import LEAVE_LWP, LeaveBalance, LeavePolicy
from .services_leave_credit import (
    LeaveCreditError, _clean_year, clean_month, clean_monthly_credit, current_calendar_year, leave_type_label,
    monthly_credit_value, set_monthly_credit,
)

SAMPLE_HEADERS = ['Employee Code', 'Leave Type', 'Monthly Leave Credit']
SAMPLE_ROWS = [
    ['EMP001', 'Casual Leave', '1'],
    ['EMP002', 'Sick Leave', '0.5'],
    ['EMP003', 'Earned Leave', '1.5'],
]
MAX_IMPORT_ROWS = 2000

_COLUMNS = {
    'employee code': 'employee_code', 'employee_code': 'employee_code', 'employee id': 'employee_code',
    'employee_id': 'employee_code', 'emp code': 'employee_code',
    'leave type': 'leave_type', 'leave_type': 'leave_type',
    'monthly leave credit': 'credit', 'monthly_leave_credit': 'credit', 'monthly credit': 'credit',
    'credit': 'credit',
}
_REQUIRED = ('employee_code', 'leave_type', 'credit')


def _f(value) -> float:
    return float(value)


def leave_type_lookup() -> dict:
    """Code or label (case-insensitive) → leave_type code, for active non-LWP policies."""
    lookup = {}
    for p in LeavePolicy.objects.filter(is_active=True).exclude(leave_type=LEAVE_LWP):
        lookup[p.leave_type.lower()] = p.leave_type
        lookup[leave_type_label(p.leave_type, p).lower()] = p.leave_type
    return lookup


def annual_entitlements() -> dict:
    """leave_type → annual_days for active policies that also have an annual entitlement."""
    return {
        p.leave_type: _f(p.annual_days)
        for p in LeavePolicy.objects.filter(is_active=True, annual_days__gt=0).exclude(leave_type=LEAVE_LWP)
    }


def normalize_rows(raw_rows: list[dict]) -> tuple[list[dict], str | None]:
    """Map the file's headers to employee_code / leave_type / credit and number the rows."""
    if not raw_rows:
        return [], 'The file contains no data rows.'
    present = {_COLUMNS.get((k or '').strip().lower()) for k in raw_rows[0].keys()}
    missing = [c for c in _REQUIRED if c not in present]
    if missing:
        return [], 'Missing column(s): ' + ', '.join(
            {'employee_code': 'Employee Code', 'leave_type': 'Leave Type', 'credit': 'Monthly Leave Credit'}[c]
            for c in missing
        ) + '. Use the sample template.'
    if len(raw_rows) > MAX_IMPORT_ROWS:
        return [], f'The file has {len(raw_rows)} rows; import at most {MAX_IMPORT_ROWS} at a time.'
    rows = []
    for i, raw in enumerate(raw_rows, start=2):  # row 1 is the header
        row = {'row': i}
        for key, val in raw.items():
            col = _COLUMNS.get((key or '').strip().lower())
            if col:
                row[col] = str(val or '').strip()
        rows.append(row)
    return rows, None


def plan_import(rows: list[dict], *, actor, year, month) -> dict:
    """
    Validate every row without writing anything. Each row gets a status:
    new / update / unchanged (same value already set — skipped) / error.
    """
    from apps.accounts.models import User
    from .views.leave import _can_manage_leave_credits

    year, month = _clean_year(year), clean_month(month)
    types = leave_type_lookup()
    codes = {r.get('employee_code', '') for r in rows} - {''}
    employees = {u.employee_id: u for u in User.objects.filter(employee_id__in=codes)}

    planned, seen = [], set()
    for r in rows:
        code, raw_type, raw_credit = r.get('employee_code', ''), r.get('leave_type', ''), r.get('credit', '')
        out = {'row': r['row'], 'employee_code': code, 'employee_name': None, 'leave_type': raw_type,
               'leave_type_label': None, 'credit': raw_credit, 'previous': None, 'delta': None,
               'status': 'error', 'message': ''}
        planned.append(out)

        employee = employees.get(code)
        if not code or employee is None or not _can_manage_leave_credits(actor, employee):
            out['message'] = f'Employee code "{code}" was not found.' if code else 'Employee Code is required.'
            continue
        out['employee_name'] = employee.full_name
        if not employee.is_active:
            out['message'] = 'Employee is inactive.'
            continue
        leave_type = types.get(raw_type.lower())
        if not leave_type:
            out['message'] = f'Leave type "{raw_type}" is not an active leave type.' if raw_type else 'Leave Type is required.'
            continue
        out['leave_type'] = leave_type
        out['leave_type_label'] = leave_type_label(leave_type, LeavePolicy.objects.filter(leave_type=leave_type).first())
        try:
            value = clean_monthly_credit(raw_credit)
        except LeaveCreditError as exc:
            out['message'] = str(exc)
            continue
        out['credit'] = _f(value)
        key = (employee.pk, leave_type)
        if key in seen:
            out['status'] = 'duplicate'
            out['message'] = 'Duplicate employee and leave type in this file; only the first row is used.'
            continue
        seen.add(key)

        if year != current_calendar_year() and not LeaveBalance.objects.filter(
                employee=employee, leave_type=leave_type, year=year).exists():
            out['message'] = f'No {year} balance exists for this leave type; past years can only be changed where a balance exists.'
            continue

        previous = monthly_credit_value(employee, leave_type, year, month)
        out['previous'], out['delta'] = _f(previous), _f(value - previous)
        if value == previous:
            out['status'], out['message'] = 'unchanged', 'Already set to this value; nothing to change.'
        elif previous:
            out['status'], out['message'] = 'update', f'Changes {previous} → {value} day(s).'
        else:
            out['status'], out['message'] = 'new', f'Adds {value} day(s).'
        out['_employee'] = employee

    counts = {s: sum(1 for p in planned if p['status'] == s) for s in ('new', 'update', 'unchanged', 'duplicate', 'error')}
    return {'year': year, 'month': month, 'rows': planned, 'counts': counts,
            'annual_entitlements': annual_entitlements()}


def apply_import(plan: dict, *, actor, ip_address=None) -> dict:
    """Apply the plan's new/update rows, each in its own transaction (a failed row changes nothing)."""
    created = updated = 0
    for row in plan['rows']:
        employee = row.pop('_employee', None)
        if row['status'] not in ('new', 'update'):
            continue
        try:
            result = set_monthly_credit(
                employee=employee, leave_type=row['leave_type'], year=plan['year'], month=plan['month'],
                value=Decimal(str(row['credit'])), actor=actor, source='import', ip_address=ip_address,
            )
        except LeaveCreditError as exc:
            row['status'], row['message'] = 'error', str(exc)
            continue
        row['previous'], row['delta'] = _f(result['previous']), _f(result['delta'])
        if result['status'] == 'unchanged':  # set by a concurrent change between preview and confirm
            row['status'], row['message'] = 'unchanged', 'Already set to this value; nothing to change.'
        elif result['status'] == 'updated':
            updated += 1
        else:
            created += 1
    for row in plan['rows']:
        row.pop('_employee', None)

    errors = sum(1 for r in plan['rows'] if r['status'] == 'error')
    skipped = sum(1 for r in plan['rows'] if r['status'] in ('unchanged', 'duplicate'))
    return {
        'year': plan['year'], 'month': plan['month'], 'rows': plan['rows'],
        'summary': {'created': created, 'updated': updated, 'skipped': skipped, 'failed': errors,
                    'total': len(plan['rows'])},
        'annual_entitlements': plan['annual_entitlements'],
    }


def strip_internal(plan: dict) -> dict:
    """Preview response: drop the in-memory employee objects."""
    for row in plan['rows']:
        row.pop('_employee', None)
    return plan
