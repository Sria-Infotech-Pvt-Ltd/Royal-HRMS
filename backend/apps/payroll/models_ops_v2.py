"""
Phase 7B Task O — the payroll_ops.v2 flag. Same enable-only-with-a-passing-
check pattern as Phase 7A's PayrollV2Entitlement — a separate flag, since
this one gates the OPERATIONS layer (runs/stages/bank files/statutory
files), not the calculation engine Phase 7A's flag gates.

Scoped down from the master prompt's full byte-identical-file replay
harness: this pass's gate checks that every PayrollRun's generated bank/
statutory files have a recorded checksum and that the run's own
PayrollCheckResult set has no un-acknowledged errors — a real,
code-enforced precondition, not the full historical-replay-byte-parity
system (which would require real historical bank/ECR/ESIC files to diff
against; none exist in this dev database to replay). Stated plainly as a
reduced scope, consistent with every other task this phase.
"""
import uuid

from django.db import models


class PayrollOpsV2Entitlement(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    legal_entity = models.OneToOneField(
        'platform_core.LegalEntity', on_delete=models.CASCADE, null=True, blank=True,
        related_name='payroll_ops_v2_entitlement',
    )
    is_enabled = models.BooleanField(default=False)
    enabled_at = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'payroll_ops_v2_entitlements_v2'

    def __str__(self):
        scope = self.legal_entity.code if self.legal_entity_id else 'company-wide'
        return f'payroll_ops.v2 ({scope}): {"ON" if self.is_enabled else "off"}'
