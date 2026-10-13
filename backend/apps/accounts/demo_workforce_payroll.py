"""
Runs a real payroll cycle for the `seed_demo_workforce` command by calling the project's own payroll endpoints
in-process (rest_framework APIClient with force_authenticate — no password or login is involved). Because it goes
through the real views, the cycle gets exactly what a user-driven run gets: manager approval rows, audit-log
entries, the salary engine's statutory deductions, bank-detail snapshots and the dual sign-off before "paid".

The runner is state-driven and idempotent: it finds the cycle it tagged earlier and continues from whatever
status it is in. A cycle that was not created by this seed is never advanced.
"""
from django.test import override_settings
from rest_framework.test import APIClient

from apps.accounts.demo_workforce_data import CYCLE_TAG
from apps.payroll.models import EmployeePayslip, ManagerAttendanceApproval, PayrollCycle

DEMO_EMAIL_DOMAIN = '@example.com'


class PayrollStepError(Exception):
    """A payroll endpoint refused a step; the message is the endpoint's own."""


def _call(client, user, method, path, payload=None):
    client.force_authenticate(user=user)
    response = getattr(client, method)(path, payload or {}, format='json')
    body = response.json() if response['Content-Type'].startswith('application/json') else {}
    if response.status_code >= 400 or body.get('success') is False:
        raise PayrollStepError(f"{method.upper()} {path} → {response.status_code}: {body.get('message', body)}")
    return body.get('data')


def _find_or_create_cycle(client, actor, branch, period):
    start, end, pay_date = period
    cycle = PayrollCycle.objects.filter(branch=branch, cycle_start=start, cycle_end=end, notes=CYCLE_TAG).first()
    if cycle is not None:
        return cycle
    if PayrollCycle.objects.filter(branch=branch, cycle_start__lte=end, cycle_end__gte=start).exclude(
            status=PayrollCycle.STATUS_CANCELLED).exists():
        return None  # a real cycle already covers this period — leave it alone
    _call(client, actor, 'post', '/api/payroll/cycles/', {
        'cycle_start': str(start), 'cycle_end': str(end), 'pay_date': str(pay_date),
        'branch_id': str(branch.pk), 'notes': CYCLE_TAG,
    })
    return PayrollCycle.objects.get(branch=branch, cycle_start=start, cycle_end=end, notes=CYCLE_TAG)


def _approve_attendance(client, actor, cycle, can_act_as_any_manager):
    """L1: each manager row is approved by that manager (demo accounts only unless allowed), then HR L2."""
    for row in ManagerAttendanceApproval.objects.filter(cycle=cycle, approved_at__isnull=True).select_related('manager'):
        if not (can_act_as_any_manager or row.manager.email.lower().endswith(DEMO_EMAIL_DOMAIN)):
            raise PayrollStepError(
                f'{row.manager.email} must approve attendance for this cycle (a real account) — '
                'approve it in the app, or re-run with --approve-as-any-manager.')
        _call(client, row.manager, 'post', f'/api/payroll/cycles/{cycle.pk}/approve-attendance/', {'level': 'L1'})
    cycle.refresh_from_db()
    if not cycle.attendance_approved_by_l1_id:  # no manager rows existed → HR approves L1 directly
        _call(client, actor, 'post', f'/api/payroll/cycles/{cycle.pk}/approve-attendance/', {'level': 'L1'})
        cycle.refresh_from_db()
    if cycle.status == PayrollCycle.STATUS_ATTENDANCE_PENDING:
        _call(client, actor, 'post', f'/api/payroll/cycles/{cycle.pk}/approve-attendance/', {'level': 'L2'})


def _advance(client, actor, cycle, employee_codes, can_act_as_any_manager):
    """Take the cycle one stage forward from its current status. Returns False once it is paid."""
    status = cycle.status
    base = f'/api/payroll/cycles/{cycle.pk}'
    if status == PayrollCycle.STATUS_ATTENDANCE_PENDING:
        _approve_attendance(client, actor, cycle, can_act_as_any_manager)
    elif status == PayrollCycle.STATUS_ATTENDANCE_APPROVED:
        _call(client, actor, 'post', f'{base}/process/', {'employee_ids': employee_codes})
    elif status == PayrollCycle.STATUS_PAYSLIPS_GENERATED:
        _call(client, actor, 'post', f'{base}/payslips/dispatch/')
    elif status == PayrollCycle.STATUS_QUERY_WINDOW_OPEN:
        _acknowledge_and_pay(client, actor, cycle)
    else:
        return False
    cycle.refresh_from_db()
    return cycle.status != PayrollCycle.STATUS_PAID


def _acknowledge_and_pay(client, actor, cycle):
    for payslip in cycle.payslips.filter(status=EmployeePayslip.STATUS_SENT).select_related('employee'):
        _call(client, payslip.employee, 'post', f'/api/payroll/my-payslips/{payslip.pk}/acknowledge/')
    base = f'/api/payroll/cycles/{cycle.pk}'
    _call(client, actor, 'post', f'{base}/salary-transfer/confirm/')
    _call(client, actor, 'post', f'{base}/mark-paid/')


def run_cycle(actor, branch, period, employee_codes, can_act_as_any_manager=False) -> str:
    """Drive one branch's cycle for `period` to "paid". Returns a one-line outcome."""
    with override_settings(ALLOWED_HOSTS=['*'], SECURE_SSL_REDIRECT=False):
        client = APIClient(SERVER_NAME='localhost')
        cycle = _find_or_create_cycle(client, actor, branch, period)
        if cycle is None:
            return f'{branch.branch_name} {period[0]}…{period[1]}: skipped (a cycle that is not part of this seed already covers it)'
        for _ in range(8):  # at most one pass per stage
            if not _advance(client, actor, cycle, employee_codes, can_act_as_any_manager):
                break
        payslips = cycle.payslips.count()
        return f'{branch.branch_name} {period[0]}…{period[1]}: {cycle.status}, {payslips} payslips'
