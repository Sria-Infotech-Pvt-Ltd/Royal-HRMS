import logging

from django.db import transaction
from django.db.models import Max, Q
from rest_framework import status
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView

from core.pagination import paginate, paginated_data
from core.responses import error, first_error, success

from ..models import (
    SEP_APPROVED, SEP_PENDING, SEP_STAGE2_PENDING,
    SEP_STAGE_HR, SEP_CLEARANCE_TYPE_CHOICES,
    SEPARATION_REASON_CHOICES, SEPARATION_TYPE_CHOICES,
    SeparationActivity, SeparationApprovalStage, SeparationClearance, SeparationRequest,
)
from ..serializers import SeparationRequestCreateSerializer, SeparationRequestSerializer

logger = logging.getLogger(__name__)

_ACTIVE_STATUSES = (SEP_PENDING, SEP_STAGE2_PENDING, SEP_APPROVED)


class SeparationTypeListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        types = [{'value': key, 'label': label} for key, label in SEPARATION_TYPE_CHOICES]
        return success('Separation types retrieved.', types)


class SeparationReasonListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        reasons = [{'value': key, 'label': label} for key, label in SEPARATION_REASON_CHOICES]
        return success('Separation reasons retrieved.', reasons)


def _has_perm(user, codename: str) -> bool:
    if not user or not user.role:
        return False
    if getattr(user, 'is_superuser', False):
        return True
    return user.role.role_permissions.filter(
        permission__codename__in={codename, 'settings.edit'}
    ).exists()


def _user_branch(user) -> str:
    return (getattr(user, 'branch', '') or '').strip()


def _approval_scope_filter(user) -> Q:
    """Scope filter for the HR/manager separation queue — excludes the viewer's own requests."""
    if _has_perm(user, 'settings.edit'):
        return ~Q(employee=user)
    if user.role and user.role.can_manage_team:
        return Q(employee__reporting_manager=user) & ~Q(employee=user)
    branch = _user_branch(user)
    branch_q = Q(employee__branch__iexact=branch) if branch else Q()
    return branch_q & ~Q(employee=user)


def _resolve_separation_chain(employee):
    """
    Build the approval chain for a separating employee, in action order —
    keyed off the SEPARATING employee's own role, not the requester's:

    - Manager (role.can_manage_team):   [HR, Branch Admin]           — 2 stages
    - HR-tier (see below):              [Branch Admin]               — 1 stage
    - Everyone else (regular employee): [Department Manager, HR]     — 2 stages

    "HR-tier" means the employee's own role holds separation.approve (or the
    settings.edit bypass) — i.e. the employee IS someone who'd normally be
    approving other people's separations (hr, branch_admin, system_admin).
    This check must run AFTER the can_manage_team check above, because every
    manager role is also granted separation.approve (accounts migration
    0063) — checking permission first would misroute every manager into the
    single-stage HR-tier branch instead of their own 2-stage one.

    The Manager and HR approver slots are left unresolved (None)
    whenever they can't be pinned to one specific person (no unit chief
    resolved, employee IS that chief, no HR assigned, etc.) — an
    unresolved stage then falls back to any separation.approve holder in the
    employee's branch (see _stage_actionable in serializers.py and
    _can_action_stage in views/separation_workflow.py). Branch Admin is
    always left unresolved for the same reason — it's a role-wide stage, not
    tied to one specific person.

    Returns [(stage_key, approver_or_None), ...] — one or two entries.
    """
    from ..models import SEP_STAGE_BRANCH_ADMIN, SEP_STAGE_MANAGER

    role = employee.role
    if role and role.can_manage_team:
        return [(SEP_STAGE_HR, employee.hr), (SEP_STAGE_BRANCH_ADMIN, None)]

    is_hr_tier = bool(
        role and role.role_permissions.filter(
            permission__codename__in={'separation.approve', 'settings.edit'}
        ).exists()
    )
    if is_hr_tier:
        return [(SEP_STAGE_BRANCH_ADMIN, None)]

    from apps.accounts.services_approval import resolve_employee_org_unit_chief
    chief = resolve_employee_org_unit_chief(employee)
    manager_approver = chief if (chief and chief.id != employee.id) else None
    return [(SEP_STAGE_MANAGER, manager_approver), (SEP_STAGE_HR, employee.hr)]


def _log(sep_request, user, message: str) -> None:
    SeparationActivity.objects.create(request=sep_request, actor=user, message=message)


class SeparationRequestListCreateView(APIView):
    permission_classes = [IsAuthenticated]
    parser_classes     = [MultiPartParser, FormParser, JSONParser]

    def get(self, request):
        has_manage = _has_perm(request.user, 'separation.approve')
        scope      = request.query_params.get('scope', '')
        qs_base    = SeparationRequest.objects.select_related(
            'employee', 'employee__reporting_manager', 'created_by',
        ).prefetch_related('approval_stages')

        employee_id_param = request.query_params.get('employee_id')
        if employee_id_param:
            if not (_has_perm(request.user, 'employees.view') or has_manage):
                return error('Permission denied.', http_status=status.HTTP_403_FORBIDDEN)
            from apps.accounts.models import User
            target_employee = User.objects.filter(employee_id=employee_id_param).first()
            if not target_employee:
                return error('Employee not found.', http_status=status.HTTP_404_NOT_FOUND)
            queryset = qs_base.filter(employee=target_employee)
        elif scope == 'team' and has_manage:
            queryset = qs_base.filter(_approval_scope_filter(request.user))
        else:
            queryset = qs_base.filter(employee=request.user)

        status_param = request.query_params.get('status')
        if status_param:
            queryset = queryset.filter(status__in=[s.strip() for s in status_param.split(',')])

        separation_type = request.query_params.get('separation_type')
        if separation_type:
            queryset = queryset.filter(separation_type=separation_type)

        queryset = queryset.order_by('-created_at')

        page_obj, paginator = paginate(queryset, request, default_page_size=20)
        serializer = SeparationRequestSerializer(page_obj.object_list, many=True, context={'request': request})
        return success('Separation requests retrieved.', paginated_data(paginator, page_obj, serializer.data))

    def post(self, request):
        target_employee = request.user
        employee_id      = (request.data.get('employee_id') or '').strip()
        if employee_id and employee_id != request.user.employee_id:
            if not _has_perm(request.user, 'employees.view'):
                return error('Permission denied.', http_status=status.HTTP_403_FORBIDDEN)
            from apps.accounts.models import User
            target_employee = User.objects.filter(employee_id=employee_id).first()
            if not target_employee:
                return error('Employee not found.', http_status=status.HTTP_404_NOT_FOUND)

        serializer = SeparationRequestCreateSerializer(data=request.data)
        if not serializer.is_valid():
            return error(first_error(serializer.errors))

        if SeparationRequest.objects.filter(employee=target_employee, status__in=_ACTIVE_STATUSES).exists():
            return error('This employee already has an active separation request.')

        with transaction.atomic():
            last_num = (
                SeparationRequest.objects.select_for_update().aggregate(n=Max('request_number'))['n'] or 0
            )
            sep_request = SeparationRequest.objects.create(
                employee=target_employee,
                request_number=last_num + 1,
                created_by=request.user,
                **serializer.validated_data,
            )
            chain = _resolve_separation_chain(target_employee)
            SeparationApprovalStage.objects.bulk_create([
                SeparationApprovalStage(request=sep_request, stage=stage, sequence=i + 1, approver=approver)
                for i, (stage, approver) in enumerate(chain)
            ])
            SeparationClearance.objects.bulk_create([
                SeparationClearance(request=sep_request, clearance_type=clearance_type)
                for clearance_type, _label in SEP_CLEARANCE_TYPE_CHOICES
            ])
            _log(sep_request, request.user, f'Separation request submitted by {request.user.full_name}.')

        logger.info(
            'Separation request %s created for %s by %s',
            sep_request.id, target_employee.email, request.user.email,
        )
        out = SeparationRequestSerializer(sep_request, context={'request': request})
        return success('Separation request submitted.', out.data, http_status=status.HTTP_201_CREATED)


class SeparationRequestDetailView(APIView):
    permission_classes = [IsAuthenticated]
    parser_classes     = [MultiPartParser, FormParser, JSONParser]

    def _get_object(self, request, request_id: str):
        try:
            sep_request = SeparationRequest.objects.select_related(
                'employee', 'employee__reporting_manager', 'created_by',
            ).prefetch_related('approval_stages').get(id=request_id)
        except SeparationRequest.DoesNotExist:
            return None, error('Separation request not found.', http_status=status.HTTP_404_NOT_FOUND)

        user    = request.user
        is_own  = sep_request.employee_id == user.id
        can_see = is_own or _has_perm(user, 'separation.approve') or _has_perm(user, 'employees.view')
        if not can_see:
            return None, error('Permission denied.', http_status=status.HTTP_403_FORBIDDEN)
        return sep_request, None

    def get(self, request, request_id: str):
        sep_request, err = self._get_object(request, request_id)
        if err:
            return err
        return success(
            'Separation request retrieved.',
            SeparationRequestSerializer(sep_request, context={'request': request}).data,
        )

    def patch(self, request, request_id: str):
        sep_request, err = self._get_object(request, request_id)
        if err:
            return err

        action = request.data.get('action', 'update')
        editable_statuses = (SEP_PENDING, SEP_STAGE2_PENDING)

        if action == 'cancel':
            if sep_request.employee_id != request.user.id:
                return error('Only the employee can cancel their own request.', http_status=status.HTTP_403_FORBIDDEN)
            if sep_request.status not in editable_statuses:
                return error('Only pending requests can be cancelled.')
            sep_request.status = 'cancelled'
            sep_request.save(update_fields=['status', 'updated_at'])
            _log(sep_request, request.user, f'Request cancelled by {request.user.full_name}.')
            logger.info('Separation request %s cancelled by %s', sep_request.id, request.user.email)
            return success(
                'Separation request cancelled.',
                SeparationRequestSerializer(sep_request, context={'request': request}).data,
            )

        # Default action ("update"): the employee edits their own still-open request.
        if sep_request.employee_id != request.user.id:
            return error('Only the employee can edit their own request.', http_status=status.HTTP_403_FORBIDDEN)
        if sep_request.status not in editable_statuses:
            return error('Only pending requests can be edited.')
        serializer = SeparationRequestCreateSerializer(sep_request, data=request.data, partial=True)
        if not serializer.is_valid():
            return error(first_error(serializer.errors))
        serializer.save()
        _log(sep_request, request.user, f'Request details updated by {request.user.full_name}.')
        logger.info('Separation request %s updated by %s', sep_request.id, request.user.email)
        return success(
            'Separation request updated.',
            SeparationRequestSerializer(sep_request, context={'request': request}).data,
        )

    def delete(self, request, request_id: str):
        if not _has_perm(request.user, 'separation.approve'):
            return error('Only HR can delete separation requests.', http_status=status.HTTP_403_FORBIDDEN)
        sep_request, err = self._get_object(request, request_id)
        if err:
            return err
        if sep_request.status == SEP_APPROVED:
            return error('Approved separation requests cannot be deleted.', http_status=status.HTTP_409_CONFLICT)
        sep_request.delete()
        logger.info('Separation request %s deleted by %s', request_id, request.user.email)
        return success('Separation request deleted.')
