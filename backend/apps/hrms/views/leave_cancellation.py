"""
Cancelling an APPROVED leave (a pending one is still cancelled directly by
the employee — LeaveRequestDetailView.patch).

POST /api/leave/requests/<id>/cancellation/            employee: request it (reason required)
POST /api/leave/requests/<id>/cancellation/decision/   approver: approve | reject (remarks required to reject)
GET  /api/leave/cancellations/                         approver: cancellation requests I can decide

Rules
- Only an approved leave that has not started yet (start date after today).
- Decided by the leave's final approver: its HR (L2) approver when it had one,
  else its manager (L1) — the same authority checks as approval
  (_can_approve_at_stage: designated approver, HR fallback in branch, branch
  admin, admin, delegate, escalation target). Never by the employee.
- Approval: status → cancelled, the deducted days are returned to the balance,
  the planned "on leave" attendance days are removed, monthly statements resync.
- Rejection: the leave stays approved.
"""
from __future__ import annotations

import logging

from django.db import transaction
from django.db.models import F
from django.utils import timezone
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView

from core.permissions import has_perm
from core.responses import error, get_client_ip, success

from apps.hrms.models import REQ_APPROVED, REQ_CANCELLED, LeaveBalance, LeaveRequest
from apps.hrms.serializers import LeaveRequestSerializer

logger = logging.getLogger(__name__)


def decision_stage(lr: LeaveRequest) -> str:
    return 'l2' if (lr.l2_approver_id or lr.l2_actioned_at) else 'l1'


def can_decide(user, lr: LeaveRequest) -> bool:
    from apps.hrms.views.leave import _can_approve_at_stage
    if lr.employee_id == user.id or not has_perm(user, 'leave.approve'):
        return False
    return _can_approve_at_stage(user, lr, decision_stage(lr))


def _restore_balance(lr: LeaveRequest) -> float:
    """Inverse of _deduct_balance_safe: return the days that were deducted at approval."""
    if lr.is_lwp:
        return 0.0
    days = float(lr.total_days) - float(lr.lop_days or 0)
    if days > 0:
        LeaveBalance.objects.filter(employee=lr.employee, leave_type=lr.leave_type,
                                    year=lr.start_date.year).update(used_days=F('used_days') - days)
    return max(days, 0.0)


def _remove_planned_attendance(lr: LeaveRequest) -> int:
    """The future 'on leave' days written at approval (_sync_leave_attendance) — only days without punches."""
    from apps.attendance.models import AttendanceRecord
    deleted, _ = AttendanceRecord.objects.filter(
        employee=lr.employee, date__range=(lr.start_date, lr.end_date), date__gt=timezone.localdate(),
        status=AttendanceRecord.STATUS_ON_LEAVE, first_punch_in__isnull=True,
    ).delete()
    return deleted


def _audit(request, action, lr, extra=None):
    from apps.accounts.models import AuditLog
    AuditLog.objects.create(user=request.user, action=action, module='leave', object_id=str(lr.id),
                            changes={'employee': lr.employee.full_name, 'leave_type': lr.leave_type,
                                     'start_date': lr.start_date.isoformat(), 'end_date': lr.end_date.isoformat(),
                                     **(extra or {})},
                            branch=lr.employee.branch, ip_address=get_client_ip(request))


class LeaveCancellationRequestView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, request_id):
        lr = LeaveRequest.objects.select_related('employee').filter(id=request_id, employee=request.user).first()
        if lr is None:
            return error('Leave request not found.', http_status=status.HTTP_404_NOT_FOUND)
        if lr.status != REQ_APPROVED:
            return error('Only an approved leave needs a cancellation request — cancel a pending one directly.')
        if lr.start_date <= timezone.localdate():
            return error('This leave has already started. Contact HR to change it.')
        if lr.cancellation_status == LeaveRequest.CANCELLATION_REQUESTED:
            return error('A cancellation request is already waiting for approval.')
        reason = (request.data.get('reason') or '').strip()
        if len(reason) < 5:
            return error('Give a reason for cancelling.', data={'reason': ['Give a reason (at least 5 characters).']})
        lr.cancellation_status = LeaveRequest.CANCELLATION_REQUESTED
        lr.cancellation_reason = reason[:1000]
        lr.cancellation_requested_at = timezone.now()
        lr.cancellation_reviewed_by, lr.cancellation_reviewed_at, lr.cancellation_remarks = None, None, ''
        lr.save(update_fields=['cancellation_status', 'cancellation_reason', 'cancellation_requested_at',
                               'cancellation_reviewed_by', 'cancellation_reviewed_at', 'cancellation_remarks',
                               'updated_at'])
        _audit(request, 'leave_cancellation_requested', lr, {'reason': lr.cancellation_reason})
        return success('Cancellation requested. You will be notified once it is decided.',
                       LeaveRequestSerializer(lr, context={'request': request}).data)


class LeaveCancellationDecisionView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, request_id):
        action = request.data.get('action')
        remarks = (request.data.get('remarks') or '').strip()
        if action not in ('approve', 'reject'):
            return error('Action must be "approve" or "reject".')
        if action == 'reject' and not remarks:
            return error('Give a reason for rejecting — it is shown to the employee.',
                         data={'remarks': ['Required when rejecting.']})
        with transaction.atomic():
            lr = (LeaveRequest.objects.select_for_update(of=('self',)).select_related('employee', 'l1_approver', 'l2_approver')
                  .filter(id=request_id).first())
            if lr is None or lr.cancellation_status != LeaveRequest.CANCELLATION_REQUESTED or lr.status != REQ_APPROVED:
                return error('No cancellation request waiting for a decision.', http_status=404)
            if not can_decide(request.user, lr):
                return error('You are not authorised to decide this cancellation.', http_status=403)
            lr.cancellation_reviewed_by, lr.cancellation_reviewed_at = request.user, timezone.now()
            lr.cancellation_remarks = remarks[:1000]
            restored = 0.0
            if action == 'approve':
                restored = _restore_balance(lr)
                _remove_planned_attendance(lr)
                lr.cancellation_status, lr.status = LeaveRequest.CANCELLATION_APPROVED, REQ_CANCELLED
            else:
                lr.cancellation_status = LeaveRequest.CANCELLATION_REJECTED
            lr.save()
        if action == 'approve':
            from apps.hrms.views.leave import _after_request_closed, _invalidate_leave_balance_cache
            _invalidate_leave_balance_cache(lr)
            _after_request_closed(lr)
        _audit(request, f'leave_cancellation_{action}d', lr, {'remarks': remarks, 'days_restored': restored})
        msg = 'Cancellation approved — the leave is cancelled and the days are back in the balance.' \
            if action == 'approve' else 'Cancellation rejected — the leave stays approved.'
        return success(msg, LeaveRequestSerializer(lr, context={'request': request}).data)


class LeaveCancellationListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        if not has_perm(request.user, 'leave.approve'):
            return success('Cancellation requests.', [])
        rows = (LeaveRequest.objects.filter(status=REQ_APPROVED, cancellation_status=LeaveRequest.CANCELLATION_REQUESTED)
                .exclude(employee=request.user).select_related('employee', 'l1_approver', 'l2_approver')
                .order_by('cancellation_requested_at'))
        out = [r for r in rows if can_decide(request.user, r)]
        return success('Cancellation requests.', LeaveRequestSerializer(out, many=True, context={'request': request}).data)
