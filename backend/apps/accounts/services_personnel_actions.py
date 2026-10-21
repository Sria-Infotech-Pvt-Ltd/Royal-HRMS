"""
Business logic for PersonnelActionRequest (see models_personnel_action.py).

Maker-checker rules enforced here, not in the views:
  * the person who raised a request can never decide any step of it;
  * nobody can decide a step of a request about themselves;
  * each step can only be decided by someone who holds that step's authority
    AND covers the employee (direct reports for the manager step, same branch
    — or an org-wide admin — for the HR / Payroll steps);
  * the change is applied ONLY after the last step is approved, through the
    same view the direct path uses, running as the approver who holds the
    permission that view checks. So an approved request can never do
    something its approver could not have done by hand.
"""
from __future__ import annotations

from core.access import can_manage_team
import logging
from datetime import datetime
from typing import Optional

from django.db import transaction
from django.utils import timezone
from rest_framework.test import APIRequestFactory, force_authenticate

from core.permissions import has_perm

from .models import AuditLog, Position, User
from .models_personnel_action import PersonnelActionRequest as PAR

logger = logging.getLogger(__name__)

STEP_MANAGER = 'manager'
STEP_HR      = 'hr'
STEP_PAYROLL = 'payroll'

STEP_LABELS = {
    STEP_MANAGER: 'Reporting manager',
    STEP_HR:      'HR Business Partner',
    STEP_PAYROLL: 'Payroll Admin',
}

# Mirrors the reference's approval routes. Org assignment / Confirmation list
# only the reporting manager there; because the manager is the one RAISING
# them, a second pair of eyes with real apply authority (HR) is appended —
# otherwise the maker would be the only checker.
BASE_ROUTES = {
    PAR.TYPE_PROMOTION:      [STEP_MANAGER, STEP_HR],
    PAR.TYPE_ORG_ASSIGNMENT: [STEP_MANAGER, STEP_HR],
    PAR.TYPE_CONFIRMATION:   [STEP_MANAGER, STEP_HR],
    PAR.TYPE_PAY_CHANGE:     [STEP_HR, STEP_PAYROLL],
}


class ActionRequestError(Exception):
    """Raised for any rule violation; message is safe to show to the user."""

    def __init__(self, message: str, http_status: int = 400):
        super().__init__(message)
        self.message = message
        self.http_status = http_status


# ─── scope / authority ───────────────────────────────────────────────────────

def _covers(user: User, employee: User) -> bool:
    """HR/Payroll approvers act org-wide if they hold settings.edit, otherwise
    only inside their own branch — the same rule _employee_out_of_branch_scope
    applies to every other employee action."""
    if user.is_superuser or has_perm(user, 'settings.edit'):
        return True
    return bool(user.branch) and user.branch == employee.branch


def can_decide_step(user: User, req: PAR, step: dict) -> bool:
    if step.get('status') != 'pending' or req.status != PAR.STATUS_PENDING:
        return False
    if user.id == req.raised_by_id or user.id == req.employee_id:
        return False
    key = step['key']
    employee = req.employee
    if key == STEP_MANAGER:
        return employee.reporting_manager_id == user.id
    if key == STEP_HR:
        return has_perm(user, 'employees.approve') and has_perm(user, 'employees.edit') and _covers(user, employee)
    if key == STEP_PAYROLL:
        return has_perm(user, 'payroll.edit') and _covers(user, employee)
    return False


def current_step(req: PAR) -> Optional[dict]:
    if req.status != PAR.STATUS_PENDING or req.current_step >= len(req.steps):
        return None
    return req.steps[req.current_step]


def can_user_decide(user: User, req: PAR) -> bool:
    step = current_step(req)
    return bool(step) and can_decide_step(user, req, step)


def can_user_cancel(user: User, req: PAR) -> bool:
    return req.status == PAR.STATUS_PENDING and (user.id == req.raised_by_id or has_perm(user, 'settings.edit'))


# ─── building a request ──────────────────────────────────────────────────────

def _route_for(action_type: str, payload: dict) -> list:
    route = list(BASE_ROUTES[action_type])
    # A promotion that also carries a new CTC needs the person who holds
    # payroll.edit to apply that half — HR alone cannot write salary.
    if action_type == PAR.TYPE_PROMOTION and payload.get('annual_ctc') and STEP_PAYROLL not in route:
        route.append(STEP_PAYROLL)
    return route


def _is_reporting_manager_of(user: User, employee: User) -> bool:
    return employee.reporting_manager_id == user.id or can_manage_team(user)


def build_steps(action_type: str, payload: dict, raiser: User, employee: User) -> list:
    now = timezone.now().isoformat()
    steps = []
    for key in _route_for(action_type, payload):
        step = {
            'key': key, 'label': STEP_LABELS[key], 'status': 'pending',
            'decided_by_id': None, 'decided_by_name': '', 'decided_at': None, 'note': '',
        }
        # The manager's own approval is the act of raising it.
        if key == STEP_MANAGER and _is_reporting_manager_of(raiser, employee):
            step.update(status='approved', decided_by_id=str(raiser.id), decided_by_name=raiser.full_name,
                        decided_at=now, note='Raised by reporting manager')
        steps.append(step)
    return steps


def _parse_date(value) -> 'datetime.date':
    try:
        return datetime.strptime(str(value or '').strip(), '%Y-%m-%d').date()
    except ValueError:
        raise ActionRequestError('effective_from must be in YYYY-MM-DD format.')


def _clean_payload(action_type: str, data: dict, employee: User) -> tuple[dict, dict]:
    """Validate the type-specific fields; return (payload, before-snapshot)."""
    payload: dict = {}
    before: dict = {}
    if action_type == PAR.TYPE_PROMOTION:
        position_id = str(data.get('position') or '').strip()
        position = Position.objects.filter(pk=position_id, is_active=True).select_related('org_unit').first() if position_id else None
        if position is None:
            raise ActionRequestError('Select a valid, active position.')
        payload['position'] = str(position.id)
        before['position'] = employee.designation or '—'
        if data.get('annual_ctc'):
            payload['annual_ctc'] = _clean_ctc(data.get('annual_ctc'))
    elif action_type == PAR.TYPE_ORG_ASSIGNMENT:
        manager_id = str(data.get('reporting_manager_id') or '').strip()
        work_location = str(data.get('work_location') or '').strip()
        if not manager_id and not work_location:
            raise ActionRequestError('Choose a new reporting manager or a new work location.')
        if manager_id:
            manager = User.objects.filter(pk=manager_id, is_active=True).first()
            if manager is None or manager.id == employee.id:
                raise ActionRequestError('Select a valid reporting manager.')
            payload['reporting_manager_id'] = str(manager.id)
        if work_location:
            payload['work_location'] = work_location
        before['reporting_manager'] = employee.reporting_manager.full_name if employee.reporting_manager_id else '—'
        before['work_location'] = employee.work_location or '—'
    elif action_type == PAR.TYPE_PAY_CHANGE:
        payload['annual_ctc'] = _clean_ctc(data.get('annual_ctc'))
        before['annual_ctc'] = _current_ctc(employee)
    elif action_type == PAR.TYPE_CONFIRMATION:
        if employee.employment_status == User.EMPLOYMENT_STATUS_CONFIRMED:
            raise ActionRequestError('This employee is already confirmed.')
        before['employment_status'] = 'Probation'
    return payload, before


def valid_reasons(action_type: str) -> dict:
    """Reason codes the underlying direct endpoint accepts for this action —
    validated at raise time so a request can never be approved and then fail
    to apply purely because its reason was not one the endpoint recognises."""
    from apps.payroll.models import EmployeeSalaryConfig

    from .models import PromotionRecord
    from .views.employees_actions import CONFIRMATION_REASON_CHOICES

    if action_type == PAR.TYPE_PAY_CHANGE:
        return dict(EmployeeSalaryConfig.REASON_CHOICES)
    if action_type == PAR.TYPE_CONFIRMATION:
        return dict(CONFIRMATION_REASON_CHOICES)
    return dict(PromotionRecord.REASON_CHOICES)


def _clean_ctc(value) -> str:
    try:
        amount = float(str(value).replace(',', '').strip())
    except (TypeError, ValueError):
        raise ActionRequestError('Annual CTC must be a number.')
    if amount <= 0:
        raise ActionRequestError('Annual CTC must be greater than zero.')
    return str(int(amount)) if amount == int(amount) else str(amount)


def _current_ctc(employee: User) -> str:
    from apps.payroll.models import EmployeeSalaryConfig
    config = EmployeeSalaryConfig.objects.filter(employee=employee, is_active=True).first()
    return str(config.annual_ctc) if config else '—'


@transaction.atomic
def raise_request(raiser: User, employee: User, data: dict) -> PAR:
    action_type = str(data.get('action_type') or '').strip()
    if action_type not in dict(PAR.TYPE_CHOICES):
        raise ActionRequestError('Select a valid action type.')
    if not has_perm(raiser, 'employees.raise_action'):
        raise ActionRequestError('You do not have permission to raise this action.', 403)
    if raiser.id == employee.id:
        raise ActionRequestError('You cannot raise a personnel action on yourself.', 403)
    reason = str(data.get('reason') or '').strip()
    if not reason:
        raise ActionRequestError('Select a reason.')
    if reason not in valid_reasons(action_type):
        raise ActionRequestError('Select one of the recognised reasons for this action.')
    effective_from = _parse_date(data.get('effective_from'))
    payload, before = _clean_payload(action_type, data, employee)
    if PAR.objects.filter(employee=employee, action_type=action_type, status=PAR.STATUS_PENDING).exists():
        raise ActionRequestError(
            f'There is already a pending {dict(PAR.TYPE_CHOICES)[action_type].lower()} for this employee awaiting approval.', 409,
        )
    req = PAR.objects.create(
        employee=employee, action_type=action_type, reason=reason[:60], effective_from=effective_from,
        payload=payload, before=before, raised_by=raiser,
        steps=build_steps(action_type, payload, raiser, employee),
    )
    req.current_step = next((i for i, s in enumerate(req.steps) if s['status'] == 'pending'), len(req.steps))
    req.save(update_fields=['current_step', 'updated_at'])
    _audit(raiser, req, 'personnel_action_raised')
    _notify_next_approvers(req)
    return req


# ─── deciding ────────────────────────────────────────────────────────────────

@transaction.atomic
def decide(req_id, user: User, decision: str, note: str = '') -> PAR:
    if decision not in ('approve', 'reject'):
        raise ActionRequestError('decision must be approve or reject.')
    req = PAR.objects.select_for_update(of=('self',)).select_related('employee', 'raised_by').get(pk=req_id)
    step = current_step(req)
    if step is None:
        raise ActionRequestError('This request is no longer awaiting a decision.', 409)
    if not can_decide_step(user, req, step):
        raise ActionRequestError('You are not allowed to decide this step of the request.', 403)
    note = (note or '').strip()
    if decision == 'reject' and not note:
        raise ActionRequestError('Add a reason for rejecting this request.')

    step.update(
        status='approved' if decision == 'approve' else 'rejected',
        decided_by_id=str(user.id), decided_by_name=user.full_name,
        decided_at=timezone.now().isoformat(), note=note,
    )
    if decision == 'reject':
        req.status = PAR.STATUS_REJECTED
        req.decision_note = note
    else:
        req.current_step += 1
    req.steps = list(req.steps)  # force JSONField change detection
    req.save(update_fields=['steps', 'current_step', 'status', 'decision_note', 'updated_at'])
    _audit(user, req, f'personnel_action_{decision}d' if decision == 'approve' else 'personnel_action_rejected')

    if decision == 'approve' and req.current_step >= len(req.steps):
        _apply(req)
    elif decision == 'approve':
        _notify_next_approvers(req)
    _notify_raiser(req, user)
    return req


@transaction.atomic
def cancel(req_id, user: User) -> PAR:
    req = PAR.objects.select_for_update(of=('self',)).select_related('employee').get(pk=req_id)
    if not can_user_cancel(user, req):
        raise ActionRequestError('Only the person who raised a pending request can cancel it.', 403)
    req.status = PAR.STATUS_CANCELLED
    req.save(update_fields=['status', 'updated_at'])
    _audit(user, req, 'personnel_action_cancelled')
    return req


# ─── applying ────────────────────────────────────────────────────────────────

def _step_approver(req: PAR, key: str) -> Optional[User]:
    for step in req.steps:
        if step['key'] == key and step.get('decided_by_id') and step['status'] == 'approved':
            return User.objects.filter(pk=step['decided_by_id']).first()
    return None


def _dispatch(view, method: str, kwargs: dict, data: dict, user: User):
    """Call an existing DRF view as `user`, in-process, and return its response."""
    request = getattr(APIRequestFactory(), method)('/internal/personnel-action/', data, format='json')
    force_authenticate(request, user=user)
    return view.as_view()(request, **kwargs)


def _response_message(response) -> str:
    data = getattr(response, 'data', None)
    return (data or {}).get('message') if isinstance(data, dict) else ''


def _apply(req: PAR) -> None:
    from apps.payroll.views.employee_salary import EmployeeSalaryConfigListView
    from .views.employees_actions import EmployeeConfirmView
    from .views.employees_detail import EmployeeDetailView

    employee, payload = req.employee, req.payload
    hr_user = _step_approver(req, STEP_HR)
    payroll_user = _step_approver(req, STEP_PAYROLL)
    code = employee.employee_id
    effective = req.effective_from.isoformat()
    done: list[str] = []
    try:
        if req.action_type == PAR.TYPE_PROMOTION:
            _must_ok(_dispatch(EmployeeDetailView, 'put', {'employee_id': code},
                               {'position': payload['position'], 'effective_date': effective, 'reason': req.reason}, hr_user),
                     'position change')
            done.append('position')
            if payload.get('annual_ctc'):
                _must_ok(_dispatch(EmployeeSalaryConfigListView, 'post', {},
                                   {'employee': str(employee.id), 'annual_ctc': payload['annual_ctc'],
                                    'effective_from': effective, 'reason': 'promotion'}, payroll_user),
                         'pay change')
        elif req.action_type == PAR.TYPE_ORG_ASSIGNMENT:
            body = {'effective_date': effective, 'reason': req.reason}
            if payload.get('reporting_manager_id'):
                body['reporting_manager_id'] = payload['reporting_manager_id']
            if payload.get('work_location'):
                body['work_location'] = payload['work_location']
            _must_ok(_dispatch(EmployeeDetailView, 'put', {'employee_id': code}, body, hr_user), 'org assignment')
        elif req.action_type == PAR.TYPE_PAY_CHANGE:
            _must_ok(_dispatch(EmployeeSalaryConfigListView, 'post', {},
                               {'employee': str(employee.id), 'annual_ctc': payload['annual_ctc'],
                                'effective_from': effective, 'reason': req.reason}, payroll_user),
                     'pay change')
        elif req.action_type == PAR.TYPE_CONFIRMATION:
            _must_ok(_dispatch(EmployeeConfirmView, 'post', {'employee_id': code},
                               {'effective_date': effective, 'reason': req.reason}, hr_user), 'confirmation')
    except ActionRequestError as exc:
        req.status = PAR.STATUS_FAILED
        prefix = f'Already applied: {", ".join(done)}. ' if done else ''
        req.apply_error = prefix + exc.message
        req.save(update_fields=['status', 'apply_error', 'updated_at'])
        _audit(hr_user or payroll_user, req, 'personnel_action_apply_failed')
        logger.warning('Personnel action %s could not be applied: %s', req.pk, exc.message)
        return
    req.status = PAR.STATUS_APPLIED
    req.applied_at = timezone.now()
    req.save(update_fields=['status', 'applied_at', 'updated_at'])
    _audit(hr_user or payroll_user, req, 'personnel_action_applied')


def _must_ok(response, what: str) -> None:
    if response.status_code >= 400:
        raise ActionRequestError(f'The {what} was rejected: {_response_message(response) or "validation failed."}')


# ─── queries ─────────────────────────────────────────────────────────────────

def inbox_for(user: User) -> list:
    pending = PAR.objects.filter(status=PAR.STATUS_PENDING).select_related('employee', 'raised_by')
    return [r for r in pending if can_user_decide(user, r)]


# ─── side effects ────────────────────────────────────────────────────────────

def _audit(user: Optional[User], req: PAR, action: str) -> None:
    AuditLog.objects.create(
        user=user, action=action, module='employees', object_id=str(req.employee_id),
        changes={'request_id': str(req.pk), 'action_type': req.action_type, 'status': req.status,
                 'employee_id': req.employee.employee_id, 'payload': req.payload},
    )


def _notify_next_approvers(req: PAR) -> None:
    from apps.notifications.signals import _notify

    step = current_step(req)
    if not step:
        return
    candidates: list[User] = []
    if step['key'] == STEP_MANAGER and req.employee.reporting_manager_id:
        candidates = [req.employee.reporting_manager]
    else:
        codename = 'employees.approve' if step['key'] == STEP_HR else 'payroll.edit'
        candidates = [u for u in User.objects.filter(is_active=True).select_related('role')
                      if has_perm(u, codename) and can_decide_step(u, req, step)][:25]
    label = req.get_action_type_display()
    for approver in candidates:
        _notify(approver, f'{label} awaiting your approval',
                f'{req.raised_by.full_name if req.raised_by_id else "A manager"} raised a {label.lower()} for '
                f'{req.employee.full_name} ({req.employee.employee_id}).',
                'promotion', 'promotion', reference_id=str(req.pk), created_by=req.raised_by, category='approval')


def _notify_raiser(req: PAR, actor: User) -> None:
    from apps.notifications.signals import _notify

    if not req.raised_by_id:
        return
    label = req.get_action_type_display()
    outcome = {
        PAR.STATUS_APPLIED:  'approved and applied',
        PAR.STATUS_REJECTED: 'rejected',
        PAR.STATUS_FAILED:   'approved but could not be applied',
    }.get(req.status)
    if outcome:
        text = f'Your {label.lower()} for {req.employee.full_name} was {outcome}.'
        if req.status == PAR.STATUS_REJECTED and req.decision_note:
            text += f' Reason: {req.decision_note}'
    else:
        text = f'Your {label.lower()} for {req.employee.full_name} moved to the next approval step.'
    _notify(req.raised_by, f'{label} update', text, 'promotion', 'promotion',
            reference_id=str(req.pk), created_by=actor, category='approval')
