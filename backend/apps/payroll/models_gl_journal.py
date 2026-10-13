"""Phase 7B Task I — accounting journal."""
import uuid

from django.db import models


class GLMapping(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    component_code = models.CharField(max_length=40)
    legal_entity = models.ForeignKey('platform_core.LegalEntity', on_delete=models.CASCADE, null=True, blank=True, related_name='gl_mappings')
    debit_account_code = models.CharField(max_length=40)
    credit_account_code = models.CharField(max_length=40)
    narration_template = models.CharField(max_length=200, default='{component_code} for {period_start} to {period_end}')
    effective_from = models.DateField(null=True, blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        db_table = 'payroll_gl_mappings_v2'
        unique_together = [('component_code', 'legal_entity')]
        ordering = ['component_code']

    def __str__(self):
        return f'{self.component_code}: Dr {self.debit_account_code} / Cr {self.credit_account_code}'


class JournalEntry(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    run = models.ForeignKey('payroll.PayrollRun', on_delete=models.CASCADE, related_name='journal_entries')
    reversal_of = models.ForeignKey('self', on_delete=models.SET_NULL, null=True, blank=True, related_name='reversals')
    account_code = models.CharField(max_length=40)
    cost_centre = models.CharField(max_length=60, blank=True)
    debit_amount = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    credit_amount = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    narration = models.CharField(max_length=300)
    is_exported = models.BooleanField(default=False)
    exported_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'payroll_journal_entries_v2'
        ordering = ['run', 'account_code']

    def __str__(self):
        return f'{self.run_id}: {self.account_code} Dr{self.debit_amount}/Cr{self.credit_amount}'
