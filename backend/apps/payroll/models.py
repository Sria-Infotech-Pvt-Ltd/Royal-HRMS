import uuid
from django.db import models
from django.conf import settings

from core.encrypted_fields import EncryptedCharField


class PayrollSettings(models.Model):
    """Company-wide payroll configuration. Only one active record should exist."""

    APPROVAL_L1 = 'L1'
    APPROVAL_L1_L2 = 'L1_L2'
    APPROVAL_CHOICES = [
        (APPROVAL_L1, 'Manager only (L1)'),
        (APPROVAL_L1_L2, 'Manager + HR (L1 + L2)'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    cycle_start_day = models.PositiveSmallIntegerField(
        default=25,
        help_text='Day of month the pay cycle starts (e.g. 25)',
    )
    cycle_end_day = models.PositiveSmallIntegerField(
        default=24,
        help_text='Day of month the pay cycle ends (e.g. 24 of the following month)',
    )
    pay_day = models.PositiveSmallIntegerField(
        default=30,
        help_text='Day of month salary is credited',
    )
    approval_levels = models.CharField(
        max_length=10,
        choices=APPROVAL_CHOICES,
        default=APPROVAL_L1_L2,
    )
    employee_query_window_hours = models.PositiveSmallIntegerField(
        default=24,
        help_text='Hours employees have to raise queries after payslip is sent',
    )
    enable_reimbursements = models.BooleanField(default=True)
    enable_bonuses = models.BooleanField(default=True)

    # EPF / EDLI statutory rates — configurable so law changes don't require code changes
    eps_rate = models.DecimalField(
        max_digits=5, decimal_places=2, default=8.33,
        help_text='Employer EPS contribution % (EPFO-mandated; update when law changes)',
    )
    edli_rate = models.DecimalField(
        max_digits=5, decimal_places=2, default=0.50,
        help_text='EDLI contribution % on wages up to edli_wage_ceiling',
    )
    edli_wage_ceiling = models.DecimalField(
        max_digits=10, decimal_places=2, default=15000.00,
        help_text='Monthly wage ceiling for EDLI computation',
    )
    epf_admin_rate = models.DecimalField(
        max_digits=5, decimal_places=2, default=0.50,
        help_text='EPF administrative / inspection charges %',
    )
    # Gratuity provisioning is not otherwise computed anywhere in payroll
    # today (the only existing gratuity figure, SeparationSettlement.gratuity_amount,
    # is a manual one-off entered at separation, not an accrual rate) — this
    # backs the Hire wizard's CTC-preview "Gratuity Provision" row via the new
    # estimate_salary_breakdown() service, following the same configurable-
    # rate convention as eps_rate/edli_rate above rather than hardcoding the
    # standard 4.81%-of-Basic+DA formula inline.
    gratuity_rate = models.DecimalField(
        max_digits=5, decimal_places=2, default=4.81,
        help_text='Employer gratuity provision % of Basic+DA (standard formula: 15/26/12)',
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'payroll_settings'

    def __str__(self):
        return f'PayrollSettings (cycle {self.cycle_start_day}–{self.cycle_end_day}, pay {self.pay_day})'


class StatutoryConfig(models.Model):
    """Statutory deduction rules per state: PT, ESI, LWF."""

    LWF_MONTHLY = 'monthly'
    LWF_HALFYEARLY = 'halfyearly'
    LWF_ANNUAL = 'annual'
    LWF_FREQUENCY_CHOICES = [
        (LWF_MONTHLY, 'Monthly'),
        (LWF_HALFYEARLY, 'Half-yearly'),
        (LWF_ANNUAL, 'Annual'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    state = models.OneToOneField(
        'branch.State',
        on_delete=models.PROTECT,
        related_name='statutory_config',
    )

    # Professional Tax
    pt_applicable = models.BooleanField(default=False)
    # JSON: [{"min": 0, "max": 10000, "amount": 0}, {"min": 10001, "max": 15000, "amount": 110}, ...]
    pt_slabs = models.JSONField(default=list, blank=True)

    # ESI (Employee State Insurance)
    esi_applicable = models.BooleanField(default=True)
    esi_wage_ceiling = models.DecimalField(
        max_digits=10, decimal_places=2, default=21000.00,
        help_text='Monthly gross above this exempts employee from ESI',
    )
    esi_employee_rate = models.DecimalField(
        max_digits=5, decimal_places=2, default=0.75,
        help_text='Employee contribution %',
    )
    esi_employer_rate = models.DecimalField(
        max_digits=5, decimal_places=2, default=3.25,
        help_text='Employer contribution %',
    )

    # Labour Welfare Fund
    lwf_applicable = models.BooleanField(default=False)
    lwf_employee_amount = models.DecimalField(max_digits=8, decimal_places=2, default=0)
    lwf_employer_amount = models.DecimalField(max_digits=8, decimal_places=2, default=0)
    lwf_frequency = models.CharField(
        max_length=20,
        choices=LWF_FREQUENCY_CHOICES,
        default=LWF_MONTHLY,
    )
    lwf_due_months = models.JSONField(
        default=list, blank=True,
        help_text=(
            'Calendar months (1-12) in which the configured LWF amount is actually '
            'deducted. Ignored when lwf_frequency=monthly (charged every cycle). '
            'Required: exactly 1 month for annual, exactly 2 distinct months for '
            'halfyearly. Interpreted against the payroll cycle\'s start-month (same '
            'convention PayrollAdjustment.month already uses). Left empty for '
            'annual/halfyearly means LWF is not charged until configured.'
        ),
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'payroll_statutory_config'

    def __str__(self):
        return f'StatutoryConfig – {self.state.name}'

    def compute_pt(self, monthly_gross):
        """Return PT amount for a given monthly gross salary using the slab table."""
        if not self.pt_applicable:
            return 0
        gross = float(monthly_gross)
        for slab in self.pt_slabs:
            min_val = slab.get('min', 0)
            max_val = slab.get('max')
            amount = slab.get('amount', 0)
            if max_val is None:
                if gross >= min_val:
                    return amount
            elif min_val <= gross <= max_val:
                return amount
        return 0


class SalaryStructure(models.Model):
    """Template that defines how salary is broken down into components."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True)
    is_default = models.BooleanField(
        default=False,
        help_text='Exactly one structure should be marked as default',
    )
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'payroll_salary_structures'

    def __str__(self):
        return self.name


class SalaryComponent(models.Model):
    """Individual earning / deduction component within a salary structure."""

    TYPE_EARNING = 'earning'
    TYPE_DEDUCTION = 'deduction'
    TYPE_ALLOWANCE = 'allowance'
    COMPONENT_TYPE_CHOICES = [
        (TYPE_EARNING, 'Earning'),
        (TYPE_DEDUCTION, 'Deduction'),
        (TYPE_ALLOWANCE, 'Allowance'),
    ]

    CALC_PCT_CTC = 'percentage_of_ctc'
    CALC_PCT_BASIC = 'percentage_of_basic'
    CALC_FIXED = 'fixed'
    # Opt-in HRA rule that ignores `value` and instead computes 50% of Basic
    # for employees in a metro branch (Branch.is_metro), 40% otherwise — the
    # standard Income Tax HRA exemption split. A structure that already has
    # its own fixed HRA % (CALC_PCT_BASIC) keeps working unchanged; this is
    # only used when the structure's HRA component is deliberately switched
    # to this calculation type.
    CALC_METRO_HRA = 'metro_hra_of_basic'
    CALCULATION_TYPE_CHOICES = [
        (CALC_PCT_CTC, '% of CTC'),
        (CALC_PCT_BASIC, '% of Basic'),
        (CALC_FIXED, 'Fixed Amount'),
        (CALC_METRO_HRA, 'Metro HRA (50%/40% of Basic)'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    structure = models.ForeignKey(
        SalaryStructure,
        on_delete=models.CASCADE,
        related_name='components',
    )
    name = models.CharField(max_length=100)
    component_type = models.CharField(max_length=20, choices=COMPONENT_TYPE_CHOICES)
    calculation_type = models.CharField(max_length=30, choices=CALCULATION_TYPE_CHOICES)
    value = models.DecimalField(
        max_digits=10, decimal_places=4,
        help_text='Percentage (e.g. 40.00 for 40%) or fixed rupee amount',
    )
    is_taxable = models.BooleanField(default=True)
    is_active = models.BooleanField(default=True)
    order = models.PositiveSmallIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'payroll_salary_components'
        ordering = ['order', 'name']
        unique_together = [('structure', 'name')]

    def __str__(self):
        return f'{self.structure.name} › {self.name}'


class BranchPayrollConfig(models.Model):
    """Per-branch overrides: salary structure, PF applicability."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    branch = models.OneToOneField(
        'branch.Branch',
        on_delete=models.PROTECT,
        related_name='payroll_config',
    )
    salary_structure = models.ForeignKey(
        SalaryStructure,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        help_text='Leave blank to use the company default structure',
    )

    # PF (Provident Fund — central, but branch may be exempt)
    PF_WAGE_BASIC_ONLY = 'basic_only'
    PF_WAGE_BASIC_PLUS_ALLOWANCES = 'basic_plus_allowances'
    PF_WAGE_BASIS_CHOICES = [
        (PF_WAGE_BASIC_ONLY, 'Basic salary only (legacy default)'),
        (PF_WAGE_BASIC_PLUS_ALLOWANCES, 'Basic + all allowances except HRA (2019 EPFO ruling)'),
    ]

    pf_applicable = models.BooleanField(default=True)
    pf_employee_rate = models.DecimalField(max_digits=5, decimal_places=2, default=12.00)
    pf_employer_rate = models.DecimalField(max_digits=5, decimal_places=2, default=12.00)
    pf_wage_ceiling = models.DecimalField(
        max_digits=10, decimal_places=2, default=15000.00,
        help_text='PF is calculated on min(pf_wage_basis amount, this ceiling)',
    )
    pf_wage_basis = models.CharField(
        max_length=25, choices=PF_WAGE_BASIS_CHOICES, default=PF_WAGE_BASIC_ONLY,
        help_text=(
            "'basic_only' matches this branch's existing behavior (PF wages = "
            "basic salary alone). The Supreme Court's 2019 ruling on EPF "
            "wages (and Razorpay's documented PF calculation) treats all "
            "allowances except HRA as PF wages — select "
            "'basic_plus_allowances' to opt into that stricter, more "
            "compliant basis. Defaults to the legacy behavior so existing "
            "branches are not silently recalculated; change this explicitly "
            "per branch after confirming with your compliance team."
        ),
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'payroll_branch_config'

    def __str__(self):
        return f'BranchPayrollConfig – {self.branch.branch_name}'


class EmployeeSalaryConfig(models.Model):
    """Per-employee CTC and optional structure override. Multiple records = history.

    `reason`/`linked_promotion` exist because a CTC revision and a
    promotion (accounts.PromotionRecord) are otherwise two completely
    separate, unlinked records with no way to later tell "was this raise
    because of that promotion" apart from eyeballing whether their dates
    happen to match — which is also just wrong plenty of the time (annual
    increments, market corrections, and promotions-with-no-raise all
    exist). `linked_promotion` is optional and SET_NULL on delete — a
    salary history row must never disappear just because the promotion
    record it references does."""

    REASON_PROMOTION          = 'promotion'
    REASON_INCREMENT          = 'increment'
    REASON_MARKET_CORRECTION  = 'market_correction'
    REASON_OTHER              = 'other'
    REASON_CHOICES = [
        (REASON_PROMOTION,         'Promotion'),
        (REASON_INCREMENT,         'Annual Increment'),
        (REASON_MARKET_CORRECTION, 'Market Correction'),
        (REASON_OTHER,             'Other'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    employee = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='salary_configs',
    )
    annual_ctc = models.DecimalField(
        max_digits=12, decimal_places=2,
        help_text='Annual CTC in rupees',
    )
    salary_structure = models.ForeignKey(
        SalaryStructure,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        help_text='Leave blank to use branch/company default',
    )
    effective_from = models.DateField()
    reason = models.CharField(max_length=20, choices=REASON_CHOICES, blank=True)
    # Free text for REASON_OTHER (e.g. "Retention counter-offer") — the 4
    # REASON_CHOICES cover the common cases, but "Other" alone with nothing
    # else recorded would be no more useful than leaving reason blank.
    reason_note = models.CharField(max_length=200, blank=True)
    linked_promotion = models.ForeignKey(
        'accounts.PromotionRecord',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='salary_revisions',
        help_text='The specific promotion (if any) this CTC revision was for',
    )
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'payroll_employee_salary_config'
        ordering = ['-effective_from']

    def __str__(self):
        return f'{self.employee.full_name} – ₹{self.annual_ctc}/yr from {self.effective_from}'

    @property
    def monthly_ctc(self):
        return self.annual_ctc / 12


class PayrollCycle(models.Model):
    """One record per payroll run."""

    STATUS_DRAFT = 'draft'
    STATUS_ATTENDANCE_PENDING = 'attendance_pending'
    STATUS_ATTENDANCE_APPROVED = 'attendance_approved'
    STATUS_PROCESSING = 'processing'
    STATUS_PAYSLIPS_GENERATED = 'payslips_generated'
    STATUS_QUERY_WINDOW_OPEN = 'query_window_open'
    STATUS_PAID = 'paid'
    STATUS_CLOSED = 'closed'
    STATUS_CANCELLED = 'cancelled'
    STATUS_CHOICES = [
        (STATUS_DRAFT, 'Draft'),
        (STATUS_ATTENDANCE_PENDING, 'Awaiting Attendance Approval'),
        (STATUS_ATTENDANCE_APPROVED, 'Attendance Approved'),
        (STATUS_PROCESSING, 'Processing'),
        (STATUS_PAYSLIPS_GENERATED, 'Payslips Generated'),
        (STATUS_QUERY_WINDOW_OPEN, 'Employee Query Window Open'),
        (STATUS_PAID, 'Paid'),
        (STATUS_CLOSED, 'Closed'),
        (STATUS_CANCELLED, 'Cancelled'),
    ]

    CANCELLABLE_STATUSES = [
        STATUS_DRAFT,
        STATUS_ATTENDANCE_PENDING,
        STATUS_ATTENDANCE_APPROVED,
        STATUS_PROCESSING,
        STATUS_PAYSLIPS_GENERATED,
        STATUS_QUERY_WINDOW_OPEN,
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    cycle_start = models.DateField()
    cycle_end = models.DateField()
    pay_date = models.DateField()
    status = models.CharField(max_length=30, choices=STATUS_CHOICES, default=STATUS_DRAFT)

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='payroll_cycles_created',
    )
    attendance_approved_by_l1 = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='payroll_cycles_l1_approved',
    )
    attendance_approved_by_l2 = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='payroll_cycles_l2_approved',
    )
    attendance_l1_approved_at = models.DateTimeField(null=True, blank=True)
    attendance_l2_approved_at = models.DateTimeField(null=True, blank=True)
    # Set alongside L2 when the HR approver also self-attests their own
    # attendance for the cycle — distinct from attendance_l2_approved_at so
    # reports can tell a self-attestation apart from a third-party review.
    hr_self_approved_at = models.DateTimeField(null=True, blank=True)

    query_window_closes_at = models.DateTimeField(null=True, blank=True)
    paid_at = models.DateTimeField(null=True, blank=True)
    marked_paid_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='payroll_cycles_marked_paid',
    )

    branch = models.ForeignKey(
        'branch.Branch',
        on_delete=models.PROTECT,
        null=True, blank=True,
        related_name='payroll_cycles',
        help_text='Branch this cycle is scoped to. Null = company-wide (legacy).',
    )

    notes = models.TextField(blank=True)

    cancelled_at = models.DateTimeField(null=True, blank=True)
    cancelled_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='payroll_cycles_cancelled',
    )
    cancellation_reason = models.TextField(blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'payroll_cycles'
        ordering = ['-cycle_start']
        indexes = [
            # Phase 4: `status` has no index at all today, despite being
            # filtered standalone (attendance-approval queue) in addition to
            # the PK-scoped atomic claim/revert updates in ProcessPayrollView.
            models.Index(fields=['status'], name='cycle_status_idx'),
            # Phase 4: the overlapping-cycle guard (on create) and the
            # cycle-covering-a-date lookups both filter by this exact range
            # pair, with no supporting index today.
            models.Index(fields=['cycle_start', 'cycle_end'], name='cycle_start_end_idx'),
        ]

    def __str__(self):
        return f'PayrollCycle {self.cycle_start} → {self.cycle_end} [{self.status}]'


class EmployeePayslip(models.Model):
    """Computed payslip for one employee in one cycle."""

    STATUS_DRAFT = 'draft'
    STATUS_SENT = 'sent'
    STATUS_ACKNOWLEDGED = 'acknowledged'
    STATUS_QUERIED = 'queried'
    STATUS_RESOLVED = 'resolved'
    STATUS_PAID = 'paid'
    STATUS_CHOICES = [
        (STATUS_DRAFT, 'Draft'),
        (STATUS_SENT, 'Sent to Employee'),
        (STATUS_ACKNOWLEDGED, 'Acknowledged'),
        (STATUS_QUERIED, 'Query Raised'),
        (STATUS_RESOLVED, 'Query Resolved'),
        (STATUS_PAID, 'Paid'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    cycle = models.ForeignKey(
        PayrollCycle,
        on_delete=models.CASCADE,
        related_name='payslips',
    )
    employee = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='payslips',
    )
    # Structure actually used for this computation (employee override, branch,
    # or global default — whichever cycles.py resolved at the time).
    salary_structure = models.ForeignKey(
        SalaryStructure,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='payslips',
    )

    # CTC snapshot at time of calculation
    annual_ctc = models.DecimalField(max_digits=12, decimal_places=2)
    monthly_ctc = models.DecimalField(max_digits=10, decimal_places=2)

    # Earnings breakdown
    basic = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    hra = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    special_allowance = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    other_earnings = models.JSONField(
        default=dict, blank=True,
        help_text='Additional components keyed by component name and amount',
    )

    # Reimbursements + bonuses (optional — governed by PayrollSettings toggles)
    reimbursements = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    bonus = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    # Typed breakdown for bonuses: [{"type": "Annual", "amount": "5000.00", "note": ""}]
    bonus_breakdown = models.JSONField(default=list, blank=True)

    gross_earnings = models.DecimalField(max_digits=10, decimal_places=2, default=0)

    # LOP deduction
    total_working_days = models.PositiveSmallIntegerField(default=0)
    lop_days = models.DecimalField(max_digits=5, decimal_places=1, default=0)
    lop_deduction = models.DecimalField(max_digits=10, decimal_places=2, default=0)

    # Statutory deductions
    # The wage base PF was actually calculated on for this payslip (after
    # BranchPayrollConfig.pf_wage_basis and the PF ceiling were applied) —
    # stored so ECR generation can reproduce the exact figures used here
    # without re-deriving them from config that may have since changed.
    # Null on payslips computed before this field existed; ECR generation
    # falls back to a best-effort recompute (and validates it) for those.
    pf_wage_base = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    pf_employee = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    pf_employer = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    esi_employee = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    esi_employer = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    pt_deduction = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    lwf_employee = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    lwf_employer = models.DecimalField(max_digits=10, decimal_places=2, default=0)

    # One-time adjustments (additions/deductions/arrears) applied before net pay
    adjustments_earning   = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    adjustments_deduction = models.DecimalField(max_digits=10, decimal_places=2, default=0)

    total_deductions = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    net_pay = models.DecimalField(max_digits=10, decimal_places=2, default=0)

    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_DRAFT)
    payslip_pdf = models.FileField(upload_to='payslips/', null=True, blank=True)
    sent_at = models.DateTimeField(null=True, blank=True)
    query_deadline = models.DateTimeField(null=True, blank=True)
    paid_at = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'payroll_employee_payslips'
        unique_together = [('cycle', 'employee')]
        ordering = ['-cycle__cycle_start', 'employee__full_name']

    def __str__(self):
        return f'{self.employee.full_name} – {self.cycle.cycle_start}'


class PayslipQuery(models.Model):
    """Query raised by an employee against their payslip during the query window."""

    STATUS_OPEN = 'open'
    STATUS_RESOLVED = 'resolved'
    STATUS_CHOICES = [
        (STATUS_OPEN, 'Open'),
        (STATUS_RESOLVED, 'Resolved'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    payslip = models.ForeignKey(
        EmployeePayslip,
        on_delete=models.CASCADE,
        related_name='queries',
    )
    raised_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='payslip_queries_raised',
    )
    description = models.TextField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_OPEN)
    resolved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='payslip_queries_resolved',
    )
    resolution_note = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'payroll_payslip_queries'
        ordering = ['-created_at']

    def __str__(self):
        return f'Query on {self.payslip} by {self.raised_by.full_name} [{self.status}]'


class ManagerAttendanceApproval(models.Model):
    """Per-manager L1 attendance sign-off for a payroll cycle.

    One row per active manager (role.can_manage_team=True) is created when
    the cycle is created. L1 is considered complete only when every row has
    approved_at set. HR/sysadmin can approve directly if no manager rows exist.
    """

    id         = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    cycle      = models.ForeignKey(
        PayrollCycle,
        on_delete=models.CASCADE,
        related_name='manager_approvals',
    )
    manager    = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='payroll_attendance_approvals',
    )
    approved_at = models.DateTimeField(null=True, blank=True)
    # Set alongside approved_at when the manager also self-attests their own
    # attendance for the cycle — distinct from approved_at (which covers their
    # team) so reports can tell a self-attestation apart from a peer review.
    self_approved_at = models.DateTimeField(null=True, blank=True)
    note        = models.TextField(blank=True)
    created_at  = models.DateTimeField(auto_now_add=True)
    updated_at  = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'payroll_manager_attendance_approvals'
        unique_together = [('cycle', 'manager')]
        ordering = ['manager__full_name']

    def __str__(self):
        status = 'approved' if self.approved_at else 'pending'
        return f'{self.manager.full_name} – {self.cycle} [{status}]'


class PayrollAdjustment(models.Model):
    """One-time addition, deduction, or arrear for a specific employee in a payroll month.
    Created by HR before the cycle is processed; picked up automatically during ProcessPayrollView.
    """

    ADDITION  = 'addition'
    DEDUCTION = 'deduction'
    ARREAR    = 'arrear'
    TYPE_CHOICES = [
        (ADDITION,  'Addition'),
        (DEDUCTION, 'Deduction'),
        (ARREAR,    'Arrear'),
    ]

    id       = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    employee = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='payroll_adjustments',
    )
    # First day of the target payroll month (e.g. 2026-07-01 for July 2026)
    month      = models.DateField()
    type       = models.CharField(max_length=20, choices=TYPE_CHOICES)
    label      = models.CharField(max_length=200)
    amount     = models.DecimalField(max_digits=10, decimal_places=2)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='created_payroll_adjustments',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'payroll_adjustments'
        ordering = ['month', 'employee__full_name', 'type']

    def __str__(self):
        return f'{self.get_type_display()} – {self.employee.full_name} – {self.month} – ₹{self.amount}'


class SalaryTransferBatch(models.Model):
    """
    Dual-confirmation gate for releasing a payroll cycle's salaries for bank
    transfer. "Employee confirmed" means every payslip in the cycle is
    EmployeePayslip.STATUS_ACKNOWLEDGED or STATUS_RESOLVED (see
    ready_for_confirmation() in views/salary_transfer.py) — no outstanding
    STATUS_SENT (never acknowledged) or STATUS_QUERIED (disputed, unresolved)
    payslip anywhere in the cycle. "Employer confirmed" is this row's own
    confirmed_at/confirmed_by, set explicitly by HR, only once the employee
    side is already satisfied.

    Confirming snapshots every employee's CURRENT bank details into
    SalaryTransferItem at that exact moment (see that model's docstring) —
    the whole point being that a bank-detail change after this moment can
    never silently redirect a transfer both sides already signed off on.
    """
    STATUS_PENDING   = 'pending'
    STATUS_CONFIRMED = 'confirmed'
    STATUS_CANCELLED = 'cancelled'
    STATUS_CHOICES = [
        (STATUS_PENDING,   'Pending Confirmation'),
        (STATUS_CONFIRMED, 'Confirmed — Locked for Transfer'),
        (STATUS_CANCELLED, 'Cancelled'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    cycle = models.OneToOneField(
        PayrollCycle,
        on_delete=models.PROTECT,
        related_name='salary_transfer_batch',
    )
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_PENDING)

    confirmed_at = models.DateTimeField(null=True, blank=True)
    confirmed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        null=True, blank=True,
        related_name='salary_transfer_batches_confirmed',
    )

    file_generated_at = models.DateTimeField(null=True, blank=True)
    file_generated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='salary_transfer_batches_downloaded',
    )

    cancelled_at = models.DateTimeField(null=True, blank=True)
    cancelled_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='salary_transfer_batches_cancelled',
    )
    cancellation_reason = models.TextField(blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'payroll_salary_transfer_batches'
        ordering = ['-created_at']

    def __str__(self):
        return f'SalaryTransferBatch for {self.cycle} [{self.status}]'


class SalaryTransferItem(models.Model):
    """
    One employee's locked transfer instruction within a SalaryTransferBatch —
    bank details and amount snapshotted from EmployeeProfile/EmployeePayslip
    at the exact moment of employer confirmation, and never updated again.

    The bank-upload file is generated exclusively from these rows, never
    from live EmployeeProfile data — this is the actual security control:
    once both sides have confirmed, nothing (an account takeover, a
    mis-click, a legitimate-looking support request) can change where this
    specific transfer sends money without it showing up as a mismatch
    against this immutable record.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    batch = models.ForeignKey(
        SalaryTransferBatch,
        on_delete=models.CASCADE,
        related_name='items',
    )
    payslip = models.ForeignKey(
        EmployeePayslip,
        on_delete=models.PROTECT,
        related_name='transfer_items',
    )
    employee = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='salary_transfer_items',
    )

    # Locked snapshot — copied once from EmployeeProfile at confirmation time.
    account_holder_name = models.CharField(max_length=150)
    account_number       = EncryptedCharField(max_length=255)
    ifsc_code            = EncryptedCharField(max_length=255)
    bank_name            = models.CharField(max_length=200, blank=True)
    amount               = models.DecimalField(max_digits=10, decimal_places=2)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'payroll_salary_transfer_items'
        unique_together = [('batch', 'payslip')]
        ordering = ['employee__full_name']

    def __str__(self):
        return f'{self.employee.full_name} — ₹{self.amount}'


# ─── Employee Tax Declaration ───────────────────────────────────────────────────

class EmployeeTaxDeclaration(models.Model):
    """An employee's once-per-financial-year tax regime choice plus declared
    investment amounts (Section 80C/80D/etc, stored as a flexible
    section->amount JSON blob rather than one column per section — the same
    convention LeavePolicy's own applicable_* JSON fields already use in this
    codebase, and section lists change more often than a migration should be
    needed for).

    Deliberately does NOT compute actual income tax (old vs new regime
    slabs, HRA exemption interplay, 80C/80D limits) — that's a payroll-engine
    feature on its own, out of scope here; this only records what the
    employee declared and whether HR has reviewed it. Approval doesn't feed
    into any real payslip computation (no such computation exists yet) — it
    is a review/acknowledgement step, mirroring the effective-dated
    "submit -> HR reviews" shape already used by Promotion/Salary/
    Confirmation, without inventing a new workflow pattern."""

    REGIME_OLD = 'old'
    REGIME_NEW = 'new'
    REGIME_CHOICES = [
        (REGIME_OLD, 'Old Regime'),
        (REGIME_NEW, 'New Regime (115BAC)'),
    ]

    STATUS_DRAFT     = 'draft'
    STATUS_SUBMITTED = 'submitted'
    STATUS_APPROVED  = 'approved'
    STATUS_CHOICES = [
        (STATUS_DRAFT,     'Draft'),
        (STATUS_SUBMITTED, 'Submitted'),
        (STATUS_APPROVED,  'Approved'),
    ]

    id                  = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    employee            = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='tax_declarations',
    )
    # The calendar year the financial year starts in (e.g. 2026 for FY 2026-27)
    # — same integer-year convention LeaveBalance already uses for its own
    # per-year rows, rather than a free-text "2026-27" string.
    financial_year_start = models.PositiveIntegerField()
    tax_regime          = models.CharField(max_length=10, choices=REGIME_CHOICES, default=REGIME_NEW)
    declared_investments = models.JSONField(default=dict, blank=True)
    status              = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_DRAFT)
    submitted_at        = models.DateTimeField(null=True, blank=True)
    approved_at         = models.DateTimeField(null=True, blank=True)
    approved_by         = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='tax_declarations_approved',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table        = 'payroll_employee_tax_declarations'
        unique_together = [('employee', 'financial_year_start')]
        ordering        = ['-financial_year_start']

    def __str__(self) -> str:
        return f'{self.employee.full_name} — FY {self.financial_year_start}-{str(self.financial_year_start + 1)[2:]} ({self.tax_regime})'

