"""Phase 8B gap-closure — exit interview (HR-only confidential), separation-triggered clearance checklist link."""
import uuid

from django.db import models


class ExitInterview(models.Model):
    """Confidential — HR only. Field security is enforced at the view/
    serializer layer (Phase 4's dynamic-entity field security doesn't
    attach to plain Django fields, confirmed earlier this session); this
    model itself just marks `is_confidential=True` by convention so a view
    has something concrete to check."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    request = models.OneToOneField('hrms.SeparationRequest', on_delete=models.CASCADE, related_name='exit_interview')
    primary_reason = models.CharField(max_length=100, blank=True)
    responses = models.JSONField(default=dict, help_text='{"question_key": "answer"} — a Phase 2 layout-based form, simplified to JSON here.')
    conducted_by = models.ForeignKey('accounts.User', on_delete=models.SET_NULL, null=True, blank=True, related_name='exit_interviews_conducted')
    conducted_at = models.DateTimeField(null=True, blank=True)
    is_confidential = models.BooleanField(default=True)

    class Meta:
        db_table = 'hrms_exit_interviews_v2'

    def __str__(self):
        return f'Exit interview for {self.request_id}'


class SeparationChecklistLink(models.Model):
    """Links a SeparationRequest to the 8A ChecklistInstance that tracks
    its clearance tasks — created by
    services_separation_v2b.start_clearance_checklist()."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    request = models.OneToOneField('hrms.SeparationRequest', on_delete=models.CASCADE, related_name='checklist_link')
    checklist_instance = models.ForeignKey('hrms.ChecklistInstance', on_delete=models.CASCADE, related_name='separation_links')

    class Meta:
        db_table = 'hrms_separation_checklist_links_v2'

    def __str__(self):
        return f'{self.request_id} -> {self.checklist_instance_id}'
