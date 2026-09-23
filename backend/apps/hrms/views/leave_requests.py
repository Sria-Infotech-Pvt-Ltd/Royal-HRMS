import base64
import csv
import io
import logging
import time
from datetime import date, timedelta
from decimal import Decimal, InvalidOperation
from typing import TYPE_CHECKING

from django.db import transaction
from django.db.models import Count, F, Q, Sum
from django.http import HttpResponse
from django.utils import timezone
from rest_framework import status
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView

from core.pagination import paginate, paginated_data
from core.permissions import has_perm as _has_perm
from core.responses import error, first_error, get_client_ip, success

from ..models import (
    APPROVAL_APPROVED, APPROVAL_REJECTED,
    CARRY_FORWARD_UNLIMITED, CARRY_FORWARD_MANUAL,
    DURATION_FULL,
    LEAVE_LWP, LEAVE_TYPE_CHOICES,
    REQ_APPROVED, REQ_CANCELLED, REQ_L2_PENDING, REQ_PENDING, REQ_REJECTED,
    CarryForwardLog, LeaveBalance, LeavePolicy, LeaveRequest,
)
from ..serializers import (
    CarryForwardInputSerializer,
    CarryForwardLogSerializer,
    LeaveBalanceSerializer,
    LeavePolicyCreateSerializer,
    LeavePolicySerializer,
    LeavePolicyUpdateSerializer,
    LeaveRequestCreateSerializer,
    LeaveRequestSerializer,
)

if TYPE_CHECKING:
    from apps.accounts.models import User

logger = logging.getLogger(__name__)

from apps.hrms.views.leave_shared import *  # noqa: F401,F403

# ─── Leave Requests ────────────────────────────────────────────────────────────

class LeaveRequestListCreateView(APIView):
    permission_classes = [IsAuthenticated]
    parser_classes     = [MultiPartParser, FormParser, JSONParser]

    def get(self, request):
        if request.query_params.get('action') == 'preview':
            return _leave_preview(request)

        has_approve = _has_perm(request.user, 'leave.approve')
        scope       = request.query_params.get('scope', '')

        qs_base = LeaveRequest.objects.select_related('employee', 'l1_approver', 'l2_approver')

        employee_id_param = request.query_params.get('employee_id')
        if employee_id_param:
            if not (_has_perm(request.user, 'employees.view') or has_approve):
                return error('Permission denied.', http_status=status.HTTP_403_FORBIDDEN)
            from apps.accounts.models import User
            target_user = User.objects.filter(employee_id=employee_id_param).first()
            if not target_user:
                return error('Employee not found.', http_status=status.HTTP_404_NOT_FOUND)
            queryset = qs_base.filter(employee=target_user)
        elif scope == 'team' and has_approve:
            # Approval queue — scoped by role, own requests excluded
            queryset = qs_base.filter(_approval_scope_filter(request.user))
        else:
            # Default: return the requesting user's own requests only
            queryset = qs_base.filter(employee=request.user)

        leave_type = request.query_params.get('leave_type')
        if leave_type:
            queryset = queryset.filter(leave_type=leave_type)

        req_status = request.query_params.get('status')
        if req_status:
            statuses = [s.strip() for s in req_status.split(',')]
            queryset = queryset.filter(status__in=statuses)

        year = request.query_params.get('year')
        if year:
            queryset = queryset.filter(start_date__year=year)

        branch = request.query_params.get('branch')
        if branch and _has_perm(request.user, 'settings.edit'):
            queryset = queryset.filter(employee__branch__iexact=branch)

        department = request.query_params.get('department')
        if department and has_approve:
            queryset = queryset.filter(employee__department__iexact=department)

        queryset = queryset.order_by('-created_at')

        page_obj, paginator = paginate(queryset, request, default_page_size=20)
        serializer = LeaveRequestSerializer(page_obj.object_list, many=True, context={'request': request})
        return success('Leave requests retrieved.', paginated_data(paginator, page_obj, serializer.data))

    def post(self, request):
        serializer = LeaveRequestCreateSerializer(data=request.data)
        if not serializer.is_valid():
            return error(first_error(serializer.errors))

        data       = serializer.validated_data
        start      = data['start_date']
        end        = data['end_date']
        duration   = data.get('duration', 'full_day')
        leave_type = data['leave_type']

        from core.cache_service import LeavePolicyCacheService
        policy     = LeavePolicyCacheService.get(leave_type)
        total_days = _calc_working_days(start, end, duration, policy, request.user)

        if total_days <= 0:
            return error(_zero_working_days_reason(start, end, policy, request.user))

        if policy:
            today   = timezone.localdate()
            err_msg = _validate_leave_policy(
                policy, request.user, duration, total_days,
                start, end, data.get('document'), today,
            )
            if err_msg:
                return error(err_msg)

        _ACTIVE_STATUSES = (REQ_PENDING, REQ_L2_PENDING, REQ_APPROVED)
        year = start.year

        # Whole thing (overlap checks + balance check + creation) wrapped in
        # one transaction, locking the employee's own User row as a
        # stand-in mutex first — plain .exists() overlap checks with no lock
        # left a real (if narrow) window where two near-simultaneous
        # submissions from the same employee could each see no overlap and
        # both get created, since a genuinely first-ever submission has no
        # request row yet to lock. The User row always exists, so this
        # closes that gap too, not just the balance-overdraw case the lock
        # below already covered.
        lop_days = 0.0
        with transaction.atomic():
            from apps.accounts.models import User
            User.objects.select_for_update().get(pk=request.user.pk)

            overlap = LeaveRequest.objects.filter(
                employee=request.user,
                status__in=_ACTIVE_STATUSES,
                start_date__lte=end,
                end_date__gte=start,
            ).exists()
            if overlap:
                return error(
                    'You already have a leave request for the selected date(s). '
                    'Please modify or cancel the existing request before applying again.'
                )

            # Symmetric with the check apps/hrms/views/workfromhome.py's create
            # runs against LeaveRequest — a day can't be both "on leave" and
            # "working from home"; without this, approving both independently
            # leaves AttendanceRecord in a contradictory state (status=on_leave,
            # work_mode=wfh) since the two write-throughs don't know about
            # each other.
            from ..models import WorkFromHomeRequest
            wfh_overlap = WorkFromHomeRequest.objects.filter(
                employee=request.user,
                status__in=_ACTIVE_STATUSES,
                start_date__lte=end,
                end_date__gte=start,
            ).exists()
            if wfh_overlap:
                return error(
                    'You have a work-from-home request overlapping the selected date(s). '
                    'Cancel or wait for it to resolve before applying for leave on the same dates.'
                )

            if leave_type != LEAVE_LWP:
                balance = (
                    LeaveBalance.objects
                    .select_for_update()
                    .filter(employee=request.user, leave_type=leave_type, year=year)
                    .first()
                )
                if not balance:
                    return error(f'No leave balance found for {leave_type} in {year}. Contact HR.')
                available = float(balance.total_days - balance.used_days)
                if total_days > available:
                    if policy and policy.convert_to_lop:
                        # Use available balance; excess days become LOP — leave_type stays unchanged
                        lop_days = round(total_days - available, 1)
                    elif policy and policy.allow_negative_balance:
                        pass  # allow overdraft
                    else:
                        return error(f'Insufficient balance. You have {available} day(s) available.')

            l1, l2 = _resolve_approval_chain(request.user)

            # Managers skip L1 — their leave routes directly to HR (L2).
            # Also escalate to L2 when the employee has no reporting manager set,
            # so the request is never orphaned with no one to act on it.
            if (request.user.role and request.user.role.can_manage_team) or l1 is None:
                initial_status = REQ_L2_PENDING
                l1_approver    = None
                l2_approver    = l2
            else:
                initial_status = REQ_PENDING
                l1_approver    = l1
                l2_approver    = l2

            leave_request = LeaveRequest.objects.create(
                employee=request.user,
                leave_type=leave_type,
                duration=duration,
                start_date=start,
                end_date=end,
                total_days=total_days,
                lop_days=lop_days,
                reason=data.get('reason', ''),
                contact_during_leave=data.get('contact_during_leave', ''),
                handover_to=data.get('handover_to', ''),
                handover_notes=data.get('handover_notes', ''),
                document=data.get('document'),
                is_lwp=(leave_type == LEAVE_LWP),
                l1_approver=l1_approver,
                l2_approver=l2_approver,
                status=initial_status,
            )

        logger.info('Leave request %s created by %s (%s, %s days)', leave_request.id, request.user.email, leave_type, total_days)
        out = LeaveRequestSerializer(leave_request, context={'request': request})
        return success('Leave request submitted.', out.data, http_status=status.HTTP_201_CREATED)


class LeaveRequestDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def _get_request(self, request_id: str, user):
        try:
            leave_request = LeaveRequest.objects.select_related(
                'employee', 'l1_approver', 'l2_approver'
            ).get(id=request_id)
        except LeaveRequest.DoesNotExist:
            return None, error('Leave request not found.', http_status=status.HTTP_404_NOT_FOUND)

        has_approve = _has_perm(user, 'leave.approve')
        if not has_approve and leave_request.employee_id != user.id:
            return None, error('Permission denied.', http_status=status.HTTP_403_FORBIDDEN)
        if has_approve and not _can_hr_access_request(user, leave_request):
            return None, error('Permission denied.', http_status=status.HTTP_403_FORBIDDEN)

        return leave_request, None

    def get(self, request, request_id: str):
        leave_request, err = self._get_request(request_id, request.user)
        if err:
            return err
        return success('Leave request retrieved.', LeaveRequestSerializer(leave_request, context={'request': request}).data)

    def patch(self, request, request_id: str):
        """Employee cancels their own pending request."""
        leave_request, err = self._get_request(request_id, request.user)
        if err:
            return err

        if leave_request.employee_id != request.user.id:
            return error('Only the employee can cancel their own request.', http_status=status.HTTP_403_FORBIDDEN)

        if leave_request.status not in (REQ_PENDING, REQ_L2_PENDING):
            return error('Only pending requests can be cancelled.')

        leave_request.status = REQ_CANCELLED
        leave_request.save(update_fields=['status', 'updated_at'])
        logger.info('Leave request %s cancelled by %s', leave_request.id, request.user.email)
        return success('Leave request cancelled.', LeaveRequestSerializer(leave_request, context={'request': request}).data)

    def put(self, request, request_id: str):
        return self.patch(request, request_id)

    def post(self, request, request_id: str):
        return self.patch(request, request_id)

    def delete(self, request, request_id: str):
        if not _has_perm(request.user, 'leave.approve'):
            return error('Only HR can delete leave requests.', http_status=status.HTTP_403_FORBIDDEN)
        leave_request, err = self._get_request(request_id, request.user)
        if err:
            return err
        if leave_request.status == REQ_APPROVED:
            return error(
                'Approved leave requests cannot be deleted.',
                http_status=status.HTTP_409_CONFLICT,
            )
        leave_request.delete()
        logger.info('Leave request %s deleted by %s', request_id, request.user.email)
        return success('Leave request deleted.')


class LeaveApprovalView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, request_id: str):
        if not _has_perm(request.user, 'leave.approve'):
            return error('Permission denied.', http_status=status.HTTP_403_FORBIDDEN)
        try:
            leave_request = LeaveRequest.objects.select_related(
                'employee', 'l1_approver', 'l2_approver'
            ).get(id=request_id)
        except LeaveRequest.DoesNotExist:
            return error('Leave request not found.', http_status=status.HTTP_404_NOT_FOUND)
        # Viewing isn't tied to one stage the way acting is — authorised if
        # the user could act at *either* stage (designated L1 approver,
        # designated L2 approver, or the branch fallback when no L2 is
        # assigned). Checking only l2_approver_id here (as this used to)
        # hid the request entirely from its own designated L1 approver
        # whenever an L2 approver was also assigned — see the matching fix
        # in post() below.
        can_view = (
            _can_approve_at_stage(request.user, leave_request, 'l1')
            or _can_approve_at_stage(request.user, leave_request, 'l2')
        )
        if not can_view:
            return error('Permission denied.', http_status=status.HTTP_403_FORBIDDEN)
        return success(
            'Leave request retrieved.',
            LeaveRequestSerializer(leave_request, context={'request': request}).data,
        )

    def post(self, request, request_id: str):
        if not _has_perm(request.user, 'leave.approve'):
            return error('Permission denied.', http_status=status.HTTP_403_FORBIDDEN)

        action  = request.data.get('action')
        remarks = (request.data.get('remarks') or request.data.get('reason') or '').strip()

        if action not in ('approve', 'reject'):
            return error('Action must be "approve" or "reject".')

        now = timezone.now()
        balance_error = None

        # Wrapped in a transaction with a row lock on both the request itself
        # and the balance (see _deduct_balance_safe) — without locking the
        # request, two concurrent clicks/approvers on the SAME request could
        # both read status=PENDING, both pass the stage check, and both
        # mutate+save (double-firing the audit log, or double-deducting the
        # balance if the first commit's lock release lets the second run
        # through _deduct_balance_safe right behind it). Locking the balance
        # alone (as before) only stopped two DIFFERENT requests from jointly
        # overdrawing — not the same request being processed twice.
        # select_for_update(of=('self',)) since l1_approver/l2_approver are
        # nullable FKs — select_related's join to them is a LEFT OUTER JOIN,
        # and Postgres rejects FOR UPDATE across the nullable side of one
        # unless scoped to just the base table via `of`.
        with transaction.atomic():
            try:
                leave_request = (
                    LeaveRequest.objects
                    .select_related('employee', 'l1_approver', 'l2_approver')
                    .select_for_update(of=('self',))
                    .get(id=request_id)
                )
            except LeaveRequest.DoesNotExist:
                return error('Leave request not found.', http_status=status.HTTP_404_NOT_FOUND)

            if leave_request.employee_id == request.user.id:
                return error('You cannot approve or reject your own leave request.', http_status=status.HTTP_403_FORBIDDEN)
            # No blanket branch/HR-assignment gate here — _can_approve_at_stage
            # below already authorises both stages correctly (l1: designated
            # reporting manager; l2: designated HR, or any leave.approve holder
            # in-branch when no HR is assigned). A gate like the one this
            # replaced, keyed only on l2_approver_id, rejected every legitimate
            # L1 (manager) approver outright whenever the request also had an
            # L2 approver assigned — i.e. on almost every real request, since
            # HR is normally always configured as the L2 fallback.

            if leave_request.status == REQ_PENDING:
                if not _can_approve_at_stage(request.user, leave_request, 'l1'):
                    return error(
                        'You are not authorised to act on this request at the L1 stage. '
                        'Only the designated reporting manager may approve or reject it.',
                        http_status=status.HTTP_403_FORBIDDEN,
                    )
                leave_request.l1_approver    = request.user
                leave_request.l1_status      = APPROVAL_APPROVED if action == 'approve' else APPROVAL_REJECTED
                leave_request.l1_remarks     = remarks
                leave_request.l1_actioned_at = now

                if action == 'reject':
                    leave_request.status = REQ_REJECTED
                elif leave_request.l2_approver_id:
                    leave_request.status = REQ_L2_PENDING
                else:
                    # No L2 configured — L1 approval is final.
                    leave_request.status = REQ_APPROVED
                    balance_error = _deduct_balance_safe(leave_request)
                    if not balance_error:
                        _sync_leave_attendance(leave_request)

            elif leave_request.status == REQ_L2_PENDING:
                if not _can_approve_at_stage(request.user, leave_request, 'l2'):
                    return error(
                        'You are not authorised to act on this request at the L2 stage. '
                        'Only the designated HR approver may approve or reject it.',
                        http_status=status.HTTP_403_FORBIDDEN,
                    )
                leave_request.l2_approver    = request.user
                leave_request.l2_status      = APPROVAL_APPROVED if action == 'approve' else APPROVAL_REJECTED
                leave_request.l2_remarks     = remarks
                leave_request.l2_actioned_at = now
                leave_request.status = REQ_APPROVED if action == 'approve' else REQ_REJECTED
                if action == 'approve':
                    balance_error = _deduct_balance_safe(leave_request)
                    if not balance_error:
                        _sync_leave_attendance(leave_request)

            else:
                return error(f'Cannot act on a request with status "{leave_request.status}".')

            if balance_error:
                # Marks the transaction for rollback without raising — undoes
                # everything in this block, including the approver/status
                # fields already set above, so the request stays exactly as
                # it was and is ready to retry once the approver has seen why.
                transaction.set_rollback(True)
            else:
                leave_request.save()

        if balance_error:
            return error(balance_error)

        logger.info('Leave request %s %sd by %s', leave_request.id, action, request.user.email)

        from apps.accounts.models import AuditLog
        AuditLog.objects.create(
            user=request.user, action=f'leave_{action}d', module='leave',
            object_id=str(leave_request.id),
            changes={
                'employee':  leave_request.employee.full_name,
                'leave_type': leave_request.leave_type,
                'status':    leave_request.status,
                'remarks':   remarks,
            },
            branch=leave_request.employee.branch,
            ip_address=get_client_ip(request),
        )

        from apps.dashboard.views.overview import push_leave_update
        push_leave_update(request.user.id)

        return success(f'Request {action}d.', LeaveRequestSerializer(leave_request, context={'request': request}).data)






