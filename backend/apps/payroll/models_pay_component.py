"""
Phase 7A Task B — the pay component master.

This is pure master data: a company-wide, code-identified catalogue of
earning/deduction/contribution definitions, meant to eventually replace
per-structure `SalaryComponent` rows (free-text name, structure-scoped) and
every fixed `EmployeePayslip` column (basic/hra/pf_employee/esi_employer/...)
as the single source of what a line on a payslip IS.

Nothing reads this model yet. `apps.payroll.engine.legacy` (Phase 7A Task A)
is completely unaware of it and keeps computing payslips exactly as before.
Task C (pay structures + formula graph) and Task E (payslip lines) are what
will actually wire this into a real calculation — this task only builds the
catalogue and proves (via `seed_pay_components` + the mapping in that
command's own docstring) that it can describe every component this company
already uses today.
"""
import uuid

from django.db import models


class PayComponent(models.Model):
    """One earning/deduction/contribution definition, referenced everywhere
    else by `code` (immutable, never by `name` — see `name`'s own help_text)."""

    CATEGORY_EARNING              = 'earning'
    CATEGORY_DEDUCTION             = 'deduction'
    CATEGORY_EMPLOYER_CONTRIBUTION = 'employer_contribution'
    CATEGORY_REIMBURSEMENT         = 'reimbursement'
    CATEGORY_BENEFIT               = 'benefit'
    CATEGORY_STATUTORY             = 'statutory'
    CATEGORY_INFORMATIONAL         = 'informational'
    CATEGORY_NET_PAY               = 'net_pay'
    CATEGORY_CHOICES = [
        (CATEGORY_EARNING,              'Earning'),
        (CATEGORY_DEDUCTION,             'Deduction'),
        (CATEGORY_EMPLOYER_CONTRIBUTION, 'Employer contribution'),
        (CATEGORY_REIMBURSEMENT,         'Reimbursement'),
        (CATEGORY_BENEFIT,               'Benefit'),
        (CATEGORY_STATUTORY,             'Statutory'),
        (CATEGORY_INFORMATIONAL,         'Informational'),
        (CATEGORY_NET_PAY,               'Net pay'),
    ]

    # Mirrors SalaryComponent.CALCULATION_TYPE_CHOICES' 4 methods plus the 3
    # genuinely new ones the master prompt asks for (slab/input/system) that
    # nothing in this codebase computes yet — present as a documented option,
    # not wired to anything, same "data model ahead of the engine that will
    # consume it" relationship Task B has to Task C.
    METHOD_FIXED      = 'fixed'
    METHOD_PERCENTAGE = 'percentage'
    METHOD_FORMULA    = 'formula'
    METHOD_SLAB       = 'slab'
    METHOD_INPUT      = 'input'
    METHOD_SYSTEM     = 'system'
    CALCULATION_METHOD_CHOICES = [
        (METHOD_FIXED,      'Fixed amount'),
        (METHOD_PERCENTAGE, 'Percentage of a base'),
        (METHOD_FORMULA,    'Formula'),
        (METHOD_SLAB,       'Slab table'),
        (METHOD_INPUT,      'Input (supplied per period)'),
        (METHOD_SYSTEM,     'System-computed (statutory/tax/LOP engine)'),
    ]

    PRORATION_NONE          = 'none'
    PRORATION_CALENDAR_DAYS = 'calendar_days'
    PRORATION_WORKING_DAYS  = 'working_days'
    PRORATION_PAID_DAYS     = 'paid_days'
    PRORATION_CHOICES = [
        (PRORATION_NONE,          'Not prorated'),
        (PRORATION_CALENDAR_DAYS, 'Calendar days'),
        (PRORATION_WORKING_DAYS,  'Working days'),
        (PRORATION_PAID_DAYS,     'Paid days'),
    ]

    STATUS_DRAFT    = 'draft'
    STATUS_PUBLISHED = 'published'
    STATUS_RETIRED  = 'retired'
    STATUS_CHOICES = [
        (STATUS_DRAFT,     'Draft'),
        (STATUS_PUBLISHED, 'Published'),
        (STATUS_RETIRED,   'Retired'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    # ── Identity ─────────────────────────────────────────────────────────
    code = models.CharField(
        max_length=40, unique=True,
        help_text=(
            'Immutable identifier (e.g. BASIC, HRA, PF_EE). Every reference '
            'to this component — a structure, a formula, a wage-basis '
            'aggregate — uses this code, never `name`, so renaming the '
            'payslip label never breaks anything that depends on it.'
        ),
    )
    name = models.CharField(max_length=100, help_text='Internal name — safe to change freely; never referenced by code.')
    payslip_label = models.CharField(
        max_length=100, blank=True,
        help_text='What actually prints on the payslip. Falls back to `name` when blank.',
    )

    # ── Classification ───────────────────────────────────────────────────
    category = models.CharField(max_length=30, choices=CATEGORY_CHOICES)
    payslip_group = models.CharField(
        max_length=40, blank=True,
        help_text='Section header this component is grouped under on the payslip (e.g. "Earnings", "Statutory deductions").',
    )
    display_order = models.PositiveSmallIntegerField(default=0)
    show_on_payslip = models.BooleanField(default=True)
    show_if_zero = models.BooleanField(default=False)

    # ── Calculation ──────────────────────────────────────────────────────
    calculation_method = models.CharField(max_length=20, choices=CALCULATION_METHOD_CHOICES)
    base_component_code = models.CharField(
        max_length=40, blank=True,
        help_text=(
            'For percentage/formula methods: the `code` of the component '
            '(or a named aggregate such as GROSS_FOR_PF) this one is '
            'computed against. A plain code, not a FK — aggregates are not '
            'real PayComponent rows, so a FK would reject them.'
        ),
    )
    default_value = models.DecimalField(
        max_digits=12, decimal_places=4, null=True, blank=True,
        help_text='Fixed amount, or percentage (e.g. 40.00 for 40%), depending on calculation_method.',
    )
    rounding_mode = models.CharField(
        max_length=20,
        choices=[('none', 'No rounding'), ('round', 'Round'), ('ceiling', 'Round up'), ('floor', 'Round down')],
        default='round',
    )
    rounding_step = models.DecimalField(max_digits=6, decimal_places=2, default=1)

    # ── Proration and attendance ─────────────────────────────────────────
    proration = models.CharField(max_length=20, choices=PRORATION_CHOICES, default=PRORATION_NONE)
    affected_by_lop = models.BooleanField(default=False)

    # ── Tax ──────────────────────────────────────────────────────────────
    is_taxable = models.BooleanField(default=True)
    tax_section_code = models.CharField(
        max_length=40, blank=True,
        help_text='Income-tax exemption section this component falls under, if any (e.g. HRA_EXEMPTION). Not resolved by anything yet — Task G introduces TaxSection.',
    )

    # ── Contribution wage-basis flags ───────────────────────────────────
    pf_wage_inclusion = models.BooleanField(default=False)
    esi_wage_inclusion = models.BooleanField(default=False)
    gratuity_wage_inclusion = models.BooleanField(default=False)
    bonus_wage_inclusion = models.BooleanField(default=False)

    # ── Other flags ──────────────────────────────────────────────────────
    is_arrear_eligible = models.BooleanField(default=False)
    is_recurring = models.BooleanField(default=True)
    is_company_allowance = models.BooleanField(
        default=False,
        help_text='Company-managed allowance available for selection in legacy salary structures.',
    )
    gl_account_code = models.CharField(max_length=40, blank=True, help_text='Reserved for Phase 7B accounting-journal export — not read by anything today.')
    min_amount = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    max_amount = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)

    # ── Lifecycle ────────────────────────────────────────────────────────
    effective_from = models.DateField(null=True, blank=True)
    effective_to = models.DateField(null=True, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_DRAFT)
    is_active = models.BooleanField(default=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'payroll_pay_components'
        ordering = ['display_order', 'code']

    def __str__(self):
        return f'{self.code} — {self.name}'
