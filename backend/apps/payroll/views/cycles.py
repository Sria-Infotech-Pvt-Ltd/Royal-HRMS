import logging
from collections import defaultdict
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
    StatutoryConfig,
    PayrollAdjustment,
    ManagerAttendanceApproval,
)
from apps.payroll.serializers import (
    PayrollCycleSerializer,
    EmployeePayslipSerializer,
    ManagerAttendanceApprovalSerializer,
)
from apps.accounts.models import User
from apps.branch.models import Branch

logger = logging.getLogger(__name__)

_PF_DEFAULT_RATE = Decimal('12.00')
_PF_DEFAULT_CEILING = Decimal('15000.00')

# Every field the old per-employee update_or_create() used to set — reused
# as bulk_update's field list so re-processing an existing payslip touches
# exactly the same columns as before.
_PAYSLIP_FIELDS = [
    'annual_ctc', 'monthly_ctc', 'basic', 'hra', 'special_allowance', 'other_earnings',
    'reimbursements', 'bonus', 'gross_earnings', 'total_working_days', 'lop_days',
    'lop_deduction', 'pf_employee', 'pf_employer', 'esi_employee', 'esi_employer',
    'pt_deduction', 'lwf_employee', 'lwf_employer', 'adjustments_earning',
    'adjustments_deduction', 'total_deductions', 'net_pay', 'status',
]


class PayrollAlreadyProcessing(Exception):
    """Cycle wasn't in STATUS_ATTENDANCE_APPROVED at claim time — either
    already processed, or a concurrent request already claimed it."""


def _compute_employee_payslip(salary_config, components, branch_config, statutory, adjustments) -> dict:
    """
    Pure calculation for one employee — byte-identical formulas to the
    original ProcessPayrollView loop body (Phase 2: only extracted into its
    own function so process_payroll_cycle() can call it once per employee
    against pre-fetched/cached inputs instead of querying inline).
    """
    monthly_ctc = salary_config.monthly_ctc
    basic = Decimal('0')
    hra = Decimal('0')
    special_allowance = Decimal('0')
    other_earnings = {}
    other_earnings_total = Decimal('0')

    for component in components:
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
            # JSONField can't store Decimal directly — cast to float for storage,
            # but keep the running total in Decimal to avoid binary float noise.
            other_earnings[component.name] = float(amount)
            other_earnings_total += amount

    gross = basic + hra + special_allowance + other_earnings_total

    # LOP deduction (placeholder — real value fed in later from attendance)
    lop_days = Decimal('0')
    total_working_days = 26
    lop_deduction = (gross / total_working_days) * lop_days

    # PF: use branch config if present, else statutory defaults (12%/12%, Rs.15,000 ceiling)
    pf_applicable = branch_config.pf_applicable if branch_config is not None else True
    pf_employee = Decimal('0')
    pf_employer = Decimal('0')
    if pf_applicable:
        pf_ceiling  = branch_config.pf_wage_ceiling   if branch_config else _PF_DEFAULT_CEILING
        pf_emp_rate = branch_config.pf_employee_rate   if branch_config else _PF_DEFAULT_RATE
        pf_er_rate  = branch_config.pf_employer_rate   if branch_config else _PF_DEFAULT_RATE
        pf_base     = min(basic, pf_ceiling)
        pf_employee = pf_base * pf_emp_rate / 100
        pf_employer = pf_base * pf_er_rate  / 100

    # ESI, PT, LWF: from the branch's state statutory config
    esi_employee = Decimal('0')
    esi_employer = Decimal('0')
    if statutory and statutory.esi_applicable and gross <= statutory.esi_wage_ceiling:
        esi_employee = gross * statutory.esi_employee_rate / 100
        esi_employer = gross * statutory.esi_employer_rate / 100

    # PT
    pt = Decimal(str(statutory.compute_pt(gross))) if statutory else Decimal('0')

    # LWF
    lwf_employee = statutory.lwf_employee_amount if (statutory and statutory.lwf_applicable) else Decimal('0')
    lwf_employer = statutory.lwf_employer_amount if (statutory and statutory.lwf_applicable) else Decimal('0')

    adj_earning = sum(
        (a.amount for a in adjustments if a.type in (PayrollAdjustment.ADDITION, PayrollAdjustment.ARREAR)),
        Decimal('0'),
    )
    adj_deduction = sum(
        (a.amount for a in adjustments if a.type == PayrollAdjustment.DEDUCTION),
        Decimal('0'),
    )

    total_deductions = (
        lop_deduction + pf_employee + esi_employee + pt + lwf_employee + adj_deduction
    )
    net_pay = gross + adj_earning - total_deductions

    return {
        'annual_ctc':            salary_config.annual_ctc,
        'monthly_ctc':           monthly_ctc,
        'basic':                 basic,
        'hra':                   hra,
        'special_allowance':     special_allowance,
        'other_earnings':        other_earnings,
        'reimbursements':        Decimal('0'),  # populated in wizard reimbursements step
        'bonus':                 Decimal('0'),  # populated in wizard bonuses step
        'gross_earnings':        gross,
        'total_working_days':    total_working_days,
        'lop_days':              lop_days,
        'lop_deduction':         lop_deduction,
        'pf_employee':           pf_employee,
        'pf_employer':           pf_employer,
        'esi_employee':          esi_employee,
        'esi_employer':          esi_employer,
        'pt_deduction':          pt,
        'lwf_employee':          lwf_employee,
        'lwf_employer':          lwf_employer,
        'adjustments_earning':   adj_earning,
        'adjustments_deduction': adj_deduction,
        'total_deductions':      total_deductions,
        'net_pay':               net_pay,
        'status':                EmployeePayslip.STATUS_DRAFT,
    }


def process_payroll_cycle(cycle: PayrollCycle) -> dict:
    """
    Compute and persist payslips for every eligible employee in `cycle`.

    Same formulas/business rules as the original ProcessPayrollView loop —
    only the data-fetching and write strategy changed (Phase 2 performance
    optimization):
      - salary configs / branches / adjustments are fetched in 3 bulk
        queries total instead of up to 3 queries PER employee.
      - salary-structure components and state statutory config are cached
        per distinct structure/state instead of re-queried per employee.
      - payslips are written via one bulk_create + one bulk_update instead
        of one update_or_create call per employee.
      - the cycle is claimed via a single conditional UPDATE (atomic
        compare-and-swap on status) so two concurrent "Process Payroll"
        clicks can't both run the heavy loop — the second fails fast.

    Returns {'created_count': int, 'skipped': list[str]} — same shape
    ProcessPayrollView returned before.

    Raises PayrollAlreadyProcessing if the cycle isn't in
    STATUS_ATTENDANCE_APPROVED at claim time.
    """
    claimed = PayrollCycle.objects.filter(
        pk=cycle.pk, status=PayrollCycle.STATUS_ATTENDANCE_APPROVED,
    ).update(status=PayrollCycle.STATUS_PROCESSING)
    if not claimed:
        raise PayrollAlreadyProcessing(
            'Cycle is not awaiting processing — it may already be processing or processed.'
        )
    cycle.status = PayrollCycle.STATUS_PROCESSING

    try:
        return _run_payroll_processing(cycle)
    except Exception:
        # An unexpected failure after the claim must not leave the cycle
        # wedged in STATUS_PROCESSING forever (it can never be re-claimed
        # from that state) — revert it back to STATUS_ATTENDANCE_APPROVED
        # so the same cycle can simply be reprocessed. The write phase's own
        # transaction.atomic() below already guarantees no partial payslips
        # exist for this attempt; this only fixes the cycle's own status.
        logger.error('process_payroll_cycle failed for cycle %s — reverting to attendance_approved.', cycle.pk, exc_info=True)
        PayrollCycle.objects.filter(
            pk=cycle.pk, status=PayrollCycle.STATUS_PROCESSING,
        ).update(status=PayrollCycle.STATUS_ATTENDANCE_APPROVED)
        cycle.status = PayrollCycle.STATUS_ATTENDANCE_APPROVED
        raise


def _run_payroll_processing(cycle: PayrollCycle) -> dict:
    """The actual fetch/compute/write work, split out of process_payroll_cycle()
    only so the claim-revert-on-failure logic above can wrap it cleanly."""
    settings_obj = PayrollSettings.objects.first()
    default_structure = SalaryStructure.objects.filter(is_default=True, is_active=True).first()

    employees_qs = User.objects.filter(
        is_active=True,
    ).exclude(
        role__name__in=['system_admin'],
    ).select_related('role')

    if cycle.branch:
        employees_qs = employees_qs.filter(branch=cycle.branch.branch_name)

    employees = list(employees_qs)
    employee_ids = [e.id for e in employees]

    # ── Bulk fetch: latest active salary config per employee ───────────────
    # (was: EmployeeSalaryConfig.objects.filter(employee=employee, ...).first()
    #  inside the loop — 1 query per employee, plus a hidden extra query per
    #  employee when accessing salary_config.salary_structure without
    #  select_related, now fixed here too.)
    salary_config_by_employee = {}
    for cfg in (
        EmployeeSalaryConfig.objects
        .filter(employee_id__in=employee_ids, is_active=True, effective_from__lte=cycle.cycle_end)
        .select_related('salary_structure')
        .order_by('employee_id', '-effective_from')
    ):
        # First row seen per employee (ordered by -effective_from) is the latest.
        salary_config_by_employee.setdefault(cfg.employee_id, cfg)

    # ── Bulk fetch: every branch referenced by these employees ─────────────
    # (was: Branch.objects.filter(branch_name=employee.branch).first() inside the loop)
    branch_names = {e.branch for e in employees}
    branch_by_name = {
        b.branch_name: b
        for b in Branch.objects.filter(branch_name__in=branch_names)
                                .select_related('state', 'payroll_config__salary_structure')
    }

    # ── Bulk fetch: this month's one-time adjustments for all employees ────
    # (was: PayrollAdjustment.objects.filter(employee=employee, month=adj_month) inside the loop)
    adj_month = cycle.cycle_start.replace(day=1)
    adjustments_by_employee = defaultdict(list)
    for adj in PayrollAdjustment.objects.filter(employee_id__in=employee_ids, month=adj_month):
        adjustments_by_employee[adj.employee_id].append(adj)

    # ── Per-distinct-structure / per-distinct-state caches ──────────────────
    # (was: structure.components.filter(...) and StatutoryConfig.objects.filter(...)
    #  re-run for every employee even when many employees share a structure/state)
    components_cache: dict = {}
    statutory_cache: dict = {}

    def _components_for(structure):
        if structure.id not in components_cache:
            components_cache[structure.id] = list(
                structure.components.filter(is_active=True).order_by('order')
            )
        return components_cache[structure.id]

    def _statutory_for(state):
        if state is None:
            return None
        if state.id not in statutory_cache:
            statutory_cache[state.id] = StatutoryConfig.objects.filter(state=state).first()
        return statutory_cache[state.id]

    computed = {}   # employee_id -> payslip fields dict
    skipped = []

    for employee in employees:
        salary_config = salary_config_by_employee.get(employee.id)
        if salary_config is None:
            skipped.append(employee.full_name)
            continue

        branch_obj = branch_by_name.get(employee.branch)
        branch_config = getattr(branch_obj, 'payroll_config', None) if branch_obj else None

        # Resolve structure: employee override -> branch -> default
        structure = salary_config.salary_structure
        if structure is None and branch_config and branch_config.salary_structure:
            structure = branch_config.salary_structure
        if structure is None:
            structure = default_structure
        if structure is None:
            skipped.append(f'{employee.full_name} (no structure)')
            continue

        components = _components_for(structure)
        statutory = _statutory_for(branch_obj.state) if branch_obj else None
        adjustments = adjustments_by_employee.get(employee.id, [])

        computed[employee.id] = _compute_employee_payslip(
            salary_config, components, branch_config, statutory, adjustments,
        )

    # ── Write phase: bulk_create + bulk_update instead of update_or_create per employee ──
    with transaction.atomic():
        existing_by_employee = {
            p.employee_id: p
            for p in EmployeePayslip.objects.filter(cycle=cycle, employee_id__in=list(computed.keys()))
        }

        to_create = []
        to_update = []
        for employee_id, fields in computed.items():
            existing = existing_by_employee.get(employee_id)
            if existing is not None:
                for field, value in fields.items():
                    setattr(existing, field, value)
                to_update.append(existing)
            else:
                to_create.append(EmployeePayslip(cycle=cycle, employee_id=employee_id, **fields))

        if to_create:
            EmployeePayslip.objects.bulk_create(to_create, batch_size=500)
        if to_update:
            EmployeePayslip.objects.bulk_update(to_update, _PAYSLIP_FIELDS, batch_size=500)

        cycle.status = PayrollCycle.STATUS_PAYSLIPS_GENERATED
        cycle.save(update_fields=['status', 'updated_at'])

    return {'created_count': len(computed), 'skipped': skipped}


def _has_perm(user, codename: str) -> bool:
    if not user or not user.role:
        return False
    if getattr(user, 'is_superuser', False):
        return True
    return user.role.role_permissions.filter(permission__codename=codename).exists()


def _can_l1_approve(user):
    """True for any user whose role has can_manage_team, plus HR/sysadmin as fallback."""
    if not user or not user.role:
        return False
    if getattr(user, 'is_superuser', False):
        return True
    return bool(user.role.can_manage_team) or _has_perm(user, 'payroll.edit')


def _can_l2_approve(user):
    """True for users with payroll.edit (HR/sysadmin)."""
    if not user or not user.role:
        return False
    if getattr(user, 'is_superuser', False):
        return True
    return _has_perm(user, 'payroll.edit')


def _is_admin(user) -> bool:
    """Settings-level admin: unrestricted access across all branches."""
    return getattr(user, 'is_superuser', False) or _has_perm(user, 'settings.edit')


def _resolve_user_branch(user):
    """Return the Branch object for an HR user's assigned branch, or None."""
    if not user.branch:
        return None
    return Branch.objects.filter(branch_name=user.branch, status=Branch.STATUS_ACTIVE).first()


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

        cycle_start = request.data.get('cycle_start')
        cycle_end   = request.data.get('cycle_end')
        pay_date    = request.data.get('pay_date')

        if not all([cycle_start, cycle_end, pay_date]):
            return error('cycle_start, cycle_end, and pay_date are required.')

        # Resolve branch: admin may pass branch_id, HR uses their own branch
        if _is_admin(request.user):
            branch_id = request.data.get('branch_id')
            if branch_id:
                branch_obj = Branch.objects.filter(pk=branch_id, status=Branch.STATUS_ACTIVE).first()
                if not branch_obj:
                    return error('Selected branch not found or inactive.')
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

            from apps.notifications.signals import _notify
            period = f'{cycle_start} – {cycle_end}'
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
    """Admin overview: every active branch with its latest non-cancelled cycle status."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        if not _has_perm(request.user, 'payroll.view'):
            return error('Access denied.', http_status=403)

        if not _is_admin(request.user):
            return error('Admin access required for branch payroll overview.', http_status=403)

        branches = Branch.objects.filter(status=Branch.STATUS_ACTIVE).order_by('branch_name')
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

        return success('Branch payroll status retrieved.', result)


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

        if level == 'L1':
            manager_row = ManagerAttendanceApproval.objects.filter(
                cycle=cycle, manager=request.user,
            ).first()

            if manager_row:
                if manager_row.approved_at:
                    return error('You have already approved attendance for this cycle.')
                manager_row.approved_at = timezone.now()
                manager_row.note = note
                manager_row.save(update_fields=['approved_at', 'note', 'updated_at'])
                logger.info('Cycle %s: manager %s approved L1', pk, request.user.email)
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
            cycle.save(update_fields=[
                'attendance_approved_by_l2', 'attendance_l2_approved_at', 'status', 'updated_at',
            ])
            logger.info('Cycle %s L2 attendance approved by %s', pk, request.user.email)
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

        # HR can only process cycles for their own branch
        if not _is_admin(request.user) and cycle.branch:
            branch_obj = _resolve_user_branch(request.user)
            if branch_obj is None or cycle.branch_id != branch_obj.pk:
                return error('You can only process payroll for your own branch.', http_status=403)

        if cycle.status != PayrollCycle.STATUS_ATTENDANCE_APPROVED:
            return error('Attendance must be approved before processing payroll.')

        try:
            result = process_payroll_cycle(cycle)
        except PayrollAlreadyProcessing:
            return error(
                'This payroll cycle is already being processed or has already been processed.',
                http_status=409,
            )

        logger.info(
            'Payroll processed for cycle %s: %d payslips created, %d skipped by %s',
            pk, result['created_count'], len(result['skipped']), request.user.email,
        )
        return success(
            f"Payroll processed. {result['created_count']} payslips generated.",
            {'payslip_count': result['created_count'], 'skipped': result['skipped']},
        )


class MarkCyclePaidView(APIView):
    """HR marks a cycle as paid after external bank transfer is done."""

    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        if not _has_perm(request.user, 'payroll.edit'):
            return error('Only HR admin can mark payroll as paid.', http_status=403)

        cycle = get_object_or_404(PayrollCycle, pk=pk)

        if not _is_admin(request.user) and cycle.branch:
            branch_obj = _resolve_user_branch(request.user)
            if branch_obj is None or cycle.branch_id != branch_obj.pk:
                return error('You can only update payroll for your own branch.', http_status=403)

        if cycle.status not in [
            PayrollCycle.STATUS_QUERY_WINDOW_OPEN,
            PayrollCycle.STATUS_PAYSLIPS_GENERATED,
        ]:
            return error('Cycle must have payslips generated before marking as paid.')

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

        if not _is_admin(request.user) and cycle.branch:
            branch_obj = _resolve_user_branch(request.user)
            if branch_obj is None or cycle.branch_id != branch_obj.pk:
                return error('You can only cancel payroll for your own branch.', http_status=403)

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
        return success('Payroll cycle cancelled.', PayrollCycleSerializer(cycle).data)
