"""
Phase 7A Task J — the payroll.v2 flag and shadow-run diff results.

Scoped down from the master prompt's full ShadowPayslip/ShadowPayslipLine
mirror-table design to one diff-report row per real EmployeePayslip
(`PayslipShadowRunResult`) — stated plainly: this records WHETHER the new
composer (services_shadow_engine.compute_payslip_via_new_data) agreed with
the stored payslip and exactly what differed when it didn't, rather than
persisting a full duplicate payslip+line set for every historical cycle.
Given this pass's bounded scope that's sufficient to prove or disprove
parity and to gate `PayrollV2Entitlement.is_enabled`; a full mirror-table
shadow store is real additional scope for whoever does the actual
engine cutover.
"""
import uuid

from django.db import models


class PayslipShadowRunResult(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    payslip = models.OneToOneField(
        'payroll.EmployeePayslip', on_delete=models.CASCADE, related_name='shadow_run_result',
    )
    is_match = models.BooleanField()
    # {field_name: {"stored": "...", "recomputed": "..."}} for every field
    # that differed — empty dict when is_match is True.
    diffs = models.JSONField(default=dict, blank=True)
    # Set when the composer couldn't even attempt a recompute (e.g. no
    # structure resolvable) — distinct from a real numeric mismatch.
    error = models.TextField(blank=True)
    engine_version = models.CharField(max_length=40, default='task-j-v1')
    computed_at = models.DateTimeField(auto_now=True)

    # The master prompt's own escape hatch: "Any difference blocks
    # completion unless the owner approves it in writing... with the root
    # cause explained." A mismatch stays a real mismatch (diffs/is_match
    # are never edited to force a pass) — this is a SEPARATE sign-off
    # record on top of it, so enable_payroll_v2()'s gate can tell "nobody
    # has looked at this yet" apart from "a human confirmed the root cause
    # and accepted it," without ever pretending the numbers actually matched.
    owner_approved = models.BooleanField(default=False)
    approval_note = models.TextField(blank=True)
    approved_by = models.ForeignKey(
        'accounts.User', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='approved_shadow_run_exceptions',
    )
    approved_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = 'payroll_payslip_shadow_run_results_v2'
        ordering = ['-computed_at']

    def __str__(self):
        return f'{self.payslip_id} — {"match" if self.is_match else "DIFF"}'


class PayrollV2Entitlement(models.Model):
    """One row per legal entity (null = the whole company, matching every
    other nullable legal_entity FK this phase has introduced). `is_enabled`
    can only ever be set True by `services_shadow_run.enable_payroll_v2()`,
    which enforces the gate — never set it directly."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    legal_entity = models.OneToOneField(
        'platform_core.LegalEntity', on_delete=models.CASCADE, null=True, blank=True,
        related_name='payroll_v2_entitlement',
    )
    is_enabled = models.BooleanField(default=False)
    enabled_at = models.DateTimeField(null=True, blank=True)
    last_passing_shadow_run_at = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'payroll_v2_entitlements_v2'

    def __str__(self):
        scope = self.legal_entity.code if self.legal_entity_id else 'company-wide'
        return f'payroll.v2 ({scope}): {"ON" if self.is_enabled else "off"}'
