"""Phase 7B Task F — loans and advances."""
import uuid

from django.db import models


class LoanType(models.Model):
    INTEREST_NONE      = 'none'
    INTEREST_SIMPLE    = 'simple'
    INTEREST_REDUCING  = 'reducing'
    INTEREST_CHOICES = [
        (INTEREST_NONE, 'No interest'), (INTEREST_SIMPLE, 'Simple'), (INTEREST_REDUCING, 'Reducing balance'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    code = models.CharField(max_length=40, unique=True)
    name = models.CharField(max_length=100)
    max_amount = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    interest_type = models.CharField(max_length=20, choices=INTEREST_CHOICES, default=INTEREST_NONE)
    interest_rate = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    max_tenure_months = models.PositiveSmallIntegerField(default=12)
    # Perquisite tax (interest below market rate is a taxable perquisite
    # under Indian tax law) — default OFF since no tax engine wiring exists
    # for it yet; flag exists so the data model doesn't need to change
    # later, stated plainly rather than silently computed.
    is_perquisite_taxable = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'payroll_loan_types_v2'
        ordering = ['code']

    def __str__(self):
        return self.code


class EmployeeLoan(models.Model):
    STATUS_ACTIVE     = 'active'
    STATUS_CLOSED     = 'closed'
    STATUS_FORECLOSED = 'foreclosed'
    STATUS_CHOICES = [
        (STATUS_ACTIVE, 'Active'), (STATUS_CLOSED, 'Closed'), (STATUS_FORECLOSED, 'Foreclosed'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    employee = models.ForeignKey('accounts.User', on_delete=models.CASCADE, related_name='loans')
    loan_type = models.ForeignKey(LoanType, on_delete=models.PROTECT, related_name='loans')
    principal_amount = models.DecimalField(max_digits=12, decimal_places=2)
    tenure_months = models.PositiveSmallIntegerField()
    disbursement_date = models.DateField()
    outstanding_balance = models.DecimalField(max_digits=12, decimal_places=2)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_ACTIVE)
    approved_by = models.ForeignKey('accounts.User', on_delete=models.SET_NULL, null=True, blank=True, related_name='loans_approved')

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'payroll_employee_loans_v2'
        ordering = ['-disbursement_date']

    def __str__(self):
        return f'{self.employee_id} — {self.loan_type.code} ({self.principal_amount})'


class LoanEmiSchedule(models.Model):
    STATUS_PENDING  = 'pending'
    STATUS_DEDUCTED = 'deducted'
    STATUS_SKIPPED  = 'skipped'
    STATUS_DEFERRED = 'deferred'
    STATUS_CHOICES = [
        (STATUS_PENDING, 'Pending'), (STATUS_DEDUCTED, 'Deducted'),
        (STATUS_SKIPPED, 'Skipped'), (STATUS_DEFERRED, 'Deferred'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    loan = models.ForeignKey(EmployeeLoan, on_delete=models.CASCADE, related_name='emi_schedule')
    installment_number = models.PositiveSmallIntegerField()
    due_date = models.DateField()
    principal_component = models.DecimalField(max_digits=12, decimal_places=2)
    interest_component = models.DecimalField(max_digits=12, decimal_places=2)
    emi_amount = models.DecimalField(max_digits=12, decimal_places=2)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_PENDING)
    deducted_in_run = models.ForeignKey(
        'payroll.PayrollRun', on_delete=models.SET_NULL, null=True, blank=True, related_name='loan_emis_deducted',
    )

    class Meta:
        db_table = 'payroll_loan_emi_schedule_v2'
        unique_together = [('loan', 'installment_number')]
        ordering = ['loan', 'installment_number']

    def __str__(self):
        return f'{self.loan_id} EMI#{self.installment_number}'
