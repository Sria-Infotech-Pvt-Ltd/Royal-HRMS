"""
PersonnelActionRequest — a "Perform an action" (Promotion / Org assignment /
Pay change / Confirmation) that someone WITHOUT direct edit authority raised
and that must be approved, step by step, before it takes effect.

HR / Branch Admin / System Admin (anyone holding employees.edit) keep
applying these actions instantly through the existing endpoints — nothing here
changes that. This model only exists for the maker-checker path: a Reporting
Manager raises, the people on the approval route decide, and the LAST approval
applies the change through the very same view the direct path uses, so
validation, audit logging and notifications behave identically.

Separation is deliberately not modelled here: the Separation module already
has its own multi-stage approval workflow (hrms.SeparationRequest).
"""
import uuid

from django.conf import settings
from django.db import models


class PersonnelActionRequest(models.Model):
    TYPE_PROMOTION       = 'promotion'
    TYPE_ORG_ASSIGNMENT  = 'org_assignment'
    TYPE_PAY_CHANGE      = 'pay_change'
    TYPE_CONFIRMATION    = 'confirmation'
    TYPE_CHOICES = [
        (TYPE_PROMOTION,      'Promotion'),
        (TYPE_ORG_ASSIGNMENT, 'Org assignment'),
        (TYPE_PAY_CHANGE,     'Pay change'),
        (TYPE_CONFIRMATION,   'Confirmation'),
    ]

    STATUS_PENDING   = 'pending'
    STATUS_APPLIED   = 'applied'
    STATUS_REJECTED  = 'rejected'
    STATUS_CANCELLED = 'cancelled'
    STATUS_FAILED    = 'failed'
    STATUS_CHOICES = [
        (STATUS_PENDING,   'Pending approval'),
        (STATUS_APPLIED,   'Approved & applied'),
        (STATUS_REJECTED,  'Rejected'),
        (STATUS_CANCELLED, 'Cancelled'),
        (STATUS_FAILED,    'Approved, could not be applied'),
    ]

    id             = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    employee       = models.ForeignKey(
                         settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
                         related_name='personnel_action_requests',
                     )
    action_type    = models.CharField(max_length=20, choices=TYPE_CHOICES)
    reason         = models.CharField(max_length=60, blank=True, default='')
    effective_from = models.DateField()
    # The fields the action would change, exactly as the direct endpoint
    # expects them: position / annual_ctc / reporting_manager_id / work_location.
    payload        = models.JSONField(default=dict, blank=True)
    # Snapshot taken at raise time so the inbox can show BEFORE → AFTER
    # without re-deriving it from data that may have changed since.
    before         = models.JSONField(default=dict, blank=True)
    raised_by      = models.ForeignKey(
                         settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
                         null=True, blank=True, related_name='raised_personnel_actions',
                     )
    status         = models.CharField(max_length=12, choices=STATUS_CHOICES, default=STATUS_PENDING, db_index=True)
    # Ordered approval route. Each step:
    #   {key, label, status: pending|approved|rejected|skipped,
    #    decided_by_id, decided_by_name, decided_at, note}
    steps          = models.JSONField(default=list, blank=True)
    current_step   = models.PositiveSmallIntegerField(default=0)
    decision_note  = models.TextField(blank=True, default='')
    apply_error    = models.TextField(blank=True, default='')
    applied_at     = models.DateTimeField(null=True, blank=True)
    created_at     = models.DateTimeField(auto_now_add=True)
    updated_at     = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'hrms_personnel_action_requests'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['status', 'created_at'], name='par_status_created_idx'),
            models.Index(fields=['employee', 'status'],   name='par_employee_status_idx'),
        ]

    def __str__(self) -> str:
        return f'{self.get_action_type_display()} for {self.employee_id} ({self.status})'
