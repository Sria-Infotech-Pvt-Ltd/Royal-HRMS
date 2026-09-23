"""
Management command: seed_ess_demo_data

Turns the sriainfotech@gmail.com demo account into a real, fully-placed
employee (real employee_id, a real Position via Placement, designation/
department synced from that position) and then seeds realistic demo data
across every Employee Self-Service (ESS) tab — Attendance, Leave, Payslips,
Tax, Expenses, Documents, Growth/Appraisals, Policies & Assets, HR Help —
so the module can be visually verified end-to-end without any tab
rendering an empty state.

DEMO / TEST DATA ONLY. Every amount, date, and name below is fabricated
placeholder content for local/dev verification — never run this against a
real employee or a production database. Idempotent: safe to run more than
once (existing rows are detected via get_or_create / explicit existence
checks and are never duplicated).

Run:  python manage.py seed_ess_demo_data
"""
import random
from datetime import date, datetime, time, timedelta
from decimal import Decimal

from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from apps.accounts.models import CompanyAsset, EmployeeCodeSettings, Position, User
from apps.accounts.services_placement import assign_position
from apps.attendance.models import (
    AttendanceCorrection,
    AttendanceRecord,
    WeeklyTimesheetSubmission,
)
from apps.branch.models import Branch
from apps.hrms.models import (
    EMP_DOC_EDUCATION,
    EMP_DOC_IDENTITY,
    EMP_DOC_PENDING,
    EMP_DOC_TAX_PROOF,
    EMP_DOC_VERIFIED,
    EmployeeDocumentSubmission,
    Expense,
    HRHelpRequest,
    LEAVE_CASUAL,
    LEAVE_EARNED,
    LEAVE_SICK,
    LeaveBalance,
    LeaveRequest,
    REQ_APPROVED,
    REQ_PENDING,
)
from apps.payroll.models import (
    BranchPayrollConfig,
    EmployeeSalaryConfig,
    EmployeePayslip,
    EmployeeTaxDeclaration,
    PayrollCycle,
    SalaryComponent,
    SalaryStructure,
    StatutoryConfig,
)
from apps.payroll.views.shared import _compute_employee_payslip
from apps.payroll.services_income_tax import estimate_monthly_tds
from apps.performance.models import (
    CYCLE_ACTIVE,
    GOAL_AT_RISK,
    GOAL_ON_TRACK,
    Goal,
    PerformanceReview,
    ReviewCycle,
)

DEMO_EMAIL = 'sriainfotech@gmail.com'
DEMO_FIRST_NAME = 'Arjun'
DEMO_LAST_NAME = 'Mehta'
DEMO_FULL_NAME = f'{DEMO_FIRST_NAME} {DEMO_LAST_NAME}'
DEMO_POSITION_ID = '50007d4e-4e8b-45c1-92ed-a0f0903f6f0e'
DEMO_HIRE_DATE = date(2022, 6, 1)
DEMO_ANNUAL_CTC = Decimal('4800000.00')  # 48 LPA — senior engineering-leadership grade M2


class Command(BaseCommand):
    help = 'Seeds realistic ESS demo data for the sriainfotech@gmail.com account.'

    def handle(self, *args, **options):
        with transaction.atomic():
            employee = self._ensure_real_employee()
            self._seed_attendance(employee)
            self._seed_leave(employee)
            # Tax declaration seeded before payroll so _seed_payroll can resolve
            # a real regime/declared-investments pair for its income-tax calc
            # instead of falling back to defaults for every seeded payslip.
            self._seed_tax(employee)
            self._seed_payroll(employee)
            self._seed_expenses(employee)
            self._seed_documents(employee)
            self._seed_growth(employee)
            self._seed_assets_and_help(employee)

        self.stdout.write(self.style.SUCCESS('seed_ess_demo_data completed.'))

    # ── Step 1: turn the demo account into a real employee ─────────────────

    def _ensure_real_employee(self) -> User:
        employee = User.objects.get(email=DEMO_EMAIL)
        position = Position.objects.get(id=DEMO_POSITION_ID)

        if not employee.employee_id:
            employee.employee_id = EmployeeCodeSettings.generate_employee_id(
                first_name=DEMO_FIRST_NAME,
                last_name=DEMO_LAST_NAME,
                date_of_joining=DEMO_HIRE_DATE,
            )
            self.stdout.write(f'Generated employee_id: {employee.employee_id}')
        else:
            self.stdout.write(f'employee_id already set: {employee.employee_id}')

        if employee.full_name == DEMO_EMAIL or not employee.full_name.strip():
            employee.full_name = DEMO_FULL_NAME

        if not employee.date_of_joining:
            employee.date_of_joining = DEMO_HIRE_DATE

        if not employee.branch:
            # Only branch that exists in this environment today — every real
            # employee needs one (geofencing, payroll branch/state resolution).
            only_branch = Branch.objects.first()
            if only_branch:
                employee.branch = only_branch.branch_name

        employee.save()

        assign_position(
            employee, position,
            effective_from=employee.date_of_joining,
            created_by=employee,
        )
        employee.refresh_from_db()
        self.stdout.write(
            f'Position assigned: {position.title} — designation={employee.designation!r} '
            f'department={employee.department!r}'
        )
        return employee

    # ── 1. Attendance ────────────────────────────────────────────────────────

    def _seed_attendance(self, employee: User) -> None:
        rng = random.Random(f'attendance-{employee.id}')
        today = timezone.localdate()
        created = 0
        d = today - timedelta(days=27)
        while d <= today:
            if d.weekday() < 5 and not AttendanceRecord.objects.filter(employee=employee, date=d).exists():
                late = rng.random() < 0.25
                in_hour, in_minute = (9, rng.randint(16, 35)) if late else (9, rng.randint(0, 12))
                work_minutes = rng.randint(478, 525)
                out_dt = datetime.combine(d, time(in_hour, in_minute)) + timedelta(minutes=work_minutes)
                AttendanceRecord.objects.create(
                    employee=employee,
                    date=d,
                    status=AttendanceRecord.STATUS_LATE if late else AttendanceRecord.STATUS_PRESENT,
                    first_punch_in=time(in_hour, in_minute),
                    last_punch_out=out_dt.time(),
                    total_working_minutes=work_minutes,
                    is_late=late,
                )
                created += 1
            d += timedelta(days=1)
        self.stdout.write(f'Attendance: {created} AttendanceRecord rows created (weekdays, last ~4 weeks).')

        pending_date = today - timedelta(days=3)
        _, made_pending = AttendanceCorrection.objects.get_or_create(
            employee=employee, date=pending_date, status=AttendanceCorrection.STATUS_PENDING,
            defaults=dict(
                punch_type=AttendanceCorrection.PUNCH_OUT,
                requested_out_time=time(18, 45),
                reason=AttendanceCorrection.REASON_FORGOT,
                notes='Forgot to punch out after a late client call — clocked out from memory.',
                created_by=employee,
            ),
        )
        approved_date = today - timedelta(days=12)
        _, made_approved = AttendanceCorrection.objects.get_or_create(
            employee=employee, date=approved_date, status=AttendanceCorrection.STATUS_APPROVED,
            defaults=dict(
                punch_type=AttendanceCorrection.PUNCH_BOTH,
                requested_in_time=time(9, 10),
                requested_out_time=time(18, 20),
                reason=AttendanceCorrection.REASON_BIOMETRIC,
                notes='Office biometric device was down for the morning; timings confirmed by security log.',
                reviewed_by=employee,
                reviewed_at=timezone.now() - timedelta(days=10),
                created_by=employee,
            ),
        )
        self.stdout.write(
            f'Attendance corrections: pending={"created" if made_pending else "existing"}, '
            f'approved={"created" if made_approved else "existing"}.'
        )

        week_starts = [today - timedelta(days=today.weekday() + 7), today - timedelta(days=today.weekday() + 14)]
        ts_created = 0
        for week_start in week_starts:
            _, made = WeeklyTimesheetSubmission.objects.get_or_create(employee=employee, week_start=week_start)
            ts_created += int(made)
        self.stdout.write(f'Weekly timesheet submissions: {ts_created} created ({len(week_starts)} weeks checked).')

    # ── 2. Leave ─────────────────────────────────────────────────────────────

    def _seed_leave(self, employee: User) -> None:
        year = timezone.localdate().year
        balances = [
            (LEAVE_EARNED, Decimal('13.5'), Decimal('4.5')),
            (LEAVE_CASUAL, Decimal('9'),    Decimal('3')),
            (LEAVE_SICK,   Decimal('12'),   Decimal('2')),
        ]
        for leave_type, total_days, used_days in balances:
            _, made = LeaveBalance.objects.get_or_create(
                employee=employee, leave_type=leave_type, year=year,
                defaults=dict(total_days=total_days, used_days=used_days),
            )
            self.stdout.write(f'LeaveBalance {leave_type} {year}: {"created" if made else "existing"} '
                               f'({total_days} total / {used_days} used).')

        today = timezone.localdate()
        _, made_pending = LeaveRequest.objects.get_or_create(
            employee=employee, leave_type=LEAVE_CASUAL, status=REQ_PENDING,
            start_date=today + timedelta(days=9),
            defaults=dict(
                end_date=today + timedelta(days=10),
                total_days=Decimal('2'),
                reason='Attending a family function out of town.',
            ),
        )
        approved_start = today - timedelta(days=20)
        _, made_approved = LeaveRequest.objects.get_or_create(
            employee=employee, leave_type=LEAVE_EARNED, status=REQ_APPROVED,
            start_date=approved_start,
            defaults=dict(
                end_date=approved_start + timedelta(days=2),
                total_days=Decimal('3'),
                reason='Planned vacation.',
                l1_approver=employee,
                l1_status='approved',
                l1_actioned_at=timezone.now() - timedelta(days=18),
            ),
        )
        self.stdout.write(
            f'Leave requests: pending={"created" if made_pending else "existing"}, '
            f'approved={"created" if made_approved else "existing"}.'
        )

    # ── 3. Payslips ──────────────────────────────────────────────────────────

    def _seed_payroll(self, employee: User) -> None:
        structure, struct_created = SalaryStructure.objects.get_or_create(
            name='Standard Structure',
            defaults=dict(description='Default 3-component structure (Basic/HRA/Special Allowance).',
                          is_default=True, is_active=True),
        )
        if struct_created:
            SalaryComponent.objects.bulk_create([
                SalaryComponent(structure=structure, name='Basic', component_type=SalaryComponent.TYPE_EARNING,
                                 calculation_type=SalaryComponent.CALC_PCT_CTC, value=Decimal('40'), order=0),
                SalaryComponent(structure=structure, name='HRA', component_type=SalaryComponent.TYPE_ALLOWANCE,
                                 calculation_type=SalaryComponent.CALC_PCT_CTC, value=Decimal('20'), order=1),
                SalaryComponent(structure=structure, name='Special Allowance',
                                 component_type=SalaryComponent.TYPE_ALLOWANCE,
                                 calculation_type=SalaryComponent.CALC_PCT_CTC, value=Decimal('40'), order=2),
            ])
        self.stdout.write(f'Salary structure "{structure.name}": {"created" if struct_created else "existing"} '
                           f'with {structure.components.count()} components.')

        config = EmployeeSalaryConfig.objects.filter(employee=employee, is_active=True).order_by('-effective_from').first()
        if config is None:
            config = EmployeeSalaryConfig.objects.create(
                employee=employee, annual_ctc=DEMO_ANNUAL_CTC, salary_structure=structure,
                effective_from=employee.date_of_joining, reason='', is_active=True,
            )
            self.stdout.write(f'EmployeeSalaryConfig created: annual_ctc=₹{DEMO_ANNUAL_CTC}.')
        else:
            self.stdout.write(f'EmployeeSalaryConfig already exists: annual_ctc=₹{config.annual_ctc}.')

        # Follows PayrollSettings' own cycle_start_day=25/cycle_end_day=24 convention.
        cycle_specs = [
            (date(2026, 5, 25), date(2026, 6, 24),  date(2026, 6, 30), 'paid'),
            (date(2026, 6, 25), date(2026, 7, 24),  date(2026, 7, 30), 'paid'),
            (date(2026, 7, 25), date(2026, 8, 24),  date(2026, 8, 30), 'sent'),
        ]
        # This employee's role (system_admin) is deliberately excluded from
        # _eligible_employees_qs()/process_payroll_cycle()'s whole-company
        # run (admins aren't paid via payroll cycles), so that entry point
        # would silently compute zero payslips for them. _compute_employee_
        # payslip is the real, standalone formula that function itself calls
        # per employee — used directly here against the same resolved inputs
        # (structure components, branch config, statutory config) so the
        # numbers still foot against the genuine calculation logic; only the
        # whole-company eligibility filter is bypassed.
        components = list(structure.components.filter(is_active=True).order_by('order'))
        branch_obj = Branch.objects.filter(branch_name=employee.branch).select_related('state').first()
        branch_config = BranchPayrollConfig.objects.filter(branch=branch_obj).first() if branch_obj else None
        statutory = StatutoryConfig.objects.filter(state=branch_obj.state).first() if branch_obj and branch_obj.state else None

        # Real tax declaration seeded by _seed_tax() just above — feeds the
        # same estimate_monthly_tds() calculation the real payroll engine
        # uses, so this demo employee's income_tax isn't a fabricated figure.
        tax_declaration = (
            EmployeeTaxDeclaration.objects
            .filter(employee=employee)
            .order_by('-financial_year_start')
            .first()
        )
        tax_regime = tax_declaration.tax_regime if tax_declaration else EmployeeTaxDeclaration.REGIME_NEW
        declared_investments = tax_declaration.declared_investments if tax_declaration else None

        payslip_count = 0
        for cycle_start, cycle_end, pay_date, final_state in cycle_specs:
            cycle, cycle_created = PayrollCycle.objects.get_or_create(
                cycle_start=cycle_start, cycle_end=cycle_end,
                defaults=dict(
                    pay_date=pay_date, status=PayrollCycle.STATUS_ATTENDANCE_APPROVED,
                    created_by=employee,
                    attendance_approved_by_l1=employee, attendance_approved_by_l2=employee,
                    attendance_l1_approved_at=timezone.now(), attendance_l2_approved_at=timezone.now(),
                ),
            )
            payslip = EmployeePayslip.objects.filter(cycle=cycle, employee=employee).first()
            if payslip is None:
                fields = _compute_employee_payslip(
                    config, components, branch_config, statutory, adjustments=[], structure=structure,
                    lop_days=Decimal('0'), total_working_days=26, cycle_month=cycle_start.month,
                    esi_covered_earlier_this_period=False, proration_factor=Decimal('1'),
                    is_metro=branch_obj.is_metro if branch_obj else False,
                    tax_regime=tax_regime, declared_investments=declared_investments,
                )
                payslip = EmployeePayslip.objects.create(cycle=cycle, employee=employee, **fields)
            elif not payslip.income_tax:
                # Backfill: this payslip was seeded in an earlier run of this
                # command, before income_tax existed. Safe to recompute here —
                # this is the demo employee's own seeded row, not a real,
                # already-reconciled payroll record.
                income_tax = estimate_monthly_tds(payslip.gross_earnings, tax_regime, declared_investments)
                if income_tax:
                    payslip.income_tax = income_tax
                    payslip.total_deductions = payslip.total_deductions + income_tax
                    payslip.net_pay = payslip.net_pay - income_tax
                    payslip.save(update_fields=['income_tax', 'total_deductions', 'net_pay', 'updated_at'])

            if payslip is not None:
                payslip_count += 1
                if final_state == 'paid' and payslip.status != EmployeePayslip.STATUS_PAID:
                    payslip.status = EmployeePayslip.STATUS_PAID
                    payslip.sent_at = payslip.sent_at or timezone.now() - timedelta(days=45)
                    payslip.paid_at = timezone.now() - timedelta(days=40)
                    payslip.save(update_fields=['status', 'sent_at', 'paid_at', 'updated_at'])
                    cycle.status = PayrollCycle.STATUS_PAID
                    cycle.paid_at = payslip.paid_at
                    cycle.marked_paid_by = employee
                    cycle.save(update_fields=['status', 'paid_at', 'marked_paid_by', 'updated_at'])
                elif final_state == 'sent' and payslip.status not in (
                    EmployeePayslip.STATUS_SENT, EmployeePayslip.STATUS_ACKNOWLEDGED,
                ):
                    payslip.status = EmployeePayslip.STATUS_SENT
                    payslip.sent_at = timezone.now() - timedelta(days=10)
                    payslip.query_deadline = payslip.sent_at + timedelta(hours=24)
                    payslip.save(update_fields=['status', 'sent_at', 'query_deadline', 'updated_at'])
                    cycle.status = PayrollCycle.STATUS_QUERY_WINDOW_OPEN
                    cycle.query_window_closes_at = payslip.query_deadline
                    cycle.save(update_fields=['status', 'query_window_closes_at', 'updated_at'])
        self.stdout.write(f'Payslips: {payslip_count} EmployeePayslip rows present across {len(cycle_specs)} cycles.')

    # ── 4. Tax ───────────────────────────────────────────────────────────────

    def _seed_tax(self, employee: User) -> None:
        today = timezone.localdate()
        # India FY runs Apr-Mar; financial_year_start is the calendar year the FY begins in.
        fy_start = today.year if today.month >= 4 else today.year - 1
        declaration, made = EmployeeTaxDeclaration.objects.get_or_create(
            employee=employee, financial_year_start=fy_start,
            defaults=dict(
                tax_regime=EmployeeTaxDeclaration.REGIME_OLD,
                declared_investments={'80C': 120000, 'HRA': 180000},
                status=EmployeeTaxDeclaration.STATUS_DRAFT,
            ),
        )
        self.stdout.write(f'EmployeeTaxDeclaration FY{fy_start}: {"created" if made else "existing"} '
                           f'(status={declaration.status}).')

    # ── 5. Expenses ──────────────────────────────────────────────────────────

    def _seed_expenses(self, employee: User) -> None:
        today = timezone.localdate()
        branch = Branch.objects.filter(branch_name=employee.branch).first()

        def _next_expense_number() -> int:
            last = (Expense.objects.exclude(expense_number__isnull=True)
                    .order_by('-expense_number').values_list('expense_number', flat=True).first())
            return (last or 0) + 1

        _, made_pending = Expense.objects.get_or_create(
            employee=employee, title='Client visit — Bengaluru round trip', status='pending',
            defaults=dict(
                expense_number=_next_expense_number(), branch=branch, category='travel',
                amount=Decimal('18500.00'), expense_date=today - timedelta(days=4),
                description='Flight + cab fare for a partner engineering review at the Bengaluru office.',
            ),
        )
        _, made_approved = Expense.objects.get_or_create(
            employee=employee, title='Team offsite working lunch', status='approved',
            defaults=dict(
                expense_number=_next_expense_number(), branch=branch, category='meals',
                amount=Decimal('3200.00'), expense_date=today - timedelta(days=15),
                description='Working lunch with the platform team during the quarterly planning offsite.',
            ),
        )
        self.stdout.write(
            f'Expenses: pending={"created" if made_pending else "existing"}, '
            f'approved={"created" if made_approved else "existing"}.'
        )

    # ── 6. Documents ─────────────────────────────────────────────────────────

    def _seed_documents(self, employee: User) -> None:
        rows = [
            (EMP_DOC_IDENTITY,   'Aadhaar_card_scan.pdf',          EMP_DOC_PENDING,  None),
            (EMP_DOC_TAX_PROOF,  'Form16_FY2025-26.pdf',           EMP_DOC_VERIFIED, timezone.now() - timedelta(days=30)),
            (EMP_DOC_EDUCATION,  'BTech_degree_certificate.pdf',   EMP_DOC_PENDING,  None),
        ]
        created = 0
        for category, file_name, status, reviewed_at in rows:
            _, made = EmployeeDocumentSubmission.objects.get_or_create(
                employee=employee, category=category, file_name=file_name,
                defaults=dict(
                    status=status,
                    reviewed_at=reviewed_at,
                    reviewed_by=employee if reviewed_at else None,
                ),
            )
            created += int(made)
        self.stdout.write(f'Document submissions: {created} created ({len(rows)} checked).')

    # ── 7. Growth / Appraisals ───────────────────────────────────────────────

    def _seed_growth(self, employee: User) -> None:
        cycle = ReviewCycle.objects.filter(status=CYCLE_ACTIVE).first()
        cycle_created = False
        if cycle is None:
            cycle = ReviewCycle.objects.create(
                name='Q3 2026',
                period_start=date(2026, 7, 1), period_end=date(2026, 9, 30),
                self_review_due=date(2026, 10, 5), manager_review_due=date(2026, 10, 12),
                status=CYCLE_ACTIVE, created_by=employee,
            )
            cycle_created = True
        self.stdout.write(f'ReviewCycle "{cycle.name}": {"created" if cycle_created else "existing (reused)"}.')

        goal_specs = [
            ('Ship unified platform migration v2', GOAL_ON_TRACK, 60,
             'All core services migrated with zero downtime.'),
            ('Reduce infra cost by 15% this quarter', GOAL_AT_RISK, 40,
             'Cloud spend reduced by 15% QoQ without impacting SLAs.'),
        ]
        goals_created = 0
        for title, status, weight, target_metric in goal_specs:
            _, made = Goal.objects.get_or_create(
                employee=employee, cycle=cycle, title=title,
                defaults=dict(
                    description=f'Key engineering-leadership goal for {cycle.name}.',
                    target_metric=target_metric, status=status, weight_percent=weight,
                    due_date=cycle.period_end, created_by=employee,
                ),
            )
            goals_created += int(made)
        self.stdout.write(f'Goals: {goals_created} created ({len(goal_specs)} checked).')

        review, review_created = PerformanceReview.objects.get_or_create(
            employee=employee, cycle=cycle,
            defaults=dict(
                metric_reference='Platform migration velocity, infra cost trend, team delivery metrics.',
                what_changed='Led the v2 platform migration kickoff and restructured the platform team '
                             'into two focused pods.',
                key_strengths='Strong cross-team execution and stakeholder communication under a tight timeline.',
                self_rating='4',
                # Draft — deliberately not yet submitted (self_submitted_at stays null).
            ),
        )
        self.stdout.write(f'PerformanceReview (draft self-review): {"created" if review_created else "existing"}.')

    # ── 8 & 9. Policies & Assets / HR Help ───────────────────────────────────

    def _seed_assets_and_help(self, employee: User) -> None:
        _, asset_created = CompanyAsset.objects.get_or_create(
            employee=employee, asset_type='laptop',
            defaults=dict(
                tag_number='LAP-2286', condition='good',
                issued_at=employee.date_of_joining,
            ),
        )
        self.stdout.write(f'CompanyAsset (laptop): {"created" if asset_created else "existing"}.')

        def _next_request_number() -> int:
            last = (HRHelpRequest.objects.exclude(request_number__isnull=True)
                    .order_by('-request_number').values_list('request_number', flat=True).first())
            return (last or 0) + 1

        _, help_created_1 = HRHelpRequest.objects.get_or_create(
            submitted_by=employee, topic='asset_request',
            defaults=dict(
                request_number=_next_request_number(),
                priority='normal',
                message='Requesting a docking station and an external monitor for my home office setup.',
                status='in_progress',
            ),
        )
        _, help_created_2 = HRHelpRequest.objects.get_or_create(
            submitted_by=employee, topic='payroll_query',
            defaults=dict(
                request_number=_next_request_number(),
                priority='normal',
                message='Query regarding the HRA component change reflected in this month\'s payslip.',
                status='open',
            ),
        )
        self.stdout.write(
            f'HR Help requests: asset_request={"created" if help_created_1 else "existing"}, '
            f'payroll_query={"created" if help_created_2 else "existing"}.'
        )
