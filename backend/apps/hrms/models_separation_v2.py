"""
Phase 8B Task B — separation/exit additions on top of the untouched
SeparationRequest/SeparationApprovalStage/SeparationClearance/
SeparationSettlement models.

Scoped down, stated plainly: no lookup-conversion of
separation_type/reason/clearance_type/document_type (still the real
hardcoded choices — migrating them to Phase 1 lookups without breaking
every existing choice-based query is real, separate work), no exit-
interview form, no attrition-report queries. This builds the two concrete
new pieces that compose cleanly with what already exists: a link from a
SeparationRequest to the real `PayrollRun`(final_settlement) it triggers
(Phase 7B, already built), and post-exit alumni/rehire tracking.
"""
import uuid

from django.db import models


class SeparationFinalSettlementLink(models.Model):
    """One row per SeparationRequest once its final-settlement PayrollRun
    (Phase 7B Task L) has been created — lets the separation module show
    "settlement: in progress / finalized" without duplicating any
    settlement logic."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    request = models.OneToOneField('hrms.SeparationRequest', on_delete=models.CASCADE, related_name='final_settlement_link')
    payroll_run = models.ForeignKey('payroll.PayrollRun', on_delete=models.SET_NULL, null=True, blank=True, related_name='separation_links')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'hrms_separation_final_settlement_links_v2'

    def __str__(self):
        return f'{self.request_id} -> {self.payroll_run_id}'


class AlumniRecord(models.Model):
    """Created once a SeparationRequest reaches a terminal approved
    status and the employee's account is deactivated — rehire_eligible is
    field-secured by whatever view surfaces it (Phase 4 scoping, not
    enforced here)."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    employee = models.OneToOneField('accounts.User', on_delete=models.CASCADE, related_name='alumni_record')
    separation_request = models.ForeignKey('hrms.SeparationRequest', on_delete=models.SET_NULL, null=True, blank=True, related_name='alumni_records')
    last_working_day = models.DateField()
    rehire_eligible = models.BooleanField(default=True)
    rehire_note = models.CharField(max_length=300, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'hrms_alumni_records_v2'
        ordering = ['-last_working_day']

    def __str__(self):
        return f'{self.employee_id} (rehire_eligible={self.rehire_eligible})'
