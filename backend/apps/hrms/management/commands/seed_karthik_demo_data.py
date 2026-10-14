"""
Management command: seed_karthik_demo_data

Fills in realistic demo data for the already-hired employee Karthik Pillai
(EMP00063) across every module — personal/statutory/bank details, family &
nomination, education & experience, salary/payslips, tax, leave, attendance,
expenses, documents, growth/appraisals, assets, HR help — so his record
looks complete everywhere (Employee Directory, ESS, Edit full record modal)
instead of showing empty sections.

DEMO / TEST DATA ONLY. Every amount, date, and name below is fabricated
placeholder content for local/dev verification — never run this against a
real employee or a production database. Idempotent: safe to run more than
once (existing rows are detected via get_or_create / explicit existence
checks and are never duplicated).

Run:  python manage.py seed_karthik_demo_data
"""
import random
from datetime import date, datetime, time, timedelta
from decimal import Decimal
from zoneinfo import ZoneInfo

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from apps.accounts.models import (
    CompanyAsset,
    EducationRecord,
    EDUCATION_LEVEL_BACHELORS,
    EPFNominee,
    FamilyMember,
    User,
    find_conflicting_pan_profile,
    normalize_and_validate_pan,
    WorkExperienceRecord,
)
from apps.attendance.models import (
    AttendancePunch,
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
    GOAL_ON_TRACK,
    Goal,
    PerformanceReview,
    ReviewCycle,
)

EMPLOYEE_ID = 'EMP00063'
DEMO_ANNUAL_CTC = Decimal('2200000.00')  # 22 LPA — AI & ML Specialist grade
REPORTING_MANAGER_ID = 'EMP00065'  # Head — Product Engineering, same branch


class Command(BaseCommand):
    help = (
        f'Seeds realistic full-record demo data for an already-hired employee across every '
        f'module. Defaults to {EMPLOYEE_ID} (Karthik Pillai) when no --employee-id/--email is given.'
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--employee-id', default=None,
            help=f'Employee ID to seed (e.g. EMP00076). Defaults to {EMPLOYEE_ID}.',
        )
        parser.add_argument(
            '--email', default=None,
            help='Alternative to --employee-id: look the employee up by email instead.',
        )

    def handle(self, *args, **options):
        employee_id = options.get('employee_id')
        email = options.get('email')
        if email:
            try:
                employee = User.objects.get(email__iexact=email)
            except User.DoesNotExist as exc:
                raise CommandError(f'No employee with email={email!r} found.') from exc
        else:
            target_id = employee_id or EMPLOYEE_ID
            try:
                employee = User.objects.get(employee_id=target_id)
            except User.DoesNotExist as exc:
                raise CommandError(f'No employee with employee_id={target_id!r} found.') from exc

        with transaction.atomic():
            self._seed_reporting_manager(employee)
            self._seed_personal_statutory(employee)
            self._seed_family_and_nominees(employee)
            self._seed_education_and_experience(employee)
            self._seed_attendance(employee)
            self._seed_leave(employee)
            self._seed_tax(employee)
            self._seed_payroll(employee)
            self._seed_expenses(employee)
            self._seed_documents(employee)
            self._seed_growth(employee)
            self._seed_assets_and_help(employee)

        self.stdout.write(self.style.SUCCESS('seed_karthik_demo_data completed.'))

    # ── Reporting manager ────────────────────────────────────────────────────

    def _seed_reporting_manager(self, employee: User) -> None:
        if employee.reporting_manager_id:
            self.stdout.write(f'Reporting manager already set: {employee.reporting_manager_id}')
            return
        manager = User.objects.filter(employee_id=REPORTING_MANAGER_ID).first()
        if manager:
            employee.reporting_manager = manager
            employee.save(update_fields=['reporting_manager', 'updated_at'])
            self.stdout.write(f'Reporting manager set to {manager.employee_id} ({manager.full_name}).')
        else:
            self.stdout.write(f'Reporting manager candidate {REPORTING_MANAGER_ID} not found — skipped.')

    # ── Personal identity, statutory & bank ──────────────────────────────────

    def _seed_personal_statutory(self, employee: User) -> None:
        profile = employee.profile
        changed = []

        def _set(field, value):
            if not getattr(profile, field):
                setattr(profile, field, value)
                changed.append(field)

        _set('date_of_birth', date(1994, 3, 18))
        _set('gender', 'male')
        _set('marital_status', 'married')
        _set('blood_group', 'B+')
        _set('nationality', 'Indian')
        _set('place_of_birth', 'Hyderabad')
        _set('father_name', 'Suresh Pillai')
        _set('personal_email', 'karthik.pillai.personal@example.com')
        _set('current_address', 'Flat 402, Lakeview Residency, Kondapur')
        _set('current_village', 'Kondapur')
        _set('current_district', 'Hyderabad')
        _set('current_state', 'Telangana')
        _set('current_pin_code', '500084')
        profile.permanent_same_as_current = True

        _set('account_holder_name', employee.full_name or 'Karthik Pillai')
        _set('bank_name', 'HDFC Bank')
        _set('bank_branch_name', 'Kondapur Branch')
        _set('account_type', 'savings')
        if not profile.account_number:
            profile.account_number = '50100123456789'
            changed.append('account_number')
        if not profile.ifsc_code:
            profile.ifsc_code = 'HDFC0001234'
            changed.append('ifsc_code')

        if not profile.pan_number:
            pan = normalize_and_validate_pan('BNZPP1234K')
            if find_conflicting_pan_profile(pan, exclude_profile_pk=profile.pk) is None:
                profile.pan_number = pan
                changed.append('pan_number')
        _set('aadhaar_number', '456723419087')
        _set('name_as_per_aadhar', employee.full_name or 'Karthik Pillai')
        _set('uan_number', '101234567890')
        _set('esi_number', '3412345678')
        profile.pf_covered = True
        profile.esi_covered = False

        _set('core_skills', 'Python, PyTorch, LLM fine-tuning, MLOps, computer vision')
        _set('certifications', 'AWS Certified Machine Learning – Specialty')

        _set('emergency_name', 'Divya Pillai')
        _set('emergency_relationship', 'spouse')
        _set('emergency_phone', '+91 90001 23456')
        _set('emergency_email', 'divya.pillai.demo@example.com')

        profile.save()
        self.stdout.write(f'EmployeeProfile: {len(changed)} field(s) populated ({", ".join(changed) or "none — already filled"}).')

    # ── Family & nomination ───────────────────────────────────────────────────

    def _seed_family_and_nominees(self, employee: User) -> None:
        # Checked per-relationship (not "any family member exists") so an
        # employee who already has e.g. just a father on file still gets a
        # spouse/child/nominees added, rather than the whole step no-opping.
        existing = set(FamilyMember.objects.filter(employee=employee).values_list('relationship', flat=True))
        created_any = False

        spouse = FamilyMember.objects.filter(employee=employee, relationship='spouse').first()
        if spouse is None:
            spouse = FamilyMember.objects.create(
                employee=employee, name='Divya Pillai', relationship='spouse',
                date_of_birth=date(1995, 7, 22), gender='female', blood_group='O+',
                is_dependent=True, order=0,
            )
            created_any = True

        child = FamilyMember.objects.filter(employee=employee, relationship='child').first()
        if child is None:
            child = FamilyMember.objects.create(
                employee=employee, name='Advaith Pillai', relationship='child',
                date_of_birth=date(2021, 11, 4), gender='male', blood_group='O+',
                is_dependent=True, order=1,
            )
            created_any = True

        if 'father' not in existing:
            FamilyMember.objects.create(
                employee=employee, name='Suresh Pillai', relationship='father',
                date_of_birth=date(1962, 2, 10), gender='male', blood_group='B+',
                is_dependent=False, order=2,
            )
            created_any = True

        if created_any:
            self.stdout.write('Family members created/completed: spouse, child, father.')
        else:
            self.stdout.write('Family members already present — skipped.')

        if not EPFNominee.objects.filter(employee=employee).exists():
            EPFNominee.objects.create(employee=employee, family_member=spouse, scheme='both', share_percentage=70, order=0)
            EPFNominee.objects.create(employee=employee, family_member=child, scheme='both', share_percentage=30, order=1)
            self.stdout.write('EPF nominees created: spouse 70%, child 30%.')
        else:
            self.stdout.write('EPF nominees already present — skipped.')

    # ── Education & experience ────────────────────────────────────────────────

    def _seed_education_and_experience(self, employee: User) -> None:
        if EducationRecord.objects.filter(employee=employee).exists():
            self.stdout.write('Education records already present — skipped.')
        else:
            EducationRecord.objects.create(
                employee=employee, level=EDUCATION_LEVEL_BACHELORS,
                institution='International Institute of Information Technology, Hyderabad',
                specialization='Computer Science (AI & ML)',
                percentage='8.7 CGPA', score_type='cgpa', score_value=Decimal('8.7'), score_scale=Decimal('10'),
                start_date=date(2012, 8, 1), end_date=date(2016, 5, 31),
                is_highest=True, is_completed=True, order=0,
            )
            self.stdout.write('Education record created: B.Tech, IIIT Hyderabad.')

        if WorkExperienceRecord.objects.filter(employee=employee).exists():
            self.stdout.write('Experience records already present — skipped.')
        else:
            WorkExperienceRecord.objects.create(
                employee=employee, employer_name='DeepVision Analytics Pvt Ltd',
                designation='Machine Learning Engineer', employment_type='full_time',
                start_date=date(2016, 7, 1), end_date=date(2026, 5, 8),
                responsibilities='Built and deployed computer-vision and NLP models for retail analytics clients.',
                reason_for_leaving='Seeking a larger-scale platform engineering role.',
                order=0,
            )
            self.stdout.write('Experience record created: DeepVision Analytics Pvt Ltd.')

    # ── Attendance ────────────────────────────────────────────────────────────

    def _seed_attendance(self, employee: User) -> None:
        rng = random.Random(f'attendance-{employee.id}')
        ist = ZoneInfo('Asia/Kolkata')
        branch_obj = Branch.objects.filter(branch_name=employee.branch).first()
        today = timezone.localdate()
        created = 0
        punches_created = 0
        d = today - timedelta(days=27)
        while d <= today:
            if d.weekday() < 5:
                rec = AttendanceRecord.objects.filter(employee=employee, date=d).first()
                if rec is None:
                    late = rng.random() < 0.2
                    in_hour, in_minute = (9, rng.randint(16, 35)) if late else (9, rng.randint(0, 12))
                    work_minutes = rng.randint(478, 525)
                    in_time = time(in_hour, in_minute)
                    out_dt = datetime.combine(d, in_time) + timedelta(minutes=work_minutes)
                    rec = AttendanceRecord.objects.create(
                        employee=employee,
                        date=d,
                        status=AttendanceRecord.STATUS_LATE if late else AttendanceRecord.STATUS_PRESENT,
                        first_punch_in=in_time,
                        last_punch_out=out_dt.time(),
                        total_working_minutes=work_minutes,
                        is_late=late,
                    )
                    created += 1

                if rec.first_punch_in and rec.last_punch_out and not AttendancePunch.objects.filter(
                    employee=employee, punched_at__date=d,
                ).exists():
                    in_dt = datetime.combine(d, rec.first_punch_in, tzinfo=ist)
                    out_dt_aware = datetime.combine(d, rec.last_punch_out, tzinfo=ist)
                    AttendancePunch.objects.create(
                        employee=employee, branch=branch_obj, punch_type=AttendancePunch.PUNCH_IN,
                        punched_at=in_dt, source=AttendancePunch.SOURCE_WEB,
                        attendance_mode=AttendancePunch.MODE_OFFICE,
                    )
                    AttendancePunch.objects.create(
                        employee=employee, branch=branch_obj, punch_type=AttendancePunch.PUNCH_OUT,
                        punched_at=out_dt_aware, source=AttendancePunch.SOURCE_WEB,
                        attendance_mode=AttendancePunch.MODE_OFFICE,
                    )
                    punches_created += 2
            d += timedelta(days=1)
        self.stdout.write(f'Attendance: {created} AttendanceRecord rows + {punches_created} AttendancePunch rows created (weekdays, last ~4 weeks).')

        week_starts = [today - timedelta(days=today.weekday() + 7), today - timedelta(days=today.weekday() + 14)]
        ts_created = 0
        for week_start in week_starts:
            _, made = WeeklyTimesheetSubmission.objects.get_or_create(employee=employee, week_start=week_start)
            ts_created += int(made)
        self.stdout.write(f'Weekly timesheet submissions: {ts_created} created ({len(week_starts)} weeks checked).')

    # ── Leave ─────────────────────────────────────────────────────────────────

    def _seed_leave(self, employee: User) -> None:
        year = timezone.localdate().year
        balances = [
            (LEAVE_EARNED, Decimal('10'), Decimal('3')),
            (LEAVE_CASUAL, Decimal('8'),  Decimal('2')),
            (LEAVE_SICK,   Decimal('8'),  Decimal('1')),
        ]
        for leave_type, total_days, used_days in balances:
            bal, made = LeaveBalance.objects.get_or_create(
                employee=employee, leave_type=leave_type, year=year,
                defaults=dict(total_days=total_days, used_days=used_days),
            )
            self.stdout.write(f'LeaveBalance {leave_type} {year}: {"created" if made else "existing"}.')

        today = timezone.localdate()
        _, made_pending = LeaveRequest.objects.get_or_create(
            employee=employee, leave_type=LEAVE_CASUAL, status=REQ_PENDING,
            start_date=today + timedelta(days=6),
            defaults=dict(
                end_date=today + timedelta(days=6),
                total_days=Decimal('1'),
                reason='Personal work.',
            ),
        )
        approved_start = today - timedelta(days=18)
        _, made_approved = LeaveRequest.objects.get_or_create(
            employee=employee, leave_type=LEAVE_EARNED, status=REQ_APPROVED,
            start_date=approved_start,
            defaults=dict(
                end_date=approved_start + timedelta(days=1),
                total_days=Decimal('2'),
                reason='Family function.',
                l1_approver=employee.reporting_manager or employee,
                l1_status='approved',
                l1_actioned_at=timezone.now() - timedelta(days=16),
            ),
        )
        self.stdout.write(
            f'Leave requests: pending={"created" if made_pending else "existing"}, '
            f'approved={"created" if made_approved else "existing"}.'
        )

    # ── Payslips ──────────────────────────────────────────────────────────────

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

        components = list(structure.components.filter(is_active=True).order_by('order'))
        branch_obj = Branch.objects.filter(branch_name=employee.branch).select_related('state').first()
        branch_config = BranchPayrollConfig.objects.filter(branch=branch_obj).first() if branch_obj else None
        statutory = StatutoryConfig.objects.filter(state=branch_obj.state).first() if branch_obj and branch_obj.state else None

        tax_declaration = (
            EmployeeTaxDeclaration.objects
            .filter(employee=employee)
            .order_by('-financial_year_start')
            .first()
        )
        tax_regime = tax_declaration.tax_regime if tax_declaration else EmployeeTaxDeclaration.REGIME_NEW
        declared_investments = tax_declaration.declared_investments if tax_declaration else None

        cycle_specs = [
            (date(2026, 5, 25), date(2026, 6, 24),  date(2026, 6, 30), 'paid'),
            (date(2026, 6, 25), date(2026, 7, 24),  date(2026, 7, 30), 'paid'),
            (date(2026, 7, 25), date(2026, 8, 24),  date(2026, 8, 30), 'sent'),
        ]
        payslip_count = 0
        for cycle_start, cycle_end, pay_date, final_state in cycle_specs:
            cycle, _ = PayrollCycle.objects.get_or_create(
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

    # ── Tax ───────────────────────────────────────────────────────────────────

    def _seed_tax(self, employee: User) -> None:
        today = timezone.localdate()
        fy_start = today.year if today.month >= 4 else today.year - 1
        declaration, made = EmployeeTaxDeclaration.objects.get_or_create(
            employee=employee, financial_year_start=fy_start,
            defaults=dict(
                tax_regime=EmployeeTaxDeclaration.REGIME_NEW,
                declared_investments={'80C': 60000},
                status=EmployeeTaxDeclaration.STATUS_DRAFT,
            ),
        )
        self.stdout.write(f'EmployeeTaxDeclaration FY{fy_start}: {"created" if made else "existing"}.')

    # ── Expenses ──────────────────────────────────────────────────────────────

    def _seed_expenses(self, employee: User) -> None:
        today = timezone.localdate()
        branch = Branch.objects.filter(branch_name=employee.branch).first()

        def _next_expense_number() -> int:
            last = (Expense.objects.exclude(expense_number__isnull=True)
                    .order_by('-expense_number').values_list('expense_number', flat=True).first())
            return (last or 0) + 1

        _, made_pending = Expense.objects.get_or_create(
            employee=employee, title='GPU cloud credits — model training', status='pending',
            defaults=dict(
                expense_number=_next_expense_number(), branch=branch, category='other',
                amount=Decimal('9400.00'), expense_date=today - timedelta(days=5),
                description='Cloud GPU hours for fine-tuning the Q3 recommendation model.',
            ),
        )
        _, made_approved = Expense.objects.get_or_create(
            employee=employee, title='Team lunch — sprint wrap-up', status='approved',
            defaults=dict(
                expense_number=_next_expense_number(), branch=branch, category='meals',
                amount=Decimal('1800.00'), expense_date=today - timedelta(days=14),
                description='Lunch with the ML team after closing out the sprint.',
            ),
        )
        self.stdout.write(
            f'Expenses: pending={"created" if made_pending else "existing"}, '
            f'approved={"created" if made_approved else "existing"}.'
        )

    # ── Documents ─────────────────────────────────────────────────────────────

    def _seed_documents(self, employee: User) -> None:
        rows = [
            (EMP_DOC_IDENTITY,   'Aadhaar_card_scan.pdf',        EMP_DOC_VERIFIED, timezone.now() - timedelta(days=60)),
            (EMP_DOC_TAX_PROOF,  'Form16_FY2025-26.pdf',         EMP_DOC_PENDING,  None),
            (EMP_DOC_EDUCATION,  'BTech_degree_certificate.pdf', EMP_DOC_VERIFIED, timezone.now() - timedelta(days=55)),
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

    # ── Growth / Appraisals ───────────────────────────────────────────────────

    def _seed_growth(self, employee: User) -> None:
        cycle = ReviewCycle.objects.filter(status=CYCLE_ACTIVE).first()
        if cycle is None:
            cycle = ReviewCycle.objects.create(
                name='Q3 2026',
                period_start=date(2026, 7, 1), period_end=date(2026, 9, 30),
                self_review_due=date(2026, 10, 5), manager_review_due=date(2026, 10, 12),
                status=CYCLE_ACTIVE, created_by=employee,
            )
        self.stdout.write(f'ReviewCycle "{cycle.name}" ready.')

        _, goal_made = Goal.objects.get_or_create(
            employee=employee, cycle=cycle, title='Ship v2 recommendation model to production',
            defaults=dict(
                description='Key ML delivery goal for this cycle.',
                target_metric='Model live in production with measured lift over baseline.',
                status=GOAL_ON_TRACK, weight_percent=60,
                due_date=cycle.period_end, created_by=employee,
            ),
        )
        self.stdout.write(f'Goal: {"created" if goal_made else "existing"}.')

        _, review_created = PerformanceReview.objects.get_or_create(
            employee=employee, cycle=cycle,
            defaults=dict(
                metric_reference='Model accuracy uplift, deployment velocity, incident count.',
                what_changed='Led the migration of the recommendation pipeline to the new feature store.',
                key_strengths='Strong applied-ML execution and clear experiment documentation.',
                self_rating='4',
            ),
        )
        self.stdout.write(f'PerformanceReview (draft self-review): {"created" if review_created else "existing"}.')

    # ── Assets / HR Help ──────────────────────────────────────────────────────

    def _seed_assets_and_help(self, employee: User) -> None:
        _, laptop_created = CompanyAsset.objects.get_or_create(
            employee=employee, asset_type='laptop',
            defaults=dict(tag_number='LAP-3391', condition='good', issued_at=employee.date_of_joining),
        )
        _, mobile_created = CompanyAsset.objects.get_or_create(
            employee=employee, asset_type='mobile_phone',
            defaults=dict(tag_number='MOB-1182', condition='new', issued_at=employee.date_of_joining),
        )
        self.stdout.write(
            f'CompanyAsset: laptop={"created" if laptop_created else "existing"}, '
            f'mobile={"created" if mobile_created else "existing"}.'
        )

        def _next_request_number() -> int:
            last = (HRHelpRequest.objects.exclude(request_number__isnull=True)
                    .order_by('-request_number').values_list('request_number', flat=True).first())
            return (last or 0) + 1

        _, help_created = HRHelpRequest.objects.get_or_create(
            submitted_by=employee, topic='asset_request',
            defaults=dict(
                request_number=_next_request_number(),
                priority='normal',
                message='Requesting an external GPU dock for local model experimentation.',
                status='open',
            ),
        )
        self.stdout.write(f'HR Help request: {"created" if help_created else "existing"}.')
