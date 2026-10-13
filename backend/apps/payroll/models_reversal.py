"""Phase 7B Task D — reversal runs. The original EmployeePayslip is never edited."""
import uuid

from django.db import models


class ReversalEntry(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    run = models.ForeignKey('payroll.PayrollRun', on_delete=models.CASCADE, related_name='reversal_entries')
    original_payslip = models.ForeignKey('payroll.EmployeePayslip', on_delete=models.PROTECT, related_name='reversal_entries')
    component_code = models.CharField(max_length=40)
    # Always the negative of the original line's amount — a reversal
    # cancels out, never edits, the original.
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    reason = models.CharField(max_length=300)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'payroll_reversal_entries_v2'
        ordering = ['-created_at']

    def __str__(self):
        return f'Reversal of {self.original_payslip_id} › {self.component_code}: {self.amount}'
