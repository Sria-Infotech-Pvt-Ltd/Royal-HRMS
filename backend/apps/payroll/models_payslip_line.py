"""
Phase 7A Task E — payslip lines.

`PayslipLine` is the line-item shape every fixed `EmployeePayslip` column
will eventually be replaced by. For now it's purely derived/additive:
`services_payslip_lines.persist_lines_for_payslip()` reads an ALREADY-
COMPUTED `EmployeePayslip` (written by the untouched legacy engine) and
writes matching `PayslipLine` rows — nothing recomputes anything, and
nothing that reads `EmployeePayslip`'s own columns today needs to change.
"""
import uuid

from django.db import models


class PayslipLine(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    payslip = models.ForeignKey('payroll.EmployeePayslip', on_delete=models.CASCADE, related_name='lines')
    component_code = models.CharField(max_length=40)
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    ytd_amount = models.DecimalField(max_digits=14, decimal_places=2, null=True, blank=True)
    # No identity data (see Task I's own rule for the richer trace that will
    # eventually live alongside this) — just the numeric/config inputs that
    # produced `amount`, e.g. {"source": "legacy_column", "column": "pf_employee", "pf_wage_base": "15000.00"}.
    calculation_basis = models.JSONField(default=dict, blank=True)
    is_arrear = models.BooleanField(default=False)
    arrear_period = models.DateField(null=True, blank=True)
    display_order = models.PositiveSmallIntegerField(default=0)
    rule_version_ref = models.CharField(max_length=60, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'payroll_payslip_lines_v2'
        unique_together = [('payslip', 'component_code', 'is_arrear', 'arrear_period')]
        ordering = ['display_order', 'component_code']

    def __str__(self):
        return f'{self.payslip_id} › {self.component_code} = {self.amount}'
