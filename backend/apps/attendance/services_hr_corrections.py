"""
HR Attendance Correction Management services.

Handles submitting, listing, and approving/rejecting missed-punch correction
requests through a two-stage L1 (reporting manager) → L2 (HR) approval chain
— the same ApprovalWorkflowRule / EmployeeApprovalOverride mechanism used by
leave requests (workflow_type='attendance_correction'), so routing is
configurable from Settings → Approval Rules instead of hardcoded.

Approval creates the missing AttendancePunch(es) and reprocesses the day —
but only once the request reaches its FINAL approval (L1 approval with no
L2 configured, or L2 approval) — which changes the AttendanceRecord from
STATUS_INCOMPLETE → present/late and removes the employee from the
Un-Punches list automatically.
"""
from __future__ import annotations

import datetime
import logging
from zoneinfo import ZoneInfo

from django.contrib.auth import get_user_model
from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from apps.attendance.models import AttendanceCorrection, AttendancePunch

logger = logging.getLogger(__name__)
User = get_user_model()

_IST = ZoneInfo('Asia/Kolkata')


# ── Approval chain resolution (mirrors apps/hrms/views/leave.py) ──────────────

def _user_branch(user) -> str:
    return (getattr(user, 'branch', '') or '').strip()


def _resolve_approver(role, employee):
    """Resolve a Role FK to the actual User approver for a given employee."""
    if role is None:
        return None
    if role.can_manage_team:
        return getattr(employee, 'reporting_manager', None)
    return getattr(employee, 'hr', None)


def _resolve_approval_chain(employee):
    """
    Return (l1_approver, l2_approver) for an attendance correction request.
    Checks EmployeeApprovalOverride first, falls back to ApprovalWorkflowRule.
    """
    from apps.accounts.models import ApprovalWorkflowRule, EmployeeApprovalOverride

    workflow_type = ApprovalWorkflowRule.WORKFLOW_ATTENDANCE_CORRECTION

    override = EmployeeApprovalOverride.objects.filter(
        employee=employee, workflow_type=workflow_type
    ).first()
    if override:
        return override.l1_override, override.l2_override

    from core.cache_service import ApprovalWorkflowCacheService
    rule = ApprovalWorkflowCacheService.get_rule(workflow_type)
    if not rule:
        return None, None

    l1 = _resolve_approver(rule.l1_approver_role, employee) if rule.l1_approver_role else None
    l2 = _resolve_approver(rule.l2_approver_role, employee) if rule.l2_approver_role else None
    return l1, l2


def _has_perm(user, codename: str) -> bool:
    if not user or not user.role:
        return False
    if user.role.name == 'system_admin' or getattr(user, 'is_superuser', False):
        return True
    return user.role.role_permissions.filter(permission__codename=codename).exists()


def _can_hr_access_request(hr_user, correction: AttendanceCorrection) -> bool:
    """
    True when hr_user is the request's specifically assigned HR (l2_approver), or —
    for requests with no HR assigned at all — hr_user shares the employee's branch
    (or has no branch restriction). Mirrors leave.py's _can_hr_access_request: a
    branch can have several HR users, but each should only reach requests for
    their own assigned employees.
    """
    if correction.l2_approver_id:
        return correction.l2_approver_id == hr_user.id
    branch = _user_branch(hr_user)
    if not branch:
        return True
    return (getattr(correction.employee, 'branch', '') or '').strip() == branch


def _can_approve_at_stage(user, correction: AttendanceCorrection, stage: str) -> bool:
    """
    Mirrors leave.py's _can_approve_at_stage — enforces that only the
    designated approver for the current stage may act, so permission alone
    cannot let someone jump the queue or act at the wrong stage.
    """
    if _has_perm(user, 'settings.edit'):
        return True

    if stage == 'l1':
        if correction.l1_approver_id:
            return correction.l1_approver_id == user.id
        return False

    if stage == 'l2':
        if correction.l2_approver_id:
            return correction.l2_approver_id == user.id
        return _has_perm(user, 'attendance.create') and _can_hr_access_request(user, correction)

    return False


def _approval_scope_filter(user) -> Q:
    """
    Scope filter for who may see which correction requests in the review queue.
    can_manage_team   → requests where they are the designated L1 approver.
    attendance.create → requests where they are the designated l2_approver (the
                        employee's specifically assigned HR), plus — for
                        non-manager approvers only — orphaned requests (no HR
                        assigned) in their branch as a fallback. A branch can
                        have several HR users — each only reaches the
                        employees actually assigned to them.
    settings.edit     → all requests (admin override).

    can_manage_team and attendance.create are NOT mutually exclusive: the
    manager role also holds attendance.create (required to pass the
    approve-action's permission gate at L1). Checking attendance.create first
    would always route a manager into the L2/HR branch, hiding their L1 queue
    entirely — mirrors the identical fix in hrms/views/leave.py's
    _approval_scope_filter. Both scopes are combined via OR instead of
    short-circuited; the branch-wide orphan fallback is withheld from
    managers so attendance.create alone doesn't turn them into a shadow
    branch-wide HR queue.
    """
    if _has_perm(user, 'settings.edit'):
        return Q()

    is_manager = bool(user.role and user.role.can_manage_team)
    scope = Q(l1_approver=user) if is_manager else None

    if _has_perm(user, 'attendance.create'):
        l2_scope = Q(l2_approver=user)
        if not is_manager:
            branch = _user_branch(user)
            orphaned = Q(l2_approver__isnull=True)
            if branch:
                orphaned &= Q(employee__branch=branch)
            l2_scope |= orphaned
        scope = (scope | l2_scope) if scope is not None else l2_scope

    return scope if scope is not None else Q(pk=None)  # no other role gets a review queue


# ── Public API ─────────────────────────────────────────────────────────────────

def submit_correction(
    employee,
    date: datetime.date,
    punch_type: str,
    requested_in_time,
    requested_out_time,
    reason: str,
    notes: str,
) -> AttendanceCorrection:
    """
    Create a correction request, resolving and stamping its L1/L2 approval
    chain at submission time (mirrors LeaveRequest creation).

    Managers skip L1 — their own correction routes directly to HR (L2), same
    escalation rule leave requests use. Also escalates to L2 when the
    employee has no reporting manager set, so the request is never orphaned.
    """
    l1, l2 = _resolve_approval_chain(employee)

    if (employee.role and employee.role.can_manage_team) or l1 is None:
        initial_status = AttendanceCorrection.STATUS_L2_PENDING
        l1_approver    = None
        l2_approver    = l2
    else:
        initial_status = AttendanceCorrection.STATUS_PENDING
        l1_approver    = l1
        l2_approver    = l2

    return AttendanceCorrection.objects.create(
        employee=employee,
        date=date,
        punch_type=punch_type,
        requested_in_time=requested_in_time,
        requested_out_time=requested_out_time,
        reason=reason,
        notes=notes,
        status=initial_status,
        created_by=employee,
        l1_approver=l1_approver,
        l2_approver=l2_approver,
    )


def list_corrections(
    user,
    branch: str = '',
    department: str = '',
    status_filter: str = '',
) -> list[dict]:
    """
    Return correction requests visible to `user`, newest first.

    status_filter: 'pending' | 'l2_pending' | 'approved' | 'rejected' | '' (all)
    """
    employee_qs = User.objects.filter(is_active=True)
    if branch:
        employee_qs = employee_qs.filter(branch=branch)
    if department:
        employee_qs = employee_qs.filter(department=department)

    qs = (
        AttendanceCorrection.objects
        .filter(_approval_scope_filter(user))
        .filter(employee__in=employee_qs)
        .select_related('employee', 'reviewed_by', 'l1_approver', 'l2_approver')
        .order_by('-created_at')
    )
    if status_filter:
        qs = qs.filter(status=status_filter)

    return [_build_row(c, user) for c in qs]


def list_my_corrections(
    employee,
    status_filter: str = '',
    date_from: datetime.date | None = None,
    date_to: datetime.date | None = None,
) -> list[dict]:
    """
    Return `employee`'s own correction requests, newest first — for the
    employee-facing "My Corrections" screen (as opposed to list_corrections()
    above, which is scoped to what a manager/HR reviewer is allowed to act on).

    status_filter: 'pending' | 'l2_pending' | 'approved' | 'rejected' | '' (all)
    """
    qs = (
        AttendanceCorrection.objects
        .filter(employee=employee)
        .select_related('employee', 'reviewed_by', 'l1_approver', 'l2_approver')
        .order_by('-created_at')
    )
    if status_filter:
        qs = qs.filter(status=status_filter)
    if date_from:
        qs = qs.filter(date__gte=date_from)
    if date_to:
        qs = qs.filter(date__lte=date_to)

    return [_build_row(c) for c in qs]


def approve_correction(correction_id: str, actioning_user, remarks: str = '') -> dict:
    """Approve a correction at whichever stage it currently sits at."""
    return _act_on_correction(correction_id, actioning_user, approve=True, remarks=remarks)


def reject_correction(correction_id: str, actioning_user, remarks: str = '') -> dict:
    """Reject a correction at whichever stage it currently sits at."""
    return _act_on_correction(correction_id, actioning_user, approve=False, remarks=remarks)


# ── Private helpers ────────────────────────────────────────────────────────────

def _act_on_correction(correction_id: str, actioning_user, *, approve: bool, remarks: str = '') -> dict:
    from apps.attendance.services_attendance import AttendanceProcessorService

    with transaction.atomic():
        correction = _get_actionable(correction_id)

        if correction.status == AttendanceCorrection.STATUS_PENDING:
            stage = 'l1'
        elif correction.status == AttendanceCorrection.STATUS_L2_PENDING:
            stage = 'l2'
        else:
            raise ValueError('Correction not found or already reviewed.')

        if not _can_approve_at_stage(actioning_user, correction, stage):
            raise PermissionError(
                f'You are not authorised to act on this request at the {stage.upper()} stage.'
            )

        now = timezone.now()
        stage_status = AttendanceCorrection.STAGE_APPROVED if approve else AttendanceCorrection.STAGE_REJECTED
        is_final = False

        if stage == 'l1':
            correction.l1_approver    = actioning_user
            correction.l1_status      = stage_status
            correction.l1_remarks     = remarks
            correction.l1_actioned_at = now
            if not approve:
                correction.status = AttendanceCorrection.STATUS_REJECTED
                is_final = True
            elif correction.l2_approver_id:
                correction.status = AttendanceCorrection.STATUS_L2_PENDING
            else:
                correction.status = AttendanceCorrection.STATUS_APPROVED
                is_final = True
        else:  # l2
            correction.l2_approver    = actioning_user
            correction.l2_status      = stage_status
            correction.l2_remarks     = remarks
            correction.l2_actioned_at = now
            correction.status = AttendanceCorrection.STATUS_APPROVED if approve else AttendanceCorrection.STATUS_REJECTED
            is_final = True

        if is_final:
            correction.reviewed_by = actioning_user
            correction.reviewed_at = now

            if approve:
                if correction.punch_type in (AttendanceCorrection.PUNCH_IN, AttendanceCorrection.PUNCH_BOTH):
                    _create_punch(
                        correction.employee, correction.date,
                        correction.requested_in_time, AttendancePunch.PUNCH_IN,
                    )
                if correction.punch_type in (AttendanceCorrection.PUNCH_OUT, AttendanceCorrection.PUNCH_BOTH):
                    _create_punch(
                        correction.employee, correction.date,
                        correction.requested_out_time, AttendancePunch.PUNCH_OUT,
                    )
                AttendanceProcessorService.process_day(correction.employee, correction.date)

        correction.save()
        _write_correction_audit(correction, actioning_user, stage=stage, approved=approve)
        logger.info(
            'Correction %s %s at %s stage by %s (employee=%s date=%s)',
            correction.pk, stage_status, stage, actioning_user.pk, correction.employee_id, correction.date,
        )

    return _build_row(correction, actioning_user)


def _get_actionable(correction_id: str) -> AttendanceCorrection:
    try:
        return AttendanceCorrection.objects.select_related('employee', 'l1_approver', 'l2_approver').get(
            id=correction_id,
            status__in=[AttendanceCorrection.STATUS_PENDING, AttendanceCorrection.STATUS_L2_PENDING],
        )
    except AttendanceCorrection.DoesNotExist:
        raise ValueError('Correction not found or already reviewed.')


def _create_punch(
    employee,
    date: datetime.date,
    punch_time: datetime.time,
    punch_type: str,
) -> None:
    """Create a regularization punch. Skips silently if an identical one already exists."""
    punched_at = datetime.datetime.combine(date, punch_time).replace(tzinfo=_IST)
    AttendancePunch.objects.get_or_create(
        employee=employee,
        punched_at=punched_at,
        punch_type=punch_type,
        defaults={
            'source':          AttendancePunch.SOURCE_MANUAL,
            'attendance_mode': AttendancePunch.MODE_OFFICE,
        },
    )


def _write_correction_audit(correction: AttendanceCorrection, actioning_user, *, stage: str, approved: bool) -> None:
    """Write CORRECTION_APPROVED or CORRECTION_REJECTED audit entry."""
    from apps.attendance.models import AttendanceAuditLog, AttendanceRecord
    from apps.attendance.services_audit_log import write_audit_log

    record = AttendanceRecord.objects.filter(
        employee=correction.employee, date=correction.date,
    ).first()

    stage_label = 'Manager' if stage == 'l1' else 'HR'
    if approved:
        parts = []
        if correction.requested_in_time:
            parts.append(f'IN {correction.requested_in_time.strftime("%H:%M")}')
        if correction.requested_out_time:
            parts.append(f'OUT {correction.requested_out_time.strftime("%H:%M")}')
        new_value = ', '.join(parts) if parts else ''
        event  = AttendanceAuditLog.EVENT_CORRECTION_APPROVED
        action = f'Attendance correction approved by {stage_label}'
    else:
        new_value = ''
        event  = AttendanceAuditLog.EVENT_CORRECTION_REJECTED
        action = f'Attendance correction rejected by {stage_label}'

    write_audit_log(
        employee=correction.employee,
        date=correction.date,
        event=event,
        performed_by=actioning_user,
        record=record,
        new_value=new_value,
        action=action,
    )


def _build_row(c: AttendanceCorrection, user=None) -> dict:
    can_action = False
    if user and c.status == AttendanceCorrection.STATUS_PENDING:
        can_action = _can_approve_at_stage(user, c, 'l1')
    elif user and c.status == AttendanceCorrection.STATUS_L2_PENDING:
        can_action = _can_approve_at_stage(user, c, 'l2')

    employee = c.employee

    # Original (as-punched) times for that date, for context alongside what was requested.
    from apps.attendance.models import AttendanceRecord
    record = AttendanceRecord.objects.filter(employee=employee, date=c.date).only(
        'first_punch_in', 'last_punch_out',
    ).first()
    original_in  = record.first_punch_in.strftime('%H:%M') if record and record.first_punch_in else None
    original_out = record.last_punch_out.strftime('%H:%M') if record and record.last_punch_out else None

    return {
        'id':                 str(c.pk),
        'employee_id':        employee.employee_id or '',
        'name':               employee.full_name or '',
        'department':         employee.department or '',
        'branch':             employee.branch or '',
        'date':               c.date.strftime('%Y-%m-%d'),
        'punch_type':         c.punch_type,
        'original_in':        original_in,
        'original_out':       original_out,
        'requested_in':       c.requested_in_time.strftime('%H:%M') if c.requested_in_time else None,
        'requested_out':      c.requested_out_time.strftime('%H:%M') if c.requested_out_time else None,
        'reason':             c.reason,
        'notes':              c.notes or '',
        'status':             c.status,
        'l1_approver_name':   c.l1_approver.full_name if c.l1_approver else None,
        'l1_status':          c.l1_status,
        'l1_remarks':         c.l1_remarks or '',
        'l2_approver_name':   c.l2_approver.full_name if c.l2_approver else None,
        'l2_status':          c.l2_status,
        'l2_remarks':         c.l2_remarks or '',
        'can_action':         can_action,
        'reviewed_by':        c.reviewed_by.full_name if c.reviewed_by else None,
        'reviewed_at':        c.reviewed_at.strftime('%Y-%m-%d %H:%M') if c.reviewed_at else None,
        'created_at':         c.created_at.strftime('%Y-%m-%d %H:%M'),
    }
