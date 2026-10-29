import uuid

from django.conf import settings
from django.db import models


class EmployeeEditDraft(models.Model):
    """
    In-progress "Edit full record" panel changes, saved but not yet applied
    to the live employee record — lets HR/admin pause mid-edit (e.g. waiting
    on a document or approval) and resume later without losing work.

    Private to the admin who created it: unique_together(employee, created_by)
    means each admin gets their own draft slot per employee, and the
    edit-draft views only ever look up a draft by (employee, request.user) —
    one admin never sees another's in-progress draft.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    employee = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='edit_drafts',
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='created_edit_drafts',
    )
    # The full Edit Record form state (same shape the frontend's
    # EditRecordDraftState already uses for its local drafts) — stored
    # opaquely; this model doesn't need to understand the shape, only
    # round-trip it.
    data = models.JSONField(default=dict)
    last_step = models.PositiveSmallIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'employee_edit_drafts'
        unique_together = ('employee', 'created_by')

    def __str__(self):
        return f'Edit draft for {self.employee_id} by {self.created_by_id}'
