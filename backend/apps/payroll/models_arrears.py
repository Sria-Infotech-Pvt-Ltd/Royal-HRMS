"""Phase 7B Task E — arrears engine."""
import uuid

from django.db import models


class ArrearsRequest(models.Model):
    TRIGGER_COMPENSATION = 'compensation_revision'
    TRIGGER_ATTENDANCE   = 'attendance_changed_after_payroll'
    TRIGGER_LOP          = 'lop_change'
    TRIGGER_STATUTORY    = 'statutory_change'
    TRIGGER_MANUAL       = 'manual'
    TRIGGER_CHOICES = [
        (TRIGGER_COMPENSATION, 'Back-dated compensation revision'),
        (TRIGGER_ATTENDANCE,   'Attendance changed after payroll'),
        (TRIGGER_LOP,          'LOP change after finalisation'),
        (TRIGGER_STATUTORY,    'Back-dated statutory/component change'),
        (TRIGGER_MANUAL,       'Manual request'),
    ]
    STATUS_DRAFT    = 'draft'
    STATUS_PREVIEWED = 'previewed'
    STATUS_APPROVED = 'approved'
    STATUS_PAID     = 'paid'
    STATUS_REJECTED = 'rejected'
    STATUS_CHOICES = [
        (STATUS_DRAFT, 'Draft'), (STATUS_PREVIEWED, 'Previewed'),
        (STATUS_APPROVED, 'Approved'), (STATUS_PAID, 'Paid'), (STATUS_REJECTED, 'Rejected'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    employee = models.ForeignKey('accounts.User', on_delete=models.CASCADE, related_name='arrears_requests')
    trigger = models.CharField(max_length=40, choices=TRIGGER_CHOICES)
    trigger_note = models.CharField(max_length=300, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_DRAFT)
    paid_in_run = models.ForeignKey('payroll.PayrollRun', on_delete=models.SET_NULL, null=True, blank=True, related_name='arrears_requests')
    approved_by = models.ForeignKey('accounts.User', on_delete=models.SET_NULL, null=True, blank=True, related_name='arrears_approved')
    approved_at = models.DateTimeField(null=True, blank=True)
    created_by = models.ForeignKey('accounts.User', on_delete=models.SET_NULL, null=True, blank=True, related_name='arrears_requested')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'payroll_arrears_requests_v2'
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.employee_id} arrears ({self.trigger})'


class ArrearsLine(models.Model):
    """One affected past period's per-component difference —
    (corrected_amount - original_amount), computed in shadow via
    services_arrears.py reusing the Task J composer, never by editing the
    original payslip."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    request = models.ForeignKey(ArrearsRequest, on_delete=models.CASCADE, related_name='lines')
    affected_payslip = models.ForeignKey('payroll.EmployeePayslip', on_delete=models.PROTECT, related_name='arrears_lines')
    component_code = models.CharField(max_length=40)
    original_amount = models.DecimalField(max_digits=12, decimal_places=2)
    corrected_amount = models.DecimalField(max_digits=12, decimal_places=2)
    difference = models.DecimalField(max_digits=12, decimal_places=2)

    class Meta:
        db_table = 'payroll_arrears_lines_v2'
        ordering = ['affected_payslip', 'component_code']

    def __str__(self):
        return f'{self.affected_payslip_id} › {self.component_code}: {self.difference}'
