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



class ProcessPayrollView(APIView):
    """Trigger payroll calculation for all active employees in a cycle.

    Resolves each employee's salary structure via:
    1. EmployeeSalaryConfig (personal override) if active
    2. BranchPayrollConfig.salary_structure (branch-level)
    3. SalaryStructure.is_default (company default fallback)

    Statutory deductions (PF, ESI, PT, LWF) are applied per the employee's
    branch state using StatutoryConfig.
    """

    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        if not _has_perm(request.user, 'payroll.edit'):
            return error('Only HR admin can process payroll.', http_status=403)

        cycle = get_object_or_404(PayrollCycle, pk=pk)

        # HR can only process cycles for their own branch.
        # Guard must not short-circuit on cycle.branch being None — a NULL-branch
        # (global/legacy) cycle must still be blocked for non-admins, not opened.
        if not _is_admin(request.user):
            branch_obj = _resolve_user_branch(request.user)
            if branch_obj is None or cycle.branch_id != branch_obj.pk:
                return error('You can only process payroll for your own Company Code.', http_status=403)

        is_reprocess = cycle.status == PayrollCycle.STATUS_PAYSLIPS_GENERATED
        if cycle.status not in (
            PayrollCycle.STATUS_ATTENDANCE_APPROVED,
            PayrollCycle.STATUS_PAYSLIPS_GENERATED,
        ):
            return error('Attendance must be approved before processing payroll.')

        # Optional employee selection — omitted/null preserves the original
        # behavior exactly (every eligible employee). An explicit empty list
        # is rejected rather than silently treated as "everyone", since that
        # would be an easy, dangerous footgun for a caller that meant to
        # select nobody. An unknown employee code is rejected too; a real
        # employee code that just doesn't fall in this cycle's eligible
        # population (wrong branch, inactive, etc.) is silently excluded by
        # _run_payroll_processing's own filter — same as if it were never sent.
        selected_employee_codes = None
        if 'employee_ids' in request.data and request.data.get('employee_ids') is not None:
            raw_ids = request.data.get('employee_ids')
            if not isinstance(raw_ids, list):
                return error('employee_ids must be a list of employee codes.')
            selected_employee_codes = list({str(x).strip() for x in raw_ids if str(x).strip()})
            if not selected_employee_codes:
                return error(
                    'employee_ids cannot be empty. Select at least one employee, '
                    'or omit this field to process all eligible employees.',
                )
            known_codes = set(
                User.objects.filter(employee_id__in=selected_employee_codes)
                .values_list('employee_id', flat=True)
            )
            unknown_codes = [c for c in selected_employee_codes if c not in known_codes]
            if unknown_codes:
                return error(f"Unknown employee code(s): {', '.join(unknown_codes)}.")

        try:
            result = process_payroll_cycle(cycle, selected_employee_codes=selected_employee_codes)
        except PayrollAlreadyProcessing:
            return error(
                'This payroll cycle is already being processed or has already been processed.',
                http_status=409,
            )

        logger.info(
            'Payroll processed for cycle %s: %d payslips created, %d skipped by %s',
            pk, result['created_count'], len(result['skipped']), request.user.email,
        )
        AuditLog.objects.create(
            user=request.user, action='payroll_cycle_processed', module='payroll',
            object_id=str(cycle.id),
            changes={
                'is_reprocess': is_reprocess, 'payslip_count': result['created_count'],
                'skipped_count': len(result['skipped']),
            },
            branch=cycle.branch.branch_name if cycle.branch else '',
            ip_address=get_client_ip(request),
        )
        return success(
            f"Payroll processed. {result['created_count']} payslips generated.",
            {'payslip_count': result['created_count'], 'skipped': result['skipped']},
        )


class CycleEligibleEmployeesView(APIView):
    """GET /payroll/cycles/<pk>/eligible-employees/ — the employee population
    Process Payroll would consider for this cycle (before any optional
    selection), for the frontend's employee-selection checklist. Uses the
    exact same _eligible_employees_qs() the real processing pipeline uses,
    so this list can never drift out of sync with what "Process Payroll"
    actually touches. Read-only — no employee-selection state is persisted."""

    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        if not _has_perm(request.user, 'payroll.view'):
            return error('Only HR admin can view payroll cycles.', http_status=403)

        cycle = get_object_or_404(PayrollCycle, pk=pk)

        if not _is_admin(request.user):
            branch_obj = _resolve_user_branch(request.user)
            if branch_obj is None or cycle.branch_id != branch_obj.pk:
                return error('You can only view payroll for your own Company Code.', http_status=403)

        employees = list(
            _eligible_employees_qs(cycle)
            .order_by('full_name')
            .values('id', 'employee_id', 'full_name', 'department', 'designation')
        )
        return success('Eligible employees retrieved.', {'results': employees, 'count': len(employees)})


class MarkCyclePaidView(APIView):
    """HR marks a cycle as paid after external bank transfer is done."""

    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        if not _has_perm(request.user, 'payroll.edit'):
            return error('Only HR admin can mark payroll as paid.', http_status=403)

        cycle = get_object_or_404(PayrollCycle, pk=pk)

        if not _is_admin(request.user):
            branch_obj = _resolve_user_branch(request.user)
            if branch_obj is None or cycle.branch_id != branch_obj.pk:
                return error('You can only update payroll for your own Company Code.', http_status=403)

        if cycle.status not in [
            PayrollCycle.STATUS_QUERY_WINDOW_OPEN,
            PayrollCycle.STATUS_PAYSLIPS_GENERATED,
        ]:
            return error('Cycle must have payslips generated before marking as paid.')

        # Dual-confirmation gate: money only moves once the employee side
        # (every payslip acknowledged/resolved) AND the employer side (this
        # explicit confirm step, which locks a bank-detail snapshot) have
        # both signed off — see apps/payroll/views/salary_transfer.py.
        transfer_batch = SalaryTransferBatch.objects.filter(cycle=cycle).first()
        if not transfer_batch or transfer_batch.status != SalaryTransferBatch.STATUS_CONFIRMED:
            return error(
                'Salary transfer must be confirmed (both employee and employer sign-off) '
                'before this cycle can be marked as paid. '
                'POST /payroll/cycles/<id>/salary-transfer/confirm/ first.'
            )

        now = timezone.now()
        cycle.status      = PayrollCycle.STATUS_PAID
        cycle.paid_at     = now
        cycle.marked_paid_by = request.user
        cycle.save(update_fields=['status', 'paid_at', 'marked_paid_by', 'updated_at'])

        # Mark all draft/sent/acknowledged payslips as paid
        cycle.payslips.filter(
            status__in=[
                EmployeePayslip.STATUS_DRAFT,
                EmployeePayslip.STATUS_SENT,
                EmployeePayslip.STATUS_ACKNOWLEDGED,
                EmployeePayslip.STATUS_RESOLVED,
            ],
        ).update(status=EmployeePayslip.STATUS_PAID, paid_at=now)

        logger.info('Cycle %s marked as paid by %s', pk, request.user.email)
        AuditLog.objects.create(
            user=request.user, action='payroll_cycle_marked_paid', module='payroll',
            object_id=str(cycle.id),
            branch=cycle.branch.branch_name if cycle.branch else '',
            ip_address=get_client_ip(request),
        )
        return success('Cycle marked as paid.', PayrollCycleSerializer(cycle).data)


class CancelPayrollCycleView(APIView):
    """Cancel a payroll cycle that has not yet been paid.

    Requires a reason. Unlinking any expenses that were marked as disbursed
    through payslips in this cycle so they become available for the next run.
    Paid/closed cycles are irreversible and cannot be cancelled.
    """

    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        if not _has_perm(request.user, 'payroll.edit'):
            return error('Only HR admin can cancel payroll cycles.', http_status=403)

        cycle = get_object_or_404(PayrollCycle, pk=pk)

        if not _is_admin(request.user):
            branch_obj = _resolve_user_branch(request.user)
            if branch_obj is None or cycle.branch_id != branch_obj.pk:
                return error('You can only cancel payroll for your own Company Code.', http_status=403)

        if cycle.status == PayrollCycle.STATUS_CANCELLED:
            return error('This cycle is already cancelled.')

        if cycle.status in [PayrollCycle.STATUS_PAID, PayrollCycle.STATUS_CLOSED]:
            return error('Paid or closed payroll cycles cannot be cancelled. Contact your finance team.')

        reason = request.data.get('reason', '').strip()
        if not reason:
            return error('A cancellation reason is required.')

        with transaction.atomic():
            payslip_ids = list(cycle.payslips.values_list('id', flat=True))
            if payslip_ids:
                from apps.hrms.models import Expense
                Expense.objects.filter(
                    disbursed_in_payslip_id__in=payslip_ids,
                ).update(disbursed_in_payslip=None)
                logger.info(
                    'Unlinked expenses for %d payslips in cancelled cycle %s',
                    len(payslip_ids), pk,
                )

            cycle.status              = PayrollCycle.STATUS_CANCELLED
            cycle.cancelled_at        = timezone.now()
            cycle.cancelled_by        = request.user
            cycle.cancellation_reason = reason
            cycle.save(update_fields=[
                'status', 'cancelled_at', 'cancelled_by', 'cancellation_reason', 'updated_at',
            ])

        logger.info('Cycle %s cancelled by %s. Reason: %s', pk, request.user.email, reason)
        AuditLog.objects.create(
            user=request.user, action='payroll_cycle_cancelled', module='payroll',
            object_id=str(cycle.id), changes={'reason': reason},
            branch=cycle.branch.branch_name if cycle.branch else '',
            ip_address=get_client_ip(request),
        )
        return success('Payroll cycle cancelled.', PayrollCycleSerializer(cycle).data)
