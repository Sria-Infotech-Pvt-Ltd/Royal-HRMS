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

_PF_DEFAULT_RATE = Decimal('12.00')
_PF_DEFAULT_CEILING = Decimal('15000.00')

# Every field the old per-employee update_or_create() used to set — reused
# as bulk_update's field list so re-processing an existing payslip touches
# exactly the same columns as before.
_PAYSLIP_FIELDS = [
    'salary_structure',
    'annual_ctc', 'monthly_ctc', 'basic', 'hra', 'special_allowance', 'other_earnings',
    'reimbursements', 'bonus', 'gross_earnings', 'total_working_days', 'lop_days',
    'lop_deduction', 'pf_wage_base', 'pf_employee', 'pf_employer', 'esi_employee', 'esi_employer',
    'pt_deduction', 'lwf_employee', 'lwf_employer', 'income_tax', 'adjustments_earning',
    'adjustments_deduction', 'total_deductions', 'net_pay', 'status',
]


class PayrollAlreadyProcessing(Exception):
    """Cycle wasn't in STATUS_ATTENDANCE_APPROVED at claim time — either
    already processed, or a concurrent request already claimed it."""


def _esi_contribution_period(for_date: date) -> tuple:
    """
    ESIC's contribution periods are fixed halves of the financial year —
    April to September, and October to March — not calendar months.
    Returns (period_start, period_end) for whichever period `for_date`
    falls in. Used so ESI eligibility can be checked against "was this
    employee covered anywhere earlier in the current period", not just
    the current month in isolation (see _compute_employee_payslip).
    """
    if 4 <= for_date.month <= 9:
        return date(for_date.year, 4, 1), date(for_date.year, 9, 30)
    if for_date.month >= 10:
        return date(for_date.year, 10, 1), date(for_date.year + 1, 3, 31)
    return date(for_date.year - 1, 10, 1), date(for_date.year, 3, 31)


def _lwf_due_this_cycle(statutory, cycle_month) -> bool:
    """Whether the configured LWF amount should be charged in a cycle whose
    payroll month is `cycle_month` (1-12, cycle.cycle_start's month — the
    same "which month is this cycle" convention PayrollAdjustment.month
    already uses elsewhere in this module).

    monthly    -> every cycle.
    annual/halfyearly -> only in the configured due month(s); an empty
    lwf_due_months means "not charged" (Option A — never overcharges while
    a state's due month(s) haven't been configured yet).
    """
    if not statutory or not statutory.lwf_applicable:
        return False
    if statutory.lwf_frequency == StatutoryConfig.LWF_MONTHLY:
        return True
    return cycle_month in (statutory.lwf_due_months or [])


def _compute_employee_payslip(
    salary_config, components, branch_config, statutory, adjustments, structure,
    lop_days=Decimal('0'), total_working_days=26, cycle_month=None,
    esi_covered_earlier_this_period=False, proration_factor=Decimal('1'),
    is_metro=False, tax_regime='new', declared_investments=None,
) -> dict:
    """
    Pure calculation for one employee — byte-identical formulas to the
    original ProcessPayrollView loop body (Phase 2: only extracted into its
    own function so process_payroll_cycle() can call it once per employee
    against pre-fetched/cached inputs instead of querying inline).

    proration_factor: employed_days_in_cycle / total_days_in_cycle for a
    mid-cycle joiner or leaver (1 for a full-cycle employee — the default,
    and the only value this ever took before join/leave-date awareness was
    added). Applied uniformly to every earning component's already-computed
    amount, not threaded into the per-component calculation loop above —
    scaling basic/hra/special_allowance/each other_earnings entry by the
    same factor preserves their relative proportions (a CALC_PCT_BASIC
    component computed against the full basic, then scaled by the same
    factor as that basic, ends up correctly prorated too) while leaving the
    calculation loop itself untouched.

    tax_regime/declared_investments: this employee's real EmployeeTaxDeclaration
    for the cycle's financial year (regime + declared 80C/80D/80CCD1B/HRA
    amounts), resolved by the caller — see apps/payroll/services_income_tax.py
    for the real slab computation this feeds into.
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
        elif component.calculation_type == SalaryComponent.CALC_METRO_HRA:
            metro_pct = Decimal('50') if is_metro else Decimal('40')
            amount = basic * metro_pct / 100
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

    if proration_factor != Decimal('1'):
        basic = basic * proration_factor
        hra = hra * proration_factor
        special_allowance = special_allowance * proration_factor
        other_earnings = {name: float(Decimal(str(v)) * proration_factor) for name, v in other_earnings.items()}
        other_earnings_total = other_earnings_total * proration_factor

    gross = basic + hra + special_allowance + other_earnings_total

    # LOP deduction — lop_days and total_working_days come from actual AttendanceRecord data
    lop_deduction = (gross / total_working_days) * lop_days if total_working_days else Decimal('0')

    # PF: use branch config if present, else statutory defaults (12%/12%, Rs.15,000 ceiling)
    pf_applicable = branch_config.pf_applicable if branch_config is not None else True
    pf_employee = Decimal('0')
    pf_employer = Decimal('0')
    pf_wage_base = Decimal('0')
    if pf_applicable:
        pf_ceiling  = branch_config.pf_wage_ceiling   if branch_config else _PF_DEFAULT_CEILING
        pf_emp_rate = branch_config.pf_employee_rate   if branch_config else _PF_DEFAULT_RATE
        pf_er_rate  = branch_config.pf_employer_rate   if branch_config else _PF_DEFAULT_RATE
        pf_wage_basis = (
            branch_config.pf_wage_basis if branch_config else BranchPayrollConfig.PF_WAGE_BASIC_ONLY
        )
        # 'basic_only' (default) preserves this branch's existing behavior.
        # 'basic_plus_allowances' follows the 2019 EPFO ruling (and
        # Razorpay's documented PF calculation): PF wages = Gross - HRA,
        # i.e. every allowance except HRA counts, not just basic. Opt-in
        # per branch via BranchPayrollConfig.pf_wage_basis — see that
        # field's help_text for why this isn't just silently switched over.
        if pf_wage_basis == BranchPayrollConfig.PF_WAGE_BASIC_PLUS_ALLOWANCES:
            uncapped_pf_wage = basic + special_allowance + other_earnings_total
        else:
            uncapped_pf_wage = basic
        pf_wage_base = min(uncapped_pf_wage, pf_ceiling)
        pf_employee = pf_wage_base * pf_emp_rate / 100
        pf_employer = pf_wage_base * pf_er_rate  / 100

    # ESI, PT, LWF: from the branch's state statutory config
    esi_employee = Decimal('0')
    esi_employer = Decimal('0')
    # Coverage doesn't lapse the instant gross crosses the ceiling in a
    # single month — once ESI-covered, an employee stays covered for the
    # rest of the current contribution period (Apr-Sep / Oct-Mar), per
    # ESIC rules. esi_covered_earlier_this_period is bulk-checked by the
    # caller against prior payslips this period (see _run_payroll_processing).
    if statutory and statutory.esi_applicable and (
        gross <= statutory.esi_wage_ceiling or esi_covered_earlier_this_period
    ):
        esi_employer = gross * statutory.esi_employer_rate / 100
        # An employee averaging <=₹176/day is exempt from their OWN 0.75%
        # share — the employer's 3.25% share is still due regardless; this
        # is a deliberate asymmetric exemption, not a skip of both sides.
        days_paid = max(Decimal('1'), Decimal(total_working_days) - lop_days)
        daily_wage = gross / days_paid
        if daily_wage > Decimal('176'):
            esi_employee = gross * statutory.esi_employee_rate / 100

    # PT
    pt = Decimal(str(statutory.compute_pt(gross))) if statutory else Decimal('0')

    # LWF — only charged in the state's configured due cycle(s); see _lwf_due_this_cycle().
    lwf_due = _lwf_due_this_cycle(statutory, cycle_month)
    lwf_employee = statutory.lwf_employee_amount if lwf_due else Decimal('0')
    lwf_employer = statutory.lwf_employer_amount if lwf_due else Decimal('0')

    adj_earning = sum(
        (a.amount for a in adjustments if a.type in (PayrollAdjustment.ADDITION, PayrollAdjustment.ARREAR)),
        Decimal('0'),
    )
    adj_deduction = sum(
        (a.amount for a in adjustments if a.type == PayrollAdjustment.DEDUCTION),
        Decimal('0'),
    )

    income_tax = estimate_monthly_tds(gross, tax_regime, declared_investments)

    total_deductions = (
        lop_deduction + pf_employee + esi_employee + pt + lwf_employee + income_tax + adj_deduction
    )
    net_pay = gross + adj_earning - total_deductions

    return {
        'salary_structure':      structure,
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
        'pf_wage_base':          pf_wage_base,
        'pf_employee':           pf_employee,
        'pf_employer':           pf_employer,
        'esi_employee':          esi_employee,
        'esi_employer':          esi_employer,
        'pt_deduction':          pt,
        'lwf_employee':          lwf_employee,
        'lwf_employer':          lwf_employer,
        'income_tax':            income_tax,
        'adjustments_earning':   adj_earning,
        'adjustments_deduction': adj_deduction,
        'total_deductions':      total_deductions,
        'net_pay':               net_pay,
        'status':                EmployeePayslip.STATUS_DRAFT,
    }


def process_payroll_cycle(cycle: PayrollCycle, selected_employee_codes=None) -> dict:
    """
    Compute and persist payslips for every eligible employee in `cycle`,
    or (optionally) only a selected subset of them — see
    _run_payroll_processing()'s docstring for selected_employee_codes.

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
    is_reprocess = cycle.status == PayrollCycle.STATUS_PAYSLIPS_GENERATED
    revert_status = (
        PayrollCycle.STATUS_PAYSLIPS_GENERATED
        if is_reprocess
        else PayrollCycle.STATUS_ATTENDANCE_APPROVED
    )

    claimed = PayrollCycle.objects.filter(
        pk=cycle.pk,
        status__in=[PayrollCycle.STATUS_ATTENDANCE_APPROVED, PayrollCycle.STATUS_PAYSLIPS_GENERATED],
    ).update(status=PayrollCycle.STATUS_PROCESSING)
    if not claimed:
        raise PayrollAlreadyProcessing(
            'Cycle is not awaiting processing — it may already be processing or processed.'
        )
    cycle.status = PayrollCycle.STATUS_PROCESSING

    try:
        return _run_payroll_processing(cycle, selected_employee_codes=selected_employee_codes)
    except Exception:
        logger.error('process_payroll_cycle failed for cycle %s — reverting status.', cycle.pk, exc_info=True)
        PayrollCycle.objects.filter(
            pk=cycle.pk, status=PayrollCycle.STATUS_PROCESSING,
        ).update(status=revert_status)
        cycle.status = revert_status
        raise


def _eligible_employees_qs(cycle: PayrollCycle):
    """The exact employee population Process Payroll considers for `cycle`,
    before any optional employee-selection filter and before the
    per-employee salary-config eligibility check (that part still requires
    a bulk fetch, so it stays inside _run_payroll_processing). Shared by
    _run_payroll_processing() and CycleEligibleEmployeesView so the
    "who will this touch" preview the frontend shows can never drift from
    what actually gets processed."""
    active_qs = User.objects.filter(is_active=True).exclude(role__name__in=['system_admin'])

    # Mid-cycle leavers: an employee deactivated before this cycle is
    # processed was previously excluded outright by is_active=True above —
    # meaning someone who worked part of the cycle and then left (or was
    # offboarded) got zero payslip for the days they did work, not a
    # prorated one. Included here via a real, grounded signal — they have
    # actual AttendanceRecord rows inside this cycle's date range, proving
    # they were genuinely employed for at least part of it — rather than a
    # dedicated "relieving date" field, which doesn't exist on User today.
    leaver_ids = (
        AttendanceRecord.objects
        .filter(employee__is_active=False, date__range=(cycle.cycle_start, cycle.cycle_end))
        .exclude(employee__role__name__in=['system_admin'])
        .values_list('employee_id', flat=True)
        .distinct()
    )
    leaver_qs = User.objects.filter(id__in=leaver_ids)

    employees_qs = (active_qs | leaver_qs).select_related('role')

    if cycle.branch:
        employees_qs = employees_qs.filter(branch=cycle.branch.branch_name)

    return employees_qs


def _run_payroll_processing(cycle: PayrollCycle, selected_employee_codes=None) -> dict:
    """The actual fetch/compute/write work, split out of process_payroll_cycle()
    only so the claim-revert-on-failure logic above can wrap it cleanly.

    selected_employee_codes: optional collection of `employee_id` code
    strings. None (the default) preserves the original behavior exactly —
    every eligible employee is processed. When provided, it's intersected
    with the same eligible queryset below via a single extra .filter(),
    so it adds no additional queries and can never widen the population
    (an out-of-branch/inactive/system_admin code simply won't match and is
    silently excluded, same as if it had never been selected)."""
    default_structure = SalaryStructure.objects.filter(is_default=True, is_active=True).first()

    employees_qs = _eligible_employees_qs(cycle)
    if selected_employee_codes is not None:
        employees_qs = employees_qs.filter(employee_id__in=selected_employee_codes)

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

    # ── Bulk fetch: this cycle's financial-year tax declaration per employee ──
    # India's FY runs Apr-Mar; an employee who never submitted a declaration
    # for this FY gets the same REGIME_NEW / no-declared-investments default
    # EmployeeTaxDeclaration.tax_regime itself defaults to — see
    # services_income_tax.estimate_monthly_tds.
    fy_start = cycle.cycle_start.year if cycle.cycle_start.month >= 4 else cycle.cycle_start.year - 1
    tax_declaration_by_employee = {
        d.employee_id: d
        for d in EmployeeTaxDeclaration.objects.filter(
            employee_id__in=employee_ids, financial_year_start=fy_start,
        )
    }

    # ── Load attendance LOP rules from settings ───────────────────────────
    att_settings = (
        AttendanceSettings.objects
        .select_related('late_mark_rules')
        .filter(is_active=True)
        .first()
    )
    late_mark_rules = getattr(att_settings, 'late_mark_rules', None) if att_settings else None
    late_per_lop = (
        late_mark_rules.late_marks_per_lop
        if late_mark_rules and late_mark_rules.late_marks_per_lop > 0
        else 0
    )
    # Each late-mark LOP trigger counts as full day or half day per policy.
    late_lop_unit = Decimal('0')
    if late_per_lop:
        late_lop_unit = (
            Decimal('1')
            if late_mark_rules.lop_deduction_unit == AttendanceLateMarkRules.LOP_UNIT_FULL_DAY
            else Decimal('0.5')
        )

    # ── Bulk fetch: ESI coverage earlier in the current contribution period ──
    period_start, _period_end = _esi_contribution_period(cycle.cycle_start)
    esi_covered_earlier_ids = set(
        EmployeePayslip.objects
        .filter(
            employee_id__in=employee_ids,
            cycle__cycle_start__gte=period_start,
            cycle__cycle_start__lt=cycle.cycle_start,
            esi_employer__gt=0,
        )
        .values_list('employee_id', flat=True)
        .distinct()
    )

    # ── Bulk fetch: daily attendance for LOP calculation ──────────────────
    # Fetched once per employee (not re-queried) and kept as a raw
    # (date, status) list per employee — join/leave-date proration below
    # needs each employee's own record dates twice: once to find a mid-cycle
    # leaver's last actual attendance date (their proxy "employed through"
    # date, since no dedicated relieving-date field exists), and again to
    # aggregate absent/half-day/late/working-days counts bounded to their
    # own employed window within the cycle, not the full cycle every other
    # employee uses.
    _NON_WORKING = {AttendanceRecord.STATUS_WEEKLY_OFF, AttendanceRecord.STATUS_HOLIDAY}
    records_by_emp: dict = defaultdict(list)
    for rec in AttendanceRecord.objects.filter(
        employee_id__in=employee_ids,
        date__range=(cycle.cycle_start, cycle.cycle_end),
    ).only('employee_id', 'status', 'date'):
        records_by_emp[rec.employee_id].append((rec.date, rec.status))

    # ── Join/leave-date proration ──────────────────────────────────────────
    # Previously: a mid-cycle joiner's date_of_joining was never consulted at
    # all — they were paid the full monthly amount regardless of how many
    # days of the cycle they'd actually been employed for. A mid-cycle
    # leaver was excluded entirely by _eligible_employees_qs's is_active
    # filter (now widened above) and so got zero payslip for days they did
    # work. Both are fixed here via the same mechanism: prorate every
    # earning component by employed_days_in_cycle / total_days_in_cycle,
    # and bound the LOP/working-days calculation to that same window.
    total_days_in_cycle = (cycle.cycle_end - cycle.cycle_start).days + 1
    proration_factor_by_emp: dict = {}
    window_by_emp: dict = {}  # employee_id -> (effective_start, effective_end)
    for employee in employees:
        effective_start = cycle.cycle_start
        if employee.date_of_joining and employee.date_of_joining > cycle.cycle_start:
            effective_start = min(employee.date_of_joining, cycle.cycle_end)

        effective_end = cycle.cycle_end
        if not employee.is_active:
            # Proxy "last day employed" — the latest date this employee has
            # a real attendance record for within the cycle. Falls back to
            # effective_start (zero employed days) if they somehow have none
            # at all, though _eligible_employees_qs only includes inactive
            # employees who do have at least one such record.
            emp_dates = [d for d, _ in records_by_emp.get(employee.id, [])]
            effective_end = min(cycle.cycle_end, max(emp_dates)) if emp_dates else effective_start

        window_by_emp[employee.id] = (effective_start, effective_end)

        if effective_end < effective_start or total_days_in_cycle <= 0:
            proration_factor_by_emp[employee.id] = Decimal('0')
        else:
            employed_days = (effective_end - effective_start).days + 1
            proration_factor_by_emp[employee.id] = (
                Decimal(employed_days) / Decimal(total_days_in_cycle)
            )

    absent_count_by_emp:   dict = defaultdict(int)
    half_day_count_by_emp: dict = defaultdict(int)
    late_count_by_emp:     dict = defaultdict(int)
    working_days_by_emp:   dict = defaultdict(int)

    for employee in employees:
        eff_start, eff_end = window_by_emp[employee.id]
        for rec_date, rec_status in records_by_emp.get(employee.id, []):
            if not (eff_start <= rec_date <= eff_end):
                continue
            if rec_status not in _NON_WORKING:
                working_days_by_emp[employee.id] += 1
            if rec_status == AttendanceRecord.STATUS_ABSENT:
                absent_count_by_emp[employee.id] += 1
            elif rec_status == AttendanceRecord.STATUS_HALF_DAY:
                half_day_count_by_emp[employee.id] += 1
            elif rec_status == AttendanceRecord.STATUS_LATE:
                late_count_by_emp[employee.id] += 1

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

        absent_days  = Decimal(absent_count_by_emp.get(employee.id, 0))
        half_days    = Decimal(half_day_count_by_emp.get(employee.id, 0))
        late_count   = late_count_by_emp.get(employee.id, 0)
        # Late marks → LOP per the configured policy threshold (0 if late-mark LOP is disabled)
        late_lop     = (Decimal(late_count // late_per_lop) * late_lop_unit) if late_per_lop else Decimal('0')
        emp_lop      = absent_days + (half_days * Decimal('0.5')) + late_lop
        # Use actual working days from attendance records; fall back to settings default if no records
        emp_working_days = working_days_by_emp.get(employee.id) or 26
        tax_declaration = tax_declaration_by_employee.get(employee.id)
        computed[employee.id] = _compute_employee_payslip(
            salary_config, components, branch_config, statutory, adjustments, structure,
            lop_days=emp_lop,
            total_working_days=emp_working_days,
            cycle_month=cycle.cycle_start.month,
            esi_covered_earlier_this_period=employee.id in esi_covered_earlier_ids,
            proration_factor=proration_factor_by_emp.get(employee.id, Decimal('1')),
            is_metro=branch_obj.is_metro if branch_obj else False,
            tax_regime=tax_declaration.tax_regime if tax_declaration else EmployeeTaxDeclaration.REGIME_NEW,
            declared_investments=tax_declaration.declared_investments if tax_declaration else None,
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
