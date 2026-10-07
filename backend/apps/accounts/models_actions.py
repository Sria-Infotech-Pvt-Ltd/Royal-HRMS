"""
Phase 5B Task D — the employment action framework: admin-configurable
`ActionType`s with a declarative `effects` list resolved against a
code-registered handler registry (services_actions.EFFECT_HANDLERS), and
`EmploymentAction` — one row per actual hire/transfer/promotion/
confirmation/etc, append-only, reversed only via a correction action
(never edited or deleted).

Additive only: no existing endpoint creates one of these yet (that's
Task E/L's job). This phase proves the engine works standalone.
"""
from __future__ import annotations

import uuid

from django.db import models


class ActionType(models.Model):
    CATEGORY_CHOICES = [
        ('hire', 'Hire'), ('movement', 'Movement'), ('status', 'Status'),
        ('compensation', 'Compensation'), ('separation', 'Separation'),
        ('correction', 'Correction'), ('other', 'Other'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    code = models.CharField(max_length=50, unique=True)
    name = models.CharField(max_length=150)
    category = models.CharField(max_length=20, choices=CATEGORY_CHOICES)
    reasons = models.ForeignKey(
        'platform_core.LookupType', on_delete=models.SET_NULL, null=True, blank=True, related_name='action_types',
    )
    effects = models.JSONField(default=list, blank=True, help_text='[{"handler": "set_placement", ...params}, ...]')
    allowed_from_statuses = models.JSONField(default=list, blank=True, help_text='EMPLOYMENT_STATUS codes this action may start from; [] = any.')
    resulting_status = models.CharField(max_length=30, blank=True, help_text='EMPLOYMENT_STATUS code set on apply; blank = unchanged.')
    requires_effective_date = models.BooleanField(default=True)
    allow_backdating = models.BooleanField(default=True)
    max_backdate_days = models.PositiveIntegerField(null=True, blank=True)
    allow_future_dating = models.BooleanField(default=True)
    letter_template = models.CharField(max_length=100, blank=True)
    notification_events = models.JSONField(default=list, blank=True)
    is_system = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'hrms_action_types'
        ordering = ['category', 'name']

    def __str__(self):
        return self.code


class EmploymentAction(models.Model):
    STATUS_DRAFT = 'draft'
    STATUS_PENDING_APPROVAL = 'pending_approval'
    STATUS_APPROVED = 'approved'
    STATUS_SCHEDULED = 'scheduled'
    STATUS_APPLIED = 'applied'
    STATUS_REJECTED = 'rejected'
    STATUS_CANCELLED = 'cancelled'
    STATUS_REVERSED = 'reversed'
    STATUS_CHOICES = [
        (STATUS_DRAFT, 'Draft'), (STATUS_PENDING_APPROVAL, 'Pending Approval'),
        (STATUS_APPROVED, 'Approved'), (STATUS_SCHEDULED, 'Scheduled'),
        (STATUS_APPLIED, 'Applied'), (STATUS_REJECTED, 'Rejected'),
        (STATUS_CANCELLED, 'Cancelled'), (STATUS_REVERSED, 'Reversed'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    employee = models.ForeignKey('accounts.User', on_delete=models.CASCADE, related_name='employment_actions')
    action_type = models.ForeignKey(ActionType, on_delete=models.PROTECT, related_name='actions')
    reason = models.CharField(max_length=100, blank=True)
    effective_date = models.DateField()
    payload = models.JSONField(default=dict, blank=True)
    previous_values = models.JSONField(default=dict, blank=True, help_text='Snapshot effect handlers can restore on reversal.')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_DRAFT, db_index=True)
    workflow_instance = models.ForeignKey(
        'platform_core.WorkflowInstance', on_delete=models.SET_NULL, null=True, blank=True, related_name='employment_actions',
    )
    applied_at = models.DateTimeField(null=True, blank=True)
    applied_by = models.ForeignKey('accounts.User', on_delete=models.SET_NULL, null=True, blank=True, related_name='+')
    reversal_of = models.ForeignKey('self', on_delete=models.SET_NULL, null=True, blank=True, related_name='reversed_by')
    reference_number = models.CharField(max_length=30, blank=True)
    created_by = models.ForeignKey('accounts.User', on_delete=models.SET_NULL, null=True, blank=True, related_name='+')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'hrms_employment_actions'
        ordering = ['-effective_date', '-created_at']
        indexes = [models.Index(fields=['employee', 'effective_date'])]

    def __str__(self):
        return f'{self.action_type_id} for {self.employee_id} on {self.effective_date}'
