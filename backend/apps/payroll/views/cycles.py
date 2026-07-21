import logging
from datetime import date, timedelta
from decimal import Decimal

from django.db import transaction
from django.utils import timezone
from django.shortcuts import get_object_or_404
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated

from core.responses import success, error, first_error
from core.pagination import paginate, paginated_data
from apps.payroll.models import (
    PayrollCycle,
    PayrollSettings,
    EmployeePayslip,
    EmployeeSalaryConfig,
    SalaryStructure,
    SalaryComponent,
    BranchPayrollConfig,
    StatutoryConfig,
)
from apps.payroll.serializers import PayrollCycleSerializer, EmployeePayslipSerializer
from apps.accounts.models import User
from apps.branch.models import Branch

logger = logging.getLogger(__name__)

HR_ADMIN_ROLES = frozenset(['system_admin', 'hr_admin'])
MANAGER_ROLES = frozenset(['system_admin', 'hr_admin', 'manager'])


def _is_hr_admin(user):
    return user.role and user.role.name in HR_ADMIN_ROLES


def _is_manager_or_above(user):
    return user.role and user.role.name in MANAGER_ROLES


class PayrollCycleListView(APIView):
    """List all payroll cycles / create a new one."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        if not _is_hr_admin(request.user):
            return error('Only HR admin can view payroll cycles.', http_status=403)

        cycles = PayrollCycle.objects.select_related('created_by').order_by('-cycle_start')
        page_obj, paginator = paginate(cycles, request)
        serializer = PayrollCycleSerializer(page_obj.object_list, many=True)
        return success(
            'Payroll cycles retrieved.',
            paginated_data(paginator, page_obj, serializer.data),
        )

    def post(self, request):
        if not _is_hr_admin(request.user):
            return error('Only HR admin can create payroll cycles.', http_status=403)

        cycle_start = request.data.get('cycle_start')
        cycle_end = request.data.get('cycle_end')
        pay_date = request.data.get('pay_date')

        if not all([cycle_start, cycle_end, pay_date]):
            return error('cycle_start, cycle_end, and pay_date are required.')

        # Prevent duplicate open cycles for the same period
        if PayrollCycle.objects.filter(
            cycle_start=cycle_start,
            status__in=[
                PayrollCycle.STATUS_DRAFT,
                PayrollCycle.STATUS_ATTENDANCE_PENDING,
                PayrollCycle.STATUS_ATTENDANCE_APPROVED,
                PayrollCycle.STATUS_PROCESSING,
            ],
        ).exists():
            return error('A payroll cycle for this period is already in progress.')

        cycle = PayrollCycle.objects.create(
            cycle_start=cycle_start,
            cycle_end=cycle_end,
            pay_date=pay_date,
            status=PayrollCycle.STATUS_ATTENDANCE_PENDING,
            created_by=request.user,
            notes=request.data.get('notes', ''),
        )
        logger.info('PayrollCycle %s created by %s', cycle.id, request.user.email)

        # Notify all active managers to review and approve attendance
        try:
            from apps.notifications.signals import _notify
            period = f'{cycle_start} – {cycle_end}'
            managers = User.objects.filter(
                is_active=True, role__name='manager',
            ).exclude(pk=request.user.pk)
            for manager in managers:
                _notify(
                    manager,
                    'Attendance Approval Required',
                    f'Payroll for {period} has been initiated and requires your attendance sign-off.',
                    'attendance',
                    'payroll',
                    str(cycle.id),
                    request.user,
                )
        except Exception:
            logger.exception('Failed to send attendance approval notifications for cycle %s', cycle.id)

        return success('Payroll cycle created.', PayrollCycleSerializer(cycle).data, http_status=201)


class PayrollCycleDetailView(APIView):
    """Retrieve a single payroll cycle."""

    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        if not _is_hr_admin(request.user):
            return error('Access denied.', http_status=403)

        cycle = get_object_or_404(
            PayrollCycle.objects.select_related(
                'created_by',
                'attendance_approved_by_l1',
                'attendance_approved_by_l2',
                'marked_paid_by',
            ),
            pk=pk,
        )
        return success('Payroll cycle retrieved.', PayrollCycleSerializer(cycle).data)


class AttendanceApprovalView(APIView):
    """L1 (manager) or L2 (hr_admin) attendance approval for a payroll cycle.

    POST body: {"level": "L1"} or {"level": "L2"}
    """

    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        cycle = get_object_or_404(PayrollCycle, pk=pk)

        if cycle.status != PayrollCycle.STATUS_ATTENDANCE_PENDING:
            return error('Attendance is not pending approval for this cycle.')

        settings_obj = PayrollSettings.objects.first()
        level = request.data.get('level', '').upper()

        if level == 'L1':
            if not _is_manager_or_above(request.user):
                return error('Manager or HR admin role required for L1 approval.', http_status=403)
            if cycle.attendance_approved_by_l1_id:
                return error('L1 approval already recorded.')

            cycle.attendance_approved_by_l1 = request.user
            cycle.attendance_l1_approved_at = timezone.now()

            # If settings require only L1, move to approved immediately
            requires_l2 = settings_obj and settings_obj.approval_levels == PayrollSettings.APPROVAL_L1_L2
            if not requires_l2:
                cycle.status = PayrollCycle.STATUS_ATTENDANCE_APPROVED

            cycle.save(update_fields=[
                'attendance_approved_by_l1', 'attendance_l1_approved_at', 'status', 'updated_at',
            ])
            logger.info('Cycle %s L1 attendance approved by %s', pk, request.user.email)
            return success('L1 attendance approval recorded.', PayrollCycleSerializer(cycle).data)

        elif level == 'L2':
            if not _is_hr_admin(request.user):
                return error('HR admin role required for L2 approval.', http_status=403)
            if not cycle.attendance_approved_by_l1_id:
                return error('L1 approval must be completed first.')
            if cycle.attendance_approved_by_l2_id:
                return error('L2 approval already recorded.')

            cycle.attendance_approved_by_l2 = request.user
            cycle.attendance_l2_approved_at = timezone.now()
            cycle.status = PayrollCycle.STATUS_ATTENDANCE_APPROVED

            cycle.save(update_fields=[
                'attendance_approved_by_l2', 'attendance_l2_approved_at', 'status', 'updated_at',
            ])
            logger.info('Cycle %s L2 attendance approved by %s', pk, request.user.email)
            return success('L2 attendance approval recorded.', PayrollCycleSerializer(cycle).data)

        return error('level must be "L1" or "L2".')


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
        if not _is_hr_admin(request.user):
            return error('Only HR admin can process payroll.', http_status=403)

        cycle = get_object_or_404(PayrollCycle, pk=pk)
        if cycle.status != PayrollCycle.STATUS_ATTENDANCE_APPROVED:
            return error('Attendance must be approved before processing payroll.')

        settings_obj = PayrollSettings.objects.first()
        default_structure = SalaryStructure.objects.filter(is_default=True, is_active=True).first()

        employees = User.objects.filter(
            is_active=True,
        ).exclude(
            role__name__in=['system_admin'],
        ).select_related('role')

        created_count = 0
        skipped = []

        PF_DEFAULT_RATE = Decimal('12.00')
        PF_DEFAULT_CEILING = Decimal('15000.00')

        with transaction.atomic():
            cycle.status = PayrollCycle.STATUS_PROCESSING
            cycle.save(update_fields=['status', 'updated_at'])

            for employee in employees:
                salary_config = EmployeeSalaryConfig.objects.filter(
                    employee=employee,
                    is_active=True,
                    effective_from__lte=cycle.cycle_end,
                ).order_by('-effective_from').first()

                if salary_config is None:
                    skipped.append(employee.full_name)
                    continue

                # Single branch lookup — used for structure, PF, and statutory below
                branch_obj = Branch.objects.filter(
                    branch_name=employee.branch,
                ).select_related('state', 'payroll_config__salary_structure').first()
                branch_config = getattr(branch_obj, 'payroll_config', None) if branch_obj else None

                # Resolve structure: employee override → branch → default
                structure = salary_config.salary_structure
                if structure is None and branch_config and branch_config.salary_structure:
                    structure = branch_config.salary_structure
                if structure is None:
                    structure = default_structure
                if structure is None:
                    skipped.append(f'{employee.full_name} (no structure)')
                    continue

                monthly_ctc = salary_config.monthly_ctc
                basic = Decimal('0')
                hra = Decimal('0')
                special_allowance = Decimal('0')
                other_earnings = {}

                for component in structure.components.filter(is_active=True).order_by('order'):
                    if component.calculation_type == SalaryComponent.CALC_PCT_CTC:
                        amount = monthly_ctc * component.value / 100
                    elif component.calculation_type == SalaryComponent.CALC_PCT_BASIC:
                        amount = basic * component.value / 100
                    else:
                        amount = component.value

                    name_lower = component.name.lower()
                    if name_lower == 'basic':
                        basic = amount
                    elif name_lower == 'hra':
                        hra = amount
                    elif name_lower == 'special allowance':
                        special_allowance = amount
                    else:
                        other_earnings[component.name] = float(amount)

                gross = basic + hra + special_allowance + Decimal(sum(other_earnings.values()))

                # LOP deduction (placeholder — real value fed in later from attendance)
                lop_days = Decimal('0')
                total_working_days = 26
                lop_deduction = (gross / total_working_days) * lop_days

                # PF: use branch config if present, else statutory defaults (12%/12%, ₹15,000 ceiling)
                pf_applicable = branch_config.pf_applicable if branch_config is not None else True
                pf_employee = Decimal('0')
                pf_employer = Decimal('0')
                if pf_applicable:
                    pf_ceiling = branch_config.pf_wage_ceiling if branch_config else PF_DEFAULT_CEILING
                    pf_emp_rate = branch_config.pf_employee_rate if branch_config else PF_DEFAULT_RATE
                    pf_er_rate = branch_config.pf_employer_rate if branch_config else PF_DEFAULT_RATE
                    pf_base = min(basic, pf_ceiling)
                    pf_employee = pf_base * pf_emp_rate / 100
                    pf_employer = pf_base * pf_er_rate / 100

                # ESI, PT, LWF: from the branch's state statutory config — no branch config record needed
                esi_employee = Decimal('0')
                esi_employer = Decimal('0')
                statutory = StatutoryConfig.objects.filter(
                    state=branch_obj.state,
                ).first() if branch_obj else None
                if statutory and statutory.esi_applicable and gross <= statutory.esi_wage_ceiling:
                    esi_employee = gross * statutory.esi_employee_rate / 100
                    esi_employer = gross * statutory.esi_employer_rate / 100

                # PT
                pt = Decimal(str(statutory.compute_pt(gross))) if statutory else Decimal('0')

                # LWF (only on applicable months — simplified: always deduct if applicable)
                lwf_employee = statutory.lwf_employee_amount if (statutory and statutory.lwf_applicable) else Decimal('0')
                lwf_employer = statutory.lwf_employer_amount if (statutory and statutory.lwf_applicable) else Decimal('0')

                total_deductions = (
                    lop_deduction + pf_employee + esi_employee + pt + lwf_employee
                )
                net_pay = gross - total_deductions

                reimbursements = Decimal('0')
                bonus = Decimal('0')
                if settings_obj and settings_obj.enable_reimbursements:
                    reimbursements = Decimal('0')  # populated in wizard reimbursements step
                if settings_obj and settings_obj.enable_bonuses:
                    bonus = Decimal('0')  # populated in wizard bonuses step

                EmployeePayslip.objects.update_or_create(
                    cycle=cycle,
                    employee=employee,
                    defaults={
                        'annual_ctc': salary_config.annual_ctc,
                        'monthly_ctc': monthly_ctc,
                        'basic': basic,
                        'hra': hra,
                        'special_allowance': special_allowance,
                        'other_earnings': other_earnings,
                        'reimbursements': reimbursements,
                        'bonus': bonus,
                        'gross_earnings': gross,
                        'total_working_days': total_working_days,
                        'lop_days': lop_days,
                        'lop_deduction': lop_deduction,
                        'pf_employee': pf_employee,
                        'pf_employer': pf_employer,
                        'esi_employee': esi_employee,
                        'esi_employer': esi_employer,
                        'pt_deduction': pt,
                        'lwf_employee': lwf_employee,
                        'lwf_employer': lwf_employer,
                        'total_deductions': total_deductions,
                        'net_pay': net_pay,
                        'status': EmployeePayslip.STATUS_DRAFT,
                    },
                )
                created_count += 1

            cycle.status = PayrollCycle.STATUS_PAYSLIPS_GENERATED
            cycle.save(update_fields=['status', 'updated_at'])

        logger.info(
            'Payroll processed for cycle %s: %d payslips created, %d skipped by %s',
            pk, created_count, len(skipped), request.user.email,
        )
        return success(
            f'Payroll processed. {created_count} payslips generated.',
            {'payslip_count': created_count, 'skipped': skipped},
        )


class MarkCyclePaidView(APIView):
    """HR marks a cycle as paid after external bank transfer is done."""

    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        if not _is_hr_admin(request.user):
            return error('Only HR admin can mark payroll as paid.', http_status=403)

        cycle = get_object_or_404(PayrollCycle, pk=pk)
        if cycle.status not in [
            PayrollCycle.STATUS_QUERY_WINDOW_OPEN,
            PayrollCycle.STATUS_PAYSLIPS_GENERATED,
        ]:
            return error('Cycle must have payslips generated before marking as paid.')

        now = timezone.now()
        cycle.status = PayrollCycle.STATUS_PAID
        cycle.paid_at = now
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
        return success('Cycle marked as paid.', PayrollCycleSerializer(cycle).data)
