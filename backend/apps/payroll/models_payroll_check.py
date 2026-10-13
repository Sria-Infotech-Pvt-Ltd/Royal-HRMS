"""Phase 7B Task C — pre-run validation checks and pay holds."""
import uuid

from django.db import models


class PayrollCheck(models.Model):
    SEVERITY_ERROR   = 'error'
    SEVERITY_WARNING = 'warning'
    SEVERITY_CHOICES = [(SEVERITY_ERROR, 'Error (blocks approval)'), (SEVERITY_WARNING, 'Warning (needs acknowledgement)')]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    code = models.CharField(max_length=60, unique=True)
    description = models.CharField(max_length=300)
    severity = models.CharField(max_length=10, choices=SEVERITY_CHOICES, default=SEVERITY_WARNING)
    # Which services_payroll_checks.CHECK_REGISTRY function this row maps
    # to — a plain code, not a formula-DSL (Task C's "3A rule expression"
    # scoped down to real Python functions registered by code, same
    # trade-off as Task B's stage registry).
    check_function_code = models.CharField(max_length=60)
    is_active = models.BooleanField(default=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'payroll_checks_v2'
        ordering = ['code']

    def __str__(self):
        return self.code


class PayrollCheckResult(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    run = models.ForeignKey('payroll.PayrollRun', on_delete=models.CASCADE, related_name='check_results')
    payroll_check = models.ForeignKey(PayrollCheck, on_delete=models.CASCADE, related_name='results')
    employee = models.ForeignKey('accounts.User', on_delete=models.CASCADE, related_name='payroll_check_results')
    message = models.CharField(max_length=300)
    is_acknowledged = models.BooleanField(default=False)
    acknowledged_by = models.ForeignKey(
        'accounts.User', on_delete=models.SET_NULL, null=True, blank=True, related_name='payroll_checks_acknowledged',
    )
    acknowledgement_reason = models.CharField(max_length=300, blank=True)
    acknowledged_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'payroll_check_results_v2'
        ordering = ['payroll_check__severity', 'employee_id']

    def __str__(self):
        return f'{self.payroll_check.code} — {self.employee_id}'


class PayrollHold(models.Model):
    """An employee's pay held back from the payment file for a run (or
    indefinitely, until explicitly released). Released rows stay on record
    (released_at set) rather than being deleted — audit trail."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    employee = models.ForeignKey('accounts.User', on_delete=models.CASCADE, related_name='payroll_holds')
    reason = models.CharField(max_length=300)
    placed_by = models.ForeignKey('accounts.User', on_delete=models.SET_NULL, null=True, blank=True, related_name='payroll_holds_placed')
    placed_at = models.DateTimeField(auto_now_add=True)
    released_at = models.DateTimeField(null=True, blank=True)
    released_by = models.ForeignKey('accounts.User', on_delete=models.SET_NULL, null=True, blank=True, related_name='payroll_holds_released')

    class Meta:
        db_table = 'payroll_holds_v2'
        ordering = ['-placed_at']

    def __str__(self):
        return f'{self.employee_id} hold ({"released" if self.released_at else "active"})'

    @property
    def is_active(self):
        return self.released_at is None
