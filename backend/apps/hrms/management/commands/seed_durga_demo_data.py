"""
Management command: seed_durga_demo_data

DEMO / TEST DATA ONLY. Creates one fresh demo employee ("Durga Prasad",
email gdurgaprasad065@gmail.com) via the same hire-path logic as
seed_dummy_employees.py (create_user + assign_position + leave allocation +
weekly-off assignment), re-seated into the exact Position the original
EMP00013 held (now vacant — its Placement rows were removed as part of a
client-demo database reset), then fills in realistic demo data across every
module the same way seed_karthik_demo_data.py does, so the record looks
complete everywhere instead of showing empty sections.

Every amount, date, and name below is fabricated placeholder content for
demo purposes — never run this against a real employee or production data
with real people in it. Idempotent: safe to re-run (existing rows are
detected via get_or_create / explicit existence checks).

Run:  python manage.py seed_durga_demo_data
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
    EmployeeCodeSettings,
    EmployeeProfile,
    EPFNominee,
    FamilyMember,
    Position,
    User,
    WorkExperienceRecord,
    find_conflicting_pan_profile,
    normalize_and_validate_pan,
)
from apps.accounts.services_placement import assign_position
from apps.attendance.models import (
    AttendancePunch,
    AttendanceRecord,
    WeeklyDayPolicy,
    WeeklyTimesheetSubmission,
)
from apps.attendance.services_hr import assign_weekly_off
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
from apps.hrms.views.leave_shared import _allocate_leaves_for_employee
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
from apps.performance.models import (
    CYCLE_ACTIVE,
    GOAL_ON_TRACK,
    Goal,
    PerformanceReview,
    ReviewCycle,
)

EMAIL = 'gdurgaprasad065@gmail.com'
FULL_NAME = 'Durga Prasad'
BRANCH_NAME = 'Mulugu'
# The exact Position the original EMP00013 ("G.Durga prasad") held, now
# vacant — its only Placement row was removed as part of the demo reset.
REUSED_POSITION_ID = '0c217dba-52b1-4805-b807-b5b7d484440e'
DEMO_ANNUAL_CTC = Decimal('1400000.00')  # 14 LPA — AI & ML Associate II grade


class Command(BaseCommand):
    help = f'Creates and fully seeds the demo employee {FULL_NAME} ({EMAIL}).'

    def handle(self, *args, **options):
        with transaction.atomic():
            employee = self._get_or_create_employee()
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

        self.stdout.write(self.style.SUCCESS(f'seed_durga_demo_data completed for {employee.employee_id}.'))

    # ── Create the employee (real hire path) ─────────────────────────────────

    def _get_or_create_employee(self) -> User:
        existing = User.objects.filter(email=EMAIL).first()
        if existing:
            self.stdout.write(f'Employee already exists: {existing.employee_id} — reusing.')
            return existing

        joining = timezone.localdate() - timedelta(days=90)
        employee_id = EmployeeCodeSettings.generate_employee_id(
            first_name='Durga', last_name='Prasad', date_of_joining=joining,
        )
        user = User.objects.create_user(
            email=EMAIL,
            password='Demo@12345',
            full_name=FULL_NAME,
            employee_id=employee_id,
            department='',
            designation='',
            branch='',
            phone='+91 90000 11223',
            employee_type='Permanent',
            date_of_joining=joining,
            must_change_password=False,
            onboarding_status=User.ONBOARDING_COMPLETE,
            assessment_status=User.ASSESSMENT_COMPLETE if hasattr(User, 'ASSESSMENT_COMPLETE') else 'complete',
        )
        self.stdout.write(f'User created: {user.employee_id} <{user.email}>, joined {joining}.')

        position = Position.objects.filter(id=REUSED_POSITION_ID).first()
        if position is None:
            self.stdout.write(self.style.WARNING('Original position not found — leaving unassigned.'))
        else:
            assign_position(user, position, effective_from=joining)
            user.refresh_from_db()
            self.stdout.write(f'Placed into position {position.id} ({position.org_unit.name}).')

        if not user.branch:
            branch_obj = Branch.objects.filter(branch_name=BRANCH_NAME).first() \
                or Branch.objects.filter(status=Branch.STATUS_ACTIVE).first()
            if branch_obj:
                user.branch = branch_obj.branch_name
                user.save(update_fields=['branch', 'updated_at'])
                self.stdout.write(f'Branch set to {user.branch}.')

        _allocate_leaves_for_employee(user, user.date_of_joining)
        self.stdout.write('Leave entitlements allocated via real allocation logic.')

        default_policy = WeeklyDayPolicy.objects.filter(is_default=True, is_active=True).first()
        if default_policy is not None:
            assign_weekly_off(user.employee_id, default_policy, joining, actor=None)
            self.stdout.write('Weekly-off policy assigned.')

        return user

    # ── Personal identity, statutory & bank ──────────────────────────────────

    def _seed_personal_statutory(self, employee: User) -> None:
        profile, _ = EmployeeProfile.objects.get_or_create(user=employee)
        changed = []

        def _set(field, value):
            if not getattr(profile, field):
                setattr(profile, field, value)
                changed.append(field)

        _set('date_of_birth', date(1998, 11, 2))
        _set('gender', 'male')
        _set('marital_status', 'single')
        _set('blood_group', 'O+')
        _set('nationality', 'Indian')
        _set('place_of_birth', 'Warangal')
        _set('father_name', 'Narayana Reddy')
        _set('personal_email', 'durga.prasad.personal@example.com')
        _set('current_address', 'Plot 14, Nehru Nagar, Mulugu')
        _set('current_village', 'Mulugu')
        _set('current_district', 'Mulugu')
        _set('current_state', 'Telangana')
        _set('current_pin_code', '506343')
        profile.permanent_same_as_current = True

        _set('account_holder_name', employee.full_name or FULL_NAME)
        _set('bank_name', 'State Bank of India')
        _set('bank_branch_name', 'Mulugu Branch')
        _set('account_type', 'savings')
        if not profile.account_number:
            profile.account_number = '62100987654321'
            changed.append('account_number')
        if not profile.ifsc_code:
            profile.ifsc_code = 'SBIN0005678'
            changed.append('ifsc_code')

        if not profile.pan_number:
            pan = normalize_and_validate_pan('BXZPP4321D')
            if find_conflicting_pan_profile(pan, exclude_profile_pk=profile.pk) is None:
                profile.pan_number = pan
                changed.append('pan_number')
        _set('aadhaar_number', '891234567045')
        _set('name_as_per_aadhar', employee.full_name or FULL_NAME)
        _set('uan_number', '100987654321')
        _set('esi_number', '')
        profile.pf_covered = True
        profile.esi_covered = False

        _set('core_skills', 'Python, Django, machine learning, data pipelines, REST APIs')
        _set('certifications', 'Google Cloud Professional Machine Learning Engineer')

        _set('emergency_name', 'Narayana Reddy')
        _set('emergency_relationship', 'father')
        _set('emergency_phone', '+91 90000 99887')
        _set('emergency_email', 'narayana.reddy.demo@example.com')

        profile.save()
        self.stdout.write(f'EmployeeProfile: {len(changed)} field(s) populated.')

    # ── Family & nomination ───────────────────────────────────────────────────

    def _seed_family_and_nominees(self, employee: User) -> None:
        if FamilyMember.objects.filter(employee=employee).exists():
            self.stdout.write('Family members already present — skipped.')
            return

        father = FamilyMember.objects.create(
            employee=employee, name='Narayana Reddy', relationship='father',
            date_of_birth=date(1968, 4, 15), gender='male', blood_group='O+',
            is_dependent=True, order=0,
        )
        FamilyMember.objects.create(
            employee=employee, name='Lakshmi Reddy', relationship='mother',
            date_of_birth=date(1971, 9, 3), gender='female', blood_group='B+',
            is_dependent=True, order=1,
        )
        self.stdout.write('Family members created: father, mother.')

        EPFNominee.objects.create(employee=employee, family_member=father, scheme='both', share_percentage=100, order=0)
        self.stdout.write('EPF nominee created: father 100%.')

    # ── Education & experience ────────────────────────────────────────────────

    def _seed_education_and_experience(self, employee: User) -> None:
        if EducationRecord.objects.filter(employee=employee).exists():
            self.stdout.write('Education records already present — skipped.')
        else:
            EducationRecord.objects.create(
                employee=employee, level=EDUCATION_LEVEL_BACHELORS,
                institution='Jawaharlal Nehru Technological University, Hyderabad',
                specialization='Computer Science & Engineering',
                percentage='8.2 CGPA', score_type='cgpa', score_value=Decimal('8.2'), score_scale=Decimal('10'),
                start_date=date(2016, 8, 1), end_date=date(2020, 5, 31),
                is_highest=True, is_completed=True, order=0,
            )
            self.stdout.write('Education record created: B.Tech, JNTU Hyderabad.')

        if WorkExperienceRecord.objects.filter(employee=employee).exists():
            self.stdout.write('Experience records already present — skipped.')
        else:
            WorkExperienceRecord.objects.create(
                employee=employee, employer_name='Nexora Data Systems',
                designation='Software Engineer', employment_type='full_time',
                start_date=date(2020, 7, 1), end_date=date(2026, 7, 10),
                responsibilities='Built data pipelines and internal ML tooling for analytics products.',
                reason_for_leaving='Looking for a role with more hands-on AI/ML ownership.',
                order=0,
            )
            self.stdout.write('Experience record created: Nexora Data Systems.')

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
                    late = rng.random() < 0.15
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
        self.stdout.write(f'Attendance: {created} AttendanceRecord rows + {punches_created} AttendancePunch rows created.')

        week_starts = [today - timedelta(days=today.weekday() + 7), today - timedelta(days=today.weekday() + 14)]
        ts_created = 0
        for week_start in week_starts:
            _, made = WeeklyTimesheetSubmission.objects.get_or_create(employee=employee, week_start=week_start)
            ts_created += int(made)
        self.stdout.write(f'Weekly timesheet submissions: {ts_created} created.')

    # ── Leave ─────────────────────────────────────────────────────────────────

    def _seed_leave(self, employee: User) -> None:
        year = timezone.localdate().year
        balances = [
            (LEAVE_EARNED, Decimal('10'), Decimal('2')),
            (LEAVE_CASUAL, Decimal('8'),  Decimal('1')),
            (LEAVE_SICK,   Decimal('8'),  Decimal('0')),
        ]
        for leave_type, total_days, used_days in balances:
            LeaveBalance.objects.get_or_create(
                employee=employee, leave_type=leave_type, year=year,
                defaults=dict(total_days=total_days, used_days=used_days),
            )

        today = timezone.localdate()
        LeaveRequest.objects.get_or_create(
            employee=employee, leave_type=LEAVE_CASUAL, status=REQ_PENDING,
            start_date=today + timedelta(days=4),
            defaults=dict(
                end_date=today + timedelta(days=4),
                total_days=Decimal('1'),
                reason='Personal work.',
            ),
        )
        approved_start = today - timedelta(days=12)
        LeaveRequest.objects.get_or_create(
            employee=employee, leave_type=LEAVE_EARNED, status=REQ_APPROVED,
            start_date=approved_start,
            defaults=dict(
                end_date=approved_start + timedelta(days=1),
                total_days=Decimal('2'),
                reason='Family event.',
                l1_approver=employee.reporting_manager or employee,
                l1_status='approved',
                l1_actioned_at=timezone.now() - timedelta(days=10),
            ),
        )
        self.stdout.write('Leave balances and requests seeded.')

    # ── Payslips ──────────────────────────────────────────────────────────────

    def _seed_payroll(self, employee: User) -> None:
        structure, _ = SalaryStructure.objects.get_or_create(
            name='Standard Structure',
            defaults=dict(description='Default 3-component structure (Basic/HRA/Special Allowance).',
                          is_default=True, is_active=True),
        )
        if structure.components.count() == 0:
            SalaryComponent.objects.bulk_create([
                SalaryComponent(structure=structure, name='Basic', component_type=SalaryComponent.TYPE_EARNING,
                                 calculation_type=SalaryComponent.CALC_PCT_CTC, value=Decimal('40'), order=0),
                SalaryComponent(structure=structure, name='HRA', component_type=SalaryComponent.TYPE_ALLOWANCE,
                                 calculation_type=SalaryComponent.CALC_PCT_CTC, value=Decimal('20'), order=1),
                SalaryComponent(structure=structure, name='Special Allowance',
                                 component_type=SalaryComponent.TYPE_ALLOWANCE,
                                 calculation_type=SalaryComponent.CALC_PCT_CTC, value=Decimal('40'), order=2),
            ])

        config = EmployeeSalaryConfig.objects.filter(employee=employee, is_active=True).order_by('-effective_from').first()
        if config is None:
            config = EmployeeSalaryConfig.objects.create(
                employee=employee, annual_ctc=DEMO_ANNUAL_CTC, salary_structure=structure,
                effective_from=employee.date_of_joining, reason='', is_active=True,
            )
        self.stdout.write(f'EmployeeSalaryConfig: annual_ctc=₹{config.annual_ctc}.')

        components = list(structure.components.filter(is_active=True).order_by('order'))
        branch_obj = Branch.objects.filter(branch_name=employee.branch).select_related('state').first()
        branch_config = BranchPayrollConfig.objects.filter(branch=branch_obj).first() if branch_obj else None
        statutory = StatutoryConfig.objects.filter(state=branch_obj.state).first() if branch_obj and branch_obj.state else None

        tax_declaration = EmployeeTaxDeclaration.objects.filter(employee=employee).order_by('-financial_year_start').first()
        tax_regime = tax_declaration.tax_regime if tax_declaration else EmployeeTaxDeclaration.REGIME_NEW
        declared_investments = tax_declaration.declared_investments if tax_declaration else None

        today = timezone.localdate()
        cycle_specs = [
            (today - timedelta(days=61), today - timedelta(days=31), today - timedelta(days=25), 'paid'),
            (today - timedelta(days=30), today, today + timedelta(days=5), 'sent'),
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

            payslip_count += 1
            if final_state == 'paid' and payslip.status != EmployeePayslip.STATUS_PAID:
                payslip.status = EmployeePayslip.STATUS_PAID
                payslip.sent_at = payslip.sent_at or timezone.now() - timedelta(days=28)
                payslip.paid_at = timezone.now() - timedelta(days=25)
                payslip.save(update_fields=['status', 'sent_at', 'paid_at', 'updated_at'])
                cycle.status = PayrollCycle.STATUS_PAID
                cycle.paid_at = payslip.paid_at
                cycle.marked_paid_by = employee
                cycle.save(update_fields=['status', 'paid_at', 'marked_paid_by', 'updated_at'])
            elif final_state == 'sent' and payslip.status not in (EmployeePayslip.STATUS_SENT, EmployeePayslip.STATUS_ACKNOWLEDGED):
                payslip.status = EmployeePayslip.STATUS_SENT
                payslip.sent_at = timezone.now() - timedelta(days=2)
                payslip.query_deadline = payslip.sent_at + timedelta(hours=24)
                payslip.save(update_fields=['status', 'sent_at', 'query_deadline', 'updated_at'])
                cycle.status = PayrollCycle.STATUS_QUERY_WINDOW_OPEN
                cycle.query_window_closes_at = payslip.query_deadline
                cycle.save(update_fields=['status', 'query_window_closes_at', 'updated_at'])
        self.stdout.write(f'Payslips: {payslip_count} EmployeePayslip rows present.')

    # ── Tax ───────────────────────────────────────────────────────────────────

    def _seed_tax(self, employee: User) -> None:
        today = timezone.localdate()
        fy_start = today.year if today.month >= 4 else today.year - 1
        EmployeeTaxDeclaration.objects.get_or_create(
            employee=employee, financial_year_start=fy_start,
            defaults=dict(
                tax_regime=EmployeeTaxDeclaration.REGIME_NEW,
                declared_investments={'80C': 40000},
                status=EmployeeTaxDeclaration.STATUS_DRAFT,
            ),
        )
        self.stdout.write(f'EmployeeTaxDeclaration FY{fy_start} seeded.')

    # ── Expenses ──────────────────────────────────────────────────────────────

    def _seed_expenses(self, employee: User) -> None:
        today = timezone.localdate()
        branch = Branch.objects.filter(branch_name=employee.branch).first()

        def _next_expense_number() -> int:
            last = (Expense.objects.exclude(expense_number__isnull=True)
                    .order_by('-expense_number').values_list('expense_number', flat=True).first())
            return (last or 0) + 1

        Expense.objects.get_or_create(
            employee=employee, title='Client site visit — local travel', status='approved',
            defaults=dict(
                expense_number=_next_expense_number(), branch=branch, category='travel',
                amount=Decimal('850.00'), expense_date=today - timedelta(days=9),
                description='Cab fare for a client site visit.',
            ),
        )
        self.stdout.write('Expense record seeded.')

    # ── Documents ─────────────────────────────────────────────────────────────

    def _seed_documents(self, employee: User) -> None:
        rows = [
            (EMP_DOC_IDENTITY,   'Aadhaar_card_scan.pdf',        EMP_DOC_VERIFIED, timezone.now() - timedelta(days=80)),
            (EMP_DOC_TAX_PROOF,  'Form16_FY2025-26.pdf',         EMP_DOC_PENDING,  None),
            (EMP_DOC_EDUCATION,  'BTech_degree_certificate.pdf', EMP_DOC_VERIFIED, timezone.now() - timedelta(days=75)),
        ]
        for category, file_name, status, reviewed_at in rows:
            EmployeeDocumentSubmission.objects.get_or_create(
                employee=employee, category=category, file_name=file_name,
                defaults=dict(status=status, reviewed_at=reviewed_at, reviewed_by=employee if reviewed_at else None),
            )
        self.stdout.write('Document submissions seeded.')

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

        Goal.objects.get_or_create(
            employee=employee, cycle=cycle, title='Automate the weekly reporting pipeline',
            defaults=dict(
                description='Reduce manual effort in generating weekly ops reports.',
                target_metric='Report generation time reduced by 70%.',
                status=GOAL_ON_TRACK, weight_percent=50,
                due_date=cycle.period_end, created_by=employee,
            ),
        )
        PerformanceReview.objects.get_or_create(
            employee=employee, cycle=cycle,
            defaults=dict(
                metric_reference='Pipeline automation progress, code review turnaround.',
                what_changed='Started automating the weekly reporting workflow.',
                key_strengths='Fast learner, reliable delivery on assigned tasks.',
                self_rating='4',
            ),
        )
        self.stdout.write('Goal and performance review seeded.')

    # ── Assets / HR Help ──────────────────────────────────────────────────────

    def _seed_assets_and_help(self, employee: User) -> None:
        CompanyAsset.objects.get_or_create(
            employee=employee, asset_type='laptop',
            defaults=dict(tag_number='LAP-4120', condition='good', issued_at=employee.date_of_joining),
        )

        def _next_request_number() -> int:
            last = (HRHelpRequest.objects.exclude(request_number__isnull=True)
                    .order_by('-request_number').values_list('request_number', flat=True).first())
            return (last or 0) + 1

        HRHelpRequest.objects.get_or_create(
            submitted_by=employee, topic='it_support',
            defaults=dict(
                request_number=_next_request_number(),
                priority='normal',
                message='Laptop battery drains quickly — requesting a check-up.',
                status='open',
            ),
        )
        self.stdout.write('Company asset and HR help request seeded.')
