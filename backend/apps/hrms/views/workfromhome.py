import logging

from django.db.models import Q
from django.utils import timezone
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView

from core.pagination import paginate, paginated_data
from core.permissions import has_perm as _has_perm
from core.responses import error, first_error, get_client_ip, success

from ..models import (
    APPROVAL_APPROVED, APPROVAL_REJECTED,
    REQ_APPROVED, REQ_CANCELLED, REQ_L2_PENDING, REQ_PENDING, REQ_REJECTED,
    WorkFromHomeRequest,
)
from ..serializers import WorkFromHomeRequestCreateSerializer, WorkFromHomeRequestSerializer

logger = logging.getLogger(__name__)


def _resolve_approval_chain(employee):
    """Return (l1_approver, l2_approver) for a WFH request. See
    apps.accounts.services_approval for the shared implementation — also
    used by leave and attendance correction requests."""
    from apps.accounts.services_approval import resolve_approval_chain
    return resolve_approval_chain(employee, 'wfh')


def _user_branch(user) -> str:
    return (getattr(user, 'branch', '') or '').strip()


def _is_branch_admin(user) -> bool:
    return bool(user.role and getattr(user.role, 'can_manage_branch', False))


def _branch_admin_covers(user, employee) -> bool:
    branch = _user_branch(user)
    if not branch:
        return True
    return (getattr(employee, 'branch', '') or '').strip() == branch


def _can_hr_access_request(hr_user, wfh_request) -> bool:
    """Mirrors leave.py's _can_hr_access_request — same assigned-first,
    branch-fallback rule so the approval queue a user sees always matches
    what they can act on."""
    if _is_branch_admin(hr_user):
        return _branch_admin_covers(hr_user, wfh_request.employee)
    if wfh_request.l2_approver_id:
        return wfh_request.l2_approver_id == hr_user.id
    branch = _user_branch(hr_user)
    if not branch:
        return True
    return (getattr(wfh_request.employee, 'branch', '') or '').strip() == branch


def _can_approve_at_stage(user, wfh_request, stage: str) -> bool:
    """Mirrors leave.py's _can_approve_at_stage (see that module for the
    full reasoning) — swapped to wfh.approve as the fallback permission."""
    if _has_perm(user, 'settings.edit'):
        return True
    if _is_branch_admin(user):
        return _branch_admin_covers(user, wfh_request.employee)

    if stage == 'l1':
        if wfh_request.l1_approver_id:
            return wfh_request.l1_approver_id == user.id
        return False

    if stage == 'l2':
        if wfh_request.l2_approver_id:
            return wfh_request.l2_approver_id == user.id
        return _has_perm(user, 'wfh.approve') and _can_hr_access_request(user, wfh_request)

    return False


def _approval_scope_filter(user) -> 'Q':
    """Mirrors leave.py's _approval_scope_filter — see that module's
    docstring for the full reasoning behind each branch."""
    if _has_perm(user, 'settings.edit'):
        return ~Q(employee=user)

    if _is_branch_admin(user):
        branch = _user_branch(user)
        branch_q = Q(employee__branch__iexact=branch) if branch else Q()
        return branch_q & Q(status__in=[REQ_PENDING, REQ_L2_PENDING]) & ~Q(employee=user)

    is_manager = bool(user.role and user.role.can_manage_team)
    scope = Q(l1_approver=user, status=REQ_PENDING) if is_manager else None

    if _has_perm(user, 'wfh.approve'):
        l2_scope = Q(l2_approver=user, status=REQ_L2_PENDING)
        if not is_manager:
            branch = _user_branch(user)
            orphaned = Q(l2_approver__isnull=True, status=REQ_L2_PENDING)
            if branch:
                orphaned &= Q(employee__branch__iexact=branch)
            l2_scope |= orphaned
        scope = (scope | l2_scope) if scope is not None else l2_scope

    if scope is not None:
        return scope & ~Q(employee=user)
    return Q(employee=user)


class WorkFromHomeRequestListCreateView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        has_approve = _has_perm(request.user, 'wfh.approve')
        scope       = request.query_params.get('scope', '')

        qs_base = WorkFromHomeRequest.objects.select_related('employee', 'l1_approver', 'l2_approver')

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
            queryset = qs_base.filter(_approval_scope_filter(request.user))
        else:
            queryset = qs_base.filter(employee=request.user)

        req_status = request.query_params.get('status')
        if req_status:
            statuses = [s.strip() for s in req_status.split(',')]
            queryset = queryset.filter(status__in=statuses)

        queryset = queryset.order_by('-created_at')

        page_obj, paginator = paginate(queryset, request, default_page_size=20)
        serializer = WorkFromHomeRequestSerializer(page_obj.object_list, many=True, context={'request': request})
        return success('Work from home requests retrieved.', paginated_data(paginator, page_obj, serializer.data))

    def post(self, request):
        serializer = WorkFromHomeRequestCreateSerializer(data=request.data)
        if not serializer.is_valid():
            return error(first_error(serializer.errors))

        data  = serializer.validated_data
        start = data['start_date']
        end   = data['end_date']

        _ACTIVE_STATUSES = (REQ_PENDING, REQ_L2_PENDING, REQ_APPROVED)
        overlap = WorkFromHomeRequest.objects.filter(
            employee=request.user,
            status__in=_ACTIVE_STATUSES,
            start_date__lte=end,
            end_date__gte=start,
        ).exists()
        if overlap:
            return error(
                'You already have a work-from-home request for the selected date(s). '
                'Please cancel the existing request before applying again.'
            )

        # A day can't be both "on leave" and "working from home" — without
        # this, approving both independently leaves AttendanceRecord in a
        # contradictory state (status=on_leave, work_mode=wfh) since the two
        # write-throughs don't know about each other.
        from apps.hrms.models import LeaveRequest
        leave_overlap = LeaveRequest.objects.filter(
            employee=request.user,
            status__in=_ACTIVE_STATUSES,
            start_date__lte=end,
            end_date__gte=start,
        ).exists()
        if leave_overlap:
            return error(
                'You have a leave request overlapping the selected date(s). '
                'Cancel or wait for it to resolve before requesting work from home for the same dates.'
            )

        l1, l2 = _resolve_approval_chain(request.user)

        # Managers skip L1 — their request routes directly to HR (L2), same
        # as leave — and escalate to L2 when there's no reporting manager at
        # all, so the request is never orphaned with no one to act on it.
        if (request.user.role and request.user.role.can_manage_team) or l1 is None:
            initial_status = REQ_L2_PENDING
            l1_approver    = None
            l2_approver    = l2
        else:
            initial_status = REQ_PENDING
            l1_approver    = l1
            l2_approver    = l2

        wfh_request = WorkFromHomeRequest.objects.create(
            employee=request.user,
            start_date=start,
            end_date=end,
            reason=data.get('reason', ''),
            location_label=data.get('location_label', ''),
            latitude=data['latitude'],
            longitude=data['longitude'],
            l1_approver=l1_approver,
            l2_approver=l2_approver,
            status=initial_status,
        )

        logger.info('WFH request %s created by %s (%s to %s)', wfh_request.id, request.user.email, start, end)
        out = WorkFromHomeRequestSerializer(wfh_request, context={'request': request})
        return success('Work from home request submitted.', out.data, http_status=status.HTTP_201_CREATED)


class WorkFromHomeRequestDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def _get_request(self, request_id: str, user):
        try:
            wfh_request = WorkFromHomeRequest.objects.select_related(
                'employee', 'l1_approver', 'l2_approver'
            ).get(id=request_id)
        except WorkFromHomeRequest.DoesNotExist:
            return None, error('Work from home request not found.', http_status=status.HTTP_404_NOT_FOUND)

        is_own = wfh_request.employee_id == user.id
        # Own request, or able to act at either stage (covers L1 manager,
        # L2/HR, branch_admin, and settings.edit) — see the POST handler
        # above for why _can_hr_access_request alone isn't the right check.
        if not is_own and not (_can_approve_at_stage(user, wfh_request, 'l1') or _can_approve_at_stage(user, wfh_request, 'l2')):
            return None, error('Permission denied.', http_status=status.HTTP_403_FORBIDDEN)

        return wfh_request, None

    def get(self, request, request_id: str):
        wfh_request, err = self._get_request(request_id, request.user)
        if err:
            return err
        return success('Work from home request retrieved.', WorkFromHomeRequestSerializer(wfh_request, context={'request': request}).data)

    def patch(self, request, request_id: str):
        """Employee cancels their own pending request."""
        wfh_request, err = self._get_request(request_id, request.user)
        if err:
            return err

        if wfh_request.employee_id != request.user.id:
            return error('Only the employee can cancel their own request.', http_status=status.HTTP_403_FORBIDDEN)

        if wfh_request.status not in (REQ_PENDING, REQ_L2_PENDING):
            return error('Only pending requests can be cancelled.')

        wfh_request.status = REQ_CANCELLED
        wfh_request.save(update_fields=['status', 'updated_at'])
        logger.info('WFH request %s cancelled by %s', wfh_request.id, request.user.email)
        return success('Work from home request cancelled.', WorkFromHomeRequestSerializer(wfh_request, context={'request': request}).data)

    def put(self, request, request_id: str):
        return self.patch(request, request_id)

    def post(self, request, request_id: str):
        return self.patch(request, request_id)


class WorkFromHomeApprovalView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, request_id: str):
        if not _has_perm(request.user, 'wfh.approve'):
            return error('Permission denied.', http_status=status.HTTP_403_FORBIDDEN)
        try:
            wfh_request = WorkFromHomeRequest.objects.select_related(
                'employee', 'l1_approver', 'l2_approver'
            ).get(id=request_id)
        except WorkFromHomeRequest.DoesNotExist:
            return error('Work from home request not found.', http_status=status.HTTP_404_NOT_FOUND)
        # Whether this viewer could act at EITHER stage — not just
        # _can_hr_access_request alone, which only covers the L2/HR case
        # and would incorrectly deny a manager viewing a request they're
        # the designated L1 approver on (see the mirrored fix in the POST
        # handler below for the full explanation).
        if not (_can_approve_at_stage(request.user, wfh_request, 'l1') or _can_approve_at_stage(request.user, wfh_request, 'l2')):
            return error('Permission denied.', http_status=status.HTTP_403_FORBIDDEN)
        return success(
            'Work from home request retrieved.',
            WorkFromHomeRequestSerializer(wfh_request, context={'request': request}).data,
        )

    def post(self, request, request_id: str):
        if not _has_perm(request.user, 'wfh.approve'):
            return error('Permission denied.', http_status=status.HTTP_403_FORBIDDEN)

        try:
            wfh_request = WorkFromHomeRequest.objects.select_related('employee', 'l1_approver', 'l2_approver').get(id=request_id)
        except WorkFromHomeRequest.DoesNotExist:
            return error('Work from home request not found.', http_status=status.HTTP_404_NOT_FOUND)

        if wfh_request.employee_id == request.user.id:
            return error('You cannot approve or reject your own request.', http_status=status.HTTP_403_FORBIDDEN)
        # No blanket _can_hr_access_request gate here — that helper only
        # models L2/HR access (designated l2_approver, or branch fallback
        # when orphaned) and incorrectly rejects the L1 manager case, since
        # a manager is never the l2_approver. _can_approve_at_stage below
        # already checks the correct thing for whichever stage this request
        # is actually at (L1-designated, or L2-designated-or-branch-fallback),
        # so it's the sole authorization check.

        action  = request.data.get('action')
        remarks = (request.data.get('remarks') or request.data.get('reason') or '').strip()

        if action not in ('approve', 'reject'):
            return error('Action must be "approve" or "reject".')

        now = timezone.now()

        if wfh_request.status == REQ_PENDING:
            if not _can_approve_at_stage(request.user, wfh_request, 'l1'):
                return error(
                    'You are not authorised to act on this request at the L1 stage. '
                    'Only the designated reporting manager may approve or reject it.',
                    http_status=status.HTTP_403_FORBIDDEN,
                )
            wfh_request.l1_approver    = request.user
            wfh_request.l1_status      = APPROVAL_APPROVED if action == 'approve' else APPROVAL_REJECTED
            wfh_request.l1_remarks     = remarks
            wfh_request.l1_actioned_at = now

            if action == 'reject':
                wfh_request.status = REQ_REJECTED
            elif wfh_request.l2_approver_id:
                wfh_request.status = REQ_L2_PENDING
            else:
                wfh_request.status = REQ_APPROVED
                _sync_wfh_attendance(wfh_request)

        elif wfh_request.status == REQ_L2_PENDING:
            if not _can_approve_at_stage(request.user, wfh_request, 'l2'):
                return error(
                    'You are not authorised to act on this request at the L2 stage. '
                    'Only the designated HR approver may approve or reject it.',
                    http_status=status.HTTP_403_FORBIDDEN,
                )
            wfh_request.l2_approver    = request.user
            wfh_request.l2_status      = APPROVAL_APPROVED if action == 'approve' else APPROVAL_REJECTED
            wfh_request.l2_remarks     = remarks
            wfh_request.l2_actioned_at = now
            wfh_request.status = REQ_APPROVED if action == 'approve' else REQ_REJECTED
            if action == 'approve':
                _sync_wfh_attendance(wfh_request)

        else:
            return error(f'Cannot act on a request with status "{wfh_request.status}".')

        wfh_request.save()
        logger.info('WFH request %s %sd by %s', wfh_request.id, action, request.user.email)

        from apps.accounts.models import AuditLog
        AuditLog.objects.create(
            user=request.user, action=f'wfh_{action}d', module='wfh',
            object_id=str(wfh_request.id),
            changes={
                'employee': wfh_request.employee.full_name,
                'status':   wfh_request.status,
                'remarks':  remarks,
            },
            branch=wfh_request.employee.branch,
            ip_address=get_client_ip(request),
        )

        return success(f'Request {action}d.', WorkFromHomeRequestSerializer(wfh_request, context={'request': request}).data)


def _sync_wfh_attendance(wfh_request: WorkFromHomeRequest) -> None:
    """
    On approval, immediately flips work_mode='wfh' on any AttendanceRecord
    that already exists in range (e.g. approving a request that covers
    today or a past date already processed by a punch).

    Deliberately does NOT create placeholder records for future dates —
    unlike leave (where `status` becomes 'on_leave', the day-type itself),
    work_mode is orthogonal to presence/absence and there's no correct
    status to fabricate for a day that hasn't happened yet. Future dates
    get work_mode set correctly the moment AttendanceProcessorService.
    process_day actually builds their record (see services_attendance.py),
    which runs the same WorkFromHomeRequest.approved_for() lookup.
    """
    from apps.attendance.models import AttendanceRecord

    updated = AttendanceRecord.objects.filter(
        employee=wfh_request.employee,
        date__gte=wfh_request.start_date,
        date__lte=wfh_request.end_date,
    ).update(work_mode=AttendanceRecord.WORK_MODE_WFH)

    logger.info(
        'Synced work_mode=wfh on %d existing attendance record(s) for employee %s (request %s)',
        updated, wfh_request.employee.email, wfh_request.id,
    )
