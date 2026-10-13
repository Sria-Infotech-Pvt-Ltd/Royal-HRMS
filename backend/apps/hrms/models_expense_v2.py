"""
Phase 8B Task A — expense categories as a master, and a claim/line model
that COEXISTS with the real `Expense` (kept populated for compatibility —
see services_expense_v2.migrate_expense_to_claim(), which creates exactly
one ExpenseLine per legacy Expense, "an old Expense = a claim with one
line" per the master prompt's own compatibility rule).

Scoped down, stated plainly:
- No travel requests/advances (Task A.4) — real, separate scope.
- Policy evaluation (Task A.3) is ONE rule only this pass (a per-category
  daily/claim/month limit), not the full per-diem/mileage/duplicate-
  detection/out-of-policy-routing rule set — see
  services_expense_v2.evaluate_policy()'s own docstring.
- No multi-currency exchange-rate resolution — ExpenseLine has
  currency/exchange_rate/base_amount fields ready for it, but every
  migrated legacy line uses rate=1 (same currency as base), and nothing
  computes a REAL rate from Phase 1 exchange rates yet.
"""
import uuid

from django.db import models


class ExpenseCategory(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    code = models.CharField(max_length=40, unique=True)
    name = models.CharField(max_length=100)
    parent = models.ForeignKey('self', on_delete=models.SET_NULL, null=True, blank=True, related_name='children')
    gl_code = models.CharField(max_length=40, blank=True)
    # 'taxable' or 'exempt' — matches the 7A tax_section_code convention
    # on PayComponent rather than inventing a parallel vocabulary.
    tax_treatment = models.CharField(max_length=20, choices=[('taxable', 'Taxable'), ('exempt', 'Exempt')], default='exempt')
    requires_receipt_above_amount = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    period_limit_amount = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True,
        help_text='Max total claimable in this category over whatever period the caller checks (day/claim/month) — null = no limit.',
    )
    is_unit_based = models.BooleanField(default=False)
    unit_rate = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True, help_text='Per-km/per-night/per-day rate when is_unit_based.')
    # Phase 8B gap-closure — remaining policy dimensions.
    per_diem_by_city_tier = models.JSONField(default=dict, blank=True, help_text='{"tier_1": "2000", "tier_2": "1500", "tier_3": "1000"} — per-diem rate by city tier.')
    submission_deadline_days = models.PositiveSmallIntegerField(null=True, blank=True, help_text='Max days after expense_date a line may still be submitted. Null = no deadline.')
    OUT_OF_POLICY_BLOCK = 'block'
    OUT_OF_POLICY_ALLOW_WITH_JUSTIFICATION = 'allow_with_justification'
    OUT_OF_POLICY_EXTRA_APPROVAL = 'extra_approval'
    OUT_OF_POLICY_CHOICES = [
        (OUT_OF_POLICY_BLOCK, 'Block'), (OUT_OF_POLICY_ALLOW_WITH_JUSTIFICATION, 'Allow with justification'),
        (OUT_OF_POLICY_EXTRA_APPROVAL, 'Route to extra approval'),
    ]
    out_of_policy_behavior = models.CharField(max_length=30, choices=OUT_OF_POLICY_CHOICES, default=OUT_OF_POLICY_EXTRA_APPROVAL)
    legacy_category_code = models.CharField(max_length=20, blank=True, help_text='The old Expense.CATEGORY_CHOICES value this migrated from, if any.')
    is_active = models.BooleanField(default=True)

    class Meta:
        db_table = 'hrms_expense_categories_v2'
        ordering = ['code']

    def __str__(self):
        return self.code


class ExpenseClaim(models.Model):
    STATUS_DRAFT      = 'draft'
    STATUS_SUBMITTED  = 'submitted'
    STATUS_APPROVED   = 'approved'
    STATUS_REJECTED   = 'rejected'
    STATUS_PARTIALLY_APPROVED = 'partially_approved'
    STATUS_CHOICES = [
        (STATUS_DRAFT, 'Draft'), (STATUS_SUBMITTED, 'Submitted'), (STATUS_APPROVED, 'Approved'),
        (STATUS_REJECTED, 'Rejected'), (STATUS_PARTIALLY_APPROVED, 'Partially approved'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    # Continues the existing expense_number sequence — see
    # services_expense_v2.next_claim_number(), which reads
    # Expense.expense_number's current max rather than starting a second,
    # colliding sequence from 1.
    claim_number = models.PositiveIntegerField(unique=True, null=True, blank=True, db_index=True)
    employee = models.ForeignKey('accounts.User', on_delete=models.CASCADE, related_name='expense_claims_v2')
    purpose = models.CharField(max_length=200, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_DRAFT)
    legacy_expense = models.OneToOneField('hrms.Expense', on_delete=models.SET_NULL, null=True, blank=True, related_name='claim_v2')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'hrms_expense_claims_v2'
        ordering = ['-created_at']

    def __str__(self):
        return f'Claim #{self.claim_number or self.id}'

    @property
    def total_base_amount(self):
        from django.db.models import Sum
        return self.lines.aggregate(total=Sum('base_amount'))['total'] or 0


class ExpenseLine(models.Model):
    POLICY_RESULT_WITHIN_POLICY = 'within_policy'
    POLICY_RESULT_OVER_LIMIT    = 'over_limit'
    POLICY_RESULT_CHOICES = [(POLICY_RESULT_WITHIN_POLICY, 'Within policy'), (POLICY_RESULT_OVER_LIMIT, 'Over limit')]
    STATUS_PENDING  = 'pending'
    STATUS_APPROVED = 'approved'
    STATUS_REJECTED = 'rejected'
    STATUS_CHOICES = [(STATUS_PENDING, 'Pending'), (STATUS_APPROVED, 'Approved'), (STATUS_REJECTED, 'Rejected')]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    claim = models.ForeignKey(ExpenseClaim, on_delete=models.CASCADE, related_name='lines')
    category = models.ForeignKey(ExpenseCategory, on_delete=models.PROTECT, related_name='lines')
    expense_date = models.DateField()
    quantity = models.DecimalField(max_digits=8, decimal_places=2, default=1, help_text='For unit-based categories (km/nights/days); 1 otherwise.')
    amount = models.DecimalField(max_digits=10, decimal_places=2, help_text='quantity x rate for unit-based; the raw claimed amount otherwise.')
    currency_code = models.CharField(max_length=3, default='INR')
    exchange_rate = models.DecimalField(max_digits=10, decimal_places=4, default=1)
    base_amount = models.DecimalField(max_digits=10, decimal_places=2, help_text='amount * exchange_rate.')
    merchant = models.CharField(max_length=200, blank=True)
    description = models.TextField(blank=True)
    policy_result = models.CharField(max_length=20, choices=POLICY_RESULT_CHOICES, default=POLICY_RESULT_WITHIN_POLICY)
    policy_explanation = models.CharField(max_length=300, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_PENDING)

    class Meta:
        db_table = 'hrms_expense_lines_v2'
        ordering = ['expense_date']

    def __str__(self):
        return f'{self.claim_id} › {self.category.code}: {self.base_amount}'

    def save(self, *args, **kwargs):
        self.base_amount = self.amount * self.exchange_rate
        super().save(*args, **kwargs)
