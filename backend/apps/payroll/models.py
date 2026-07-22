import uuid
from django.db import models
from django.conf import settings


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
    CALCULATION_TYPE_CHOICES = [
        (CALC_PCT_CTC, '% of CTC'),
        (CALC_PCT_BASIC, '% of Basic'),
        (CALC_FIXED, 'Fixed Amount'),
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
    pf_applicable = models.BooleanField(default=True)
    pf_employee_rate = models.DecimalField(max_digits=5, decimal_places=2, default=12.00)
    pf_employer_rate = models.DecimalField(max_digits=5, decimal_places=2, default=12.00)
    pf_wage_ceiling = models.DecimalField(
        max_digits=10, decimal_places=2, default=15000.00,
        help_text='PF is calculated on min(basic, this ceiling)',
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'payroll_branch_config'

    def __str__(self):
        return f'BranchPayrollConfig – {self.branch.branch_name}'


class EmployeeSalaryConfig(models.Model):
    """Per-employee CTC and optional structure override. Multiple records = history."""

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
    STATUS_CHOICES = [
        (STATUS_DRAFT, 'Draft'),
        (STATUS_ATTENDANCE_PENDING, 'Awaiting Attendance Approval'),
        (STATUS_ATTENDANCE_APPROVED, 'Attendance Approved'),
        (STATUS_PROCESSING, 'Processing'),
        (STATUS_PAYSLIPS_GENERATED, 'Payslips Generated'),
        (STATUS_QUERY_WINDOW_OPEN, 'Employee Query Window Open'),
        (STATUS_PAID, 'Paid'),
        (STATUS_CLOSED, 'Closed'),
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

    query_window_closes_at = models.DateTimeField(null=True, blank=True)
    paid_at = models.DateTimeField(null=True, blank=True)
    marked_paid_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='payroll_cycles_marked_paid',
    )

    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'payroll_cycles'
        ordering = ['-cycle_start']

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
    pf_employee = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    pf_employer = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    esi_employee = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    esi_employer = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    pt_deduction = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    lwf_employee = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    lwf_employer = models.DecimalField(max_digits=10, decimal_places=2, default=0)

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
