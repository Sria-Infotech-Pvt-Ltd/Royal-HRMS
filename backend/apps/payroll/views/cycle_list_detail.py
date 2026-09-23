import logging
from collections import defaultdict
from datetime import date
from decimal import Decimal

from django.db import transaction
from django.utils import timezone
from django.utils.dateparse import parse_date
from django.shortcuts import get_object_or_404
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated

from core.responses import success, error, get_client_ip
from core.pagination import paginate, paginated_data
from core.permissions import has_perm as _has_perm
from apps.payroll.models import (
    PayrollCycle,
    PayrollSettings,
    EmployeePayslip,
    EmployeeSalaryConfig,
    SalaryStructure,
    SalaryComponent,
    StatutoryConfig,
    PayrollAdjustment,
    ManagerAttendanceApproval,
    SalaryTransferBatch,
    BranchPayrollConfig,
    EmployeeTaxDeclaration,
)
from apps.payroll.serializers import (
    PayrollCycleSerializer,
    ManagerAttendanceApprovalSerializer,
)
from apps.payroll.services_income_tax import estimate_monthly_tds
from apps.accounts.models import AuditLog, User
from apps.attendance.models import AttendanceRecord, AttendanceSettings, AttendanceLateMarkRules
from apps.branch.models import Branch

logger = logging.getLogger(__name__)

from apps.payroll.views.shared import *  # noqa: F401,F403

























class PayrollCycleListView(APIView):
    """List all payroll cycles / create a new one."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        if not _has_perm(request.user, 'payroll.view'):
            return error('Only HR admin can view payroll cycles.', http_status=403)

        cycles = PayrollCycle.objects.select_related(
            'created_by', 'branch',
        ).order_by('-cycle_start')

        if not _is_admin(request.user):
            branch_obj = _resolve_user_branch(request.user)
            if branch_obj is None:
                return error(
                    'Your account is not assigned to a branch. Contact an administrator.',
                    http_status=400,
                )
            cycles = cycles.filter(branch=branch_obj)

        page_obj, paginator = paginate(cycles, request)
        serializer = PayrollCycleSerializer(page_obj.object_list, many=True)
        return success(
            'Payroll cycles retrieved.',
            paginated_data(paginator, page_obj, serializer.data),
        )

    def post(self, request):
        if not _has_perm(request.user, 'payroll.create'):
            return error('Only HR admin can create payroll cycles.', http_status=403)

        # parse_date() (not raw strings) — PayrollCycle.objects.create() below
        # doesn't run full_clean(), so an unparsed string would sit on the
        # in-memory `cycle.cycle_start` as a plain str; notify_l1_approval_required()
        # immediately after calls .strftime() on it and crashes (silently, since
        # the seeding block below is wrapped in a broad except) — every real
        # cycle created through this endpoint has failed to notify its manager.
        cycle_start = parse_date(request.data.get('cycle_start') or '')
        cycle_end   = parse_date(request.data.get('cycle_end') or '')
        pay_date    = parse_date(request.data.get('pay_date') or '')

        if not all([cycle_start, cycle_end, pay_date]):
            return error('cycle_start, cycle_end, and pay_date are required and must be valid YYYY-MM-DD dates.')

        # Resolve branch: admin may pass branch_id, HR uses their own branch
        if _is_admin(request.user):
            branch_id = request.data.get('branch_id')
            if branch_id:
                branch_obj = Branch.objects.filter(pk=branch_id, status=Branch.STATUS_ACTIVE).first()
                if not branch_obj:
                    return error('Selected Company Code not found or inactive.')
            else:
                branch_obj = None  # admin global cycle (legacy path, no branch restriction)
        else:
            branch_obj = _resolve_user_branch(request.user)
            if branch_obj is None:
                return error(
                    'Your account is not assigned to a branch. Contact an administrator.',
                    http_status=400,
                )

        # Prevent overlapping cycles within the same branch (branch-scoped uniqueness)
        overlap_qs = PayrollCycle.objects.filter(
            cycle_start__lte=cycle_end,
            cycle_end__gte=cycle_start,
        ).exclude(status=PayrollCycle.STATUS_CANCELLED)

        if branch_obj is not None:
            overlap_qs = overlap_qs.filter(branch=branch_obj)
        else:
            overlap_qs = overlap_qs.filter(branch__isnull=True)

        if overlap_qs.exists():
            branch_label = f' in {branch_obj.branch_name}' if branch_obj else ''
            return error(
                f'A payroll cycle already exists for this period{branch_label}.'
                ' Cancel the existing cycle first.',
            )

        cycle = PayrollCycle.objects.create(
            cycle_start=cycle_start,
            cycle_end=cycle_end,
            pay_date=pay_date,
            branch=branch_obj,
            status=PayrollCycle.STATUS_ATTENDANCE_PENDING,
            created_by=request.user,
            notes=request.data.get('notes', ''),
        )
        logger.info(
            'PayrollCycle %s created by %s (branch: %s)',
            cycle.id, request.user.email,
            branch_obj.branch_name if branch_obj else 'global',
        )
        AuditLog.objects.create(
            user=request.user, action='payroll_cycle_created', module='payroll',
            object_id=str(cycle.id),
            changes={
                'cycle_start': str(cycle_start), 'cycle_end': str(cycle_end),
                'branch': branch_obj.branch_name if branch_obj else 'global',
            },
            branch=branch_obj.branch_name if branch_obj else '',
            ip_address=get_client_ip(request),
        )

        # Seed one approval row per active manager in this branch (or all if global)
        try:
            manager_qs = User.objects.filter(
                is_active=True, role__can_manage_team=True,
            ).exclude(pk=request.user.pk).select_related('role')

            if branch_obj is not None:
                manager_qs = manager_qs.filter(branch=branch_obj.branch_name)

            managers = list(manager_qs)

            ManagerAttendanceApproval.objects.bulk_create([
                ManagerAttendanceApproval(cycle=cycle, manager=m)
                for m in managers
            ])

            from apps.payroll.notifications import notify_l1_approval_required
            notify_l1_approval_required(cycle)
        except Exception:
            logger.exception(
                'Failed to seed manager approvals or send notifications for cycle %s', cycle.id,
            )

        return success('Payroll cycle created.', PayrollCycleSerializer(cycle).data, http_status=201)


class PayrollCycleDetailView(APIView):
    """Retrieve a single payroll cycle."""

    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        if not _has_perm(request.user, 'payroll.view'):
            return error('Access denied.', http_status=403)

        cycle = get_object_or_404(
            PayrollCycle.objects.select_related(
                'created_by',
                'branch',
                'attendance_approved_by_l1',
                'attendance_approved_by_l2',
                'marked_paid_by',
            ),
            pk=pk,
        )

        # HR can only access cycles for their own branch
        if not _is_admin(request.user) and cycle.branch:
            branch_obj = _resolve_user_branch(request.user)
            if branch_obj is None or cycle.branch_id != branch_obj.pk:
                return error('Access denied.', http_status=403)

        return success('Payroll cycle retrieved.', PayrollCycleSerializer(cycle).data)


class BranchPayrollStatusView(APIView):
    """Branch payroll overview: global admins see every active branch with its
    latest non-cancelled cycle status; branch-scoped users (branch_admin, HR)
    see only their own assigned branch."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        if not _has_perm(request.user, 'payroll.view'):
            return error('Access denied.', http_status=403)

        if _is_admin(request.user):
            branches = Branch.objects.filter(status=Branch.STATUS_ACTIVE).order_by('branch_name')
        else:
            branch_obj = _resolve_user_branch(request.user)
            if branch_obj is None:
                return error(
                    'Your account is not assigned to a branch. Contact an administrator.',
                    http_status=400,
                )
            branches = Branch.objects.filter(pk=branch_obj.pk)

        result = []
        for branch in branches:
            latest = (
                PayrollCycle.objects
                .filter(branch=branch)
                .exclude(status=PayrollCycle.STATUS_CANCELLED)
                .order_by('-cycle_start')
                .first()
            )
            result.append({
                'branch_id':   str(branch.id),
                'branch_name': branch.branch_name,
                'branch_code': getattr(branch, 'branch_code', ''),
                'status':      latest.status if latest else None,
                'cycle_id':    str(latest.id) if latest else None,
                'cycle_start': str(latest.cycle_start) if latest else None,
                'cycle_end':   str(latest.cycle_end) if latest else None,
                'paid_at':     latest.paid_at.isoformat() if latest and latest.paid_at else None,
            })

        return success('Company Code payroll status retrieved.', result)
