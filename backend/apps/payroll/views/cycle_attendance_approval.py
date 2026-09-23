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



class AttendanceApprovalView(APIView):
    """L1 (manager) or L2 (HR) attendance approval for a payroll cycle.

    POST body: {"level": "L1", "comment": "optional note"}
               {"level": "L2", "comment": "optional note"}

    L1 logic:
      - Each manager (role.can_manage_team=True) has a ManagerAttendanceApproval row.
      - They must approve their own row.
      - L1 is complete only when ALL rows for the cycle are approved.
      - Fallback: if no manager rows exist, HR/sysadmin can approve L1 directly.

    L2 logic: unchanged — requires payroll.edit permission, runs after L1 is done.
    """

    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        cycle = get_object_or_404(PayrollCycle, pk=pk)

        if cycle.status != PayrollCycle.STATUS_ATTENDANCE_PENDING:
            return error('Attendance is not pending approval for this cycle.')

        settings_obj = PayrollSettings.objects.first()
        level = request.data.get('level', '').upper()
        note = request.data.get('comment', '').strip()
        self_approve = bool(request.data.get('self_approve', False))

        if level == 'L1':
            manager_row = ManagerAttendanceApproval.objects.filter(
                cycle=cycle, manager=request.user,
            ).first()

            if manager_row:
                if manager_row.approved_at:
                    return error('You have already approved attendance for this cycle.')
                manager_row.approved_at = timezone.now()
                manager_row.note = note
                update_fields = ['approved_at', 'note', 'updated_at']
                if self_approve:
                    manager_row.self_approved_at = timezone.now()
                    update_fields.append('self_approved_at')
                manager_row.save(update_fields=update_fields)
                logger.info('Cycle %s: manager %s approved L1', pk, request.user.email)
                AuditLog.objects.create(
                    user=request.user, action='payroll_attendance_l1_approved', module='payroll',
                    object_id=str(cycle.id), changes={'note': note},
                    branch=cycle.branch.branch_name if cycle.branch else '',
                    ip_address=get_client_ip(request),
                )
            else:
                # Fallback path: HR/sysadmin can approve L1 when no manager rows exist
                has_manager_rows = ManagerAttendanceApproval.objects.filter(cycle=cycle).exists()
                if has_manager_rows:
                    return error(
                        'You are not assigned to approve attendance for this cycle.',
                        http_status=403,
                    )
                if not _can_l2_approve(request.user):
                    return error('Manager or HR role required for L1 approval.', http_status=403)
                if cycle.attendance_approved_by_l1_id:
                    return error('L1 approval already recorded.')
                cycle.attendance_approved_by_l1 = request.user
                cycle.attendance_l1_approved_at = timezone.now()
                requires_l2 = settings_obj and settings_obj.approval_levels == PayrollSettings.APPROVAL_L1_L2
                if not requires_l2:
                    cycle.status = PayrollCycle.STATUS_ATTENDANCE_APPROVED
                cycle.save(update_fields=[
                    'attendance_approved_by_l1', 'attendance_l1_approved_at', 'status', 'updated_at',
                ])
                logger.info(
                    'Cycle %s: HR direct L1 approval by %s (no managers configured)',
                    pk, request.user.email,
                )
                AuditLog.objects.create(
                    user=request.user, action='payroll_attendance_l1_approved', module='payroll',
                    object_id=str(cycle.id), changes={'note': note, 'method': 'hr_direct_no_managers'},
                    branch=cycle.branch.branch_name if cycle.branch else '',
                    ip_address=get_client_ip(request),
                )
                return success('L1 attendance approval recorded.', PayrollCycleSerializer(cycle).data)

            # Check if all manager rows are now approved → complete L1
            pending_count = ManagerAttendanceApproval.objects.filter(
                cycle=cycle, approved_at__isnull=True,
            ).count()

            if pending_count == 0:
                cycle.attendance_approved_by_l1 = request.user
                cycle.attendance_l1_approved_at = timezone.now()
                requires_l2 = settings_obj and settings_obj.approval_levels == PayrollSettings.APPROVAL_L1_L2
                if not requires_l2:
                    cycle.status = PayrollCycle.STATUS_ATTENDANCE_APPROVED
                cycle.save(update_fields=[
                    'attendance_approved_by_l1', 'attendance_l1_approved_at', 'status', 'updated_at',
                ])
                logger.info('Cycle %s: all managers approved — L1 complete', pk)
                AuditLog.objects.create(
                    user=request.user, action='payroll_attendance_l1_complete', module='payroll',
                    object_id=str(cycle.id), changes={'requires_l2': requires_l2},
                    branch=cycle.branch.branch_name if cycle.branch else '',
                )
                if requires_l2:
                    try:
                        from apps.payroll.notifications import notify_l2_approval_required
                        notify_l2_approval_required(cycle)
                    except Exception:
                        logger.exception('Failed to send L2 payroll notifications for cycle %s', pk)

            return success('Your attendance approval recorded.', PayrollCycleSerializer(cycle).data)

        elif level == 'L2':
            if not _can_l2_approve(request.user):
                return error('HR admin role required for L2 approval.', http_status=403)
            if not cycle.attendance_approved_by_l1_id:
                return error('L1 approval must be completed first.')
            if cycle.attendance_approved_by_l2_id:
                return error('L2 approval already recorded.')

            cycle.attendance_approved_by_l2 = request.user
            cycle.attendance_l2_approved_at = timezone.now()
            cycle.status = PayrollCycle.STATUS_ATTENDANCE_APPROVED
            update_fields = ['attendance_approved_by_l2', 'attendance_l2_approved_at', 'status', 'updated_at']
            if self_approve:
                cycle.hr_self_approved_at = timezone.now()
                update_fields.append('hr_self_approved_at')
            cycle.save(update_fields=update_fields)
            logger.info('Cycle %s L2 attendance approved by %s', pk, request.user.email)
            AuditLog.objects.create(
                user=request.user, action='payroll_attendance_l2_approved', module='payroll',
                object_id=str(cycle.id), changes={'note': note},
                branch=cycle.branch.branch_name if cycle.branch else '',
                ip_address=get_client_ip(request),
            )
            return success('L2 attendance approval recorded.', PayrollCycleSerializer(cycle).data)

        return error('level must be "L1" or "L2".')


class ManagerAttendanceApprovalListView(APIView):
    """GET per-manager approval status for a cycle.

    Returns each manager row plus a summary (approved_count, total_count,
    all_approved, current_user_pending) so the frontend can render the
    per-manager status list without client-side computation.
    """

    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        cycle = get_object_or_404(PayrollCycle, pk=pk)
        if not _has_perm(request.user, 'payroll.view') and not _can_l1_approve(request.user):
            return error('Access denied.', http_status=403)

        # Auto-seed rows for cycles created before this feature existed.
        # Only runs when the cycle is still pending and no rows exist yet.
        if (
            cycle.status == PayrollCycle.STATUS_ATTENDANCE_PENDING
            and not ManagerAttendanceApproval.objects.filter(cycle=cycle).exists()
        ):
            manager_qs = User.objects.filter(
                is_active=True, role__can_manage_team=True,
            ).select_related('role')

            if cycle.branch:
                manager_qs = manager_qs.filter(branch=cycle.branch.branch_name)

            managers = list(manager_qs)
            if managers:
                ManagerAttendanceApproval.objects.bulk_create([
                    ManagerAttendanceApproval(cycle=cycle, manager=m)
                    for m in managers
                ], ignore_conflicts=True)
                logger.info(
                    'Cycle %s: auto-seeded %d manager approval rows (legacy cycle)',
                    pk, len(managers),
                )

        rows = ManagerAttendanceApproval.objects.filter(cycle=cycle).select_related('manager')
        serializer = ManagerAttendanceApprovalSerializer(rows, many=True)

        total    = rows.count()
        approved = rows.filter(approved_at__isnull=False).count()
        current_user_pending = rows.filter(
            manager=request.user, approved_at__isnull=True,
        ).exists()

        return success('Manager approval status retrieved.', {
            'approvals': serializer.data,
            'approved_count': approved,
            'total_count': total,
            'all_approved': total > 0 and approved == total,
            'current_user_pending': current_user_pending,
        })
