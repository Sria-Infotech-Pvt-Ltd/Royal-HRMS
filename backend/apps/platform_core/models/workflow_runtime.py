"""Phase 3B Task B — workflow runtime state: instances, tasks, and the
append-only history log."""
from __future__ import annotations

import uuid

from django.conf import settings
from django.db import models

from .phase1 import LegalEntity, TimestampedModel
from .workflow import WorkflowDefinition, WorkflowStep


class WorkflowInstance(TimestampedModel):
    STATUS_IN_PROGRESS = 'in_progress'
    STATUS_APPROVED = 'approved'
    STATUS_REJECTED = 'rejected'
    STATUS_WITHDRAWN = 'withdrawn'
    STATUS_CANCELLED = 'cancelled'
    STATUS_ERROR = 'error'
    STATUS_CHOICES = [
        (STATUS_IN_PROGRESS, 'In progress'), (STATUS_APPROVED, 'Approved'), (STATUS_REJECTED, 'Rejected'),
        (STATUS_WITHDRAWN, 'Withdrawn'), (STATUS_CANCELLED, 'Cancelled'), (STATUS_ERROR, 'Error'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    definition = models.ForeignKey(WorkflowDefinition, on_delete=models.PROTECT, related_name='instances')
    definition_version = models.PositiveIntegerField(help_text='Pinned at start — Task A.1\'s "in-flight instances always continue on the version they started with."')

    content_type = models.ForeignKey('contenttypes.ContentType', on_delete=models.CASCADE, related_name='+')
    object_id = models.CharField(max_length=64)

    requester = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='+')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_IN_PROGRESS)
    current_step_codes = models.JSONField(default=list, blank=True, help_text='Usually one; more than one while inside a parallel_group.')

    legal_entity = models.ForeignKey(LegalEntity, on_delete=models.SET_NULL, null=True, blank=True, related_name='+')
    started_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = 'platform_workflow_instances'
        ordering = ['-started_at']
        indexes = [models.Index(fields=['content_type', 'object_id'], name='pwi_object_idx')]

    def __str__(self):
        return f'{self.definition_id}:{self.object_id} ({self.status})'


class WorkflowTask(TimestampedModel):
    STATUS_PENDING = 'pending'
    STATUS_APPROVED = 'approved'
    STATUS_REJECTED = 'rejected'
    STATUS_SENT_BACK = 'sent_back'
    STATUS_INFO_REQUESTED = 'info_requested'
    STATUS_DELEGATED = 'delegated'
    STATUS_REASSIGNED = 'reassigned'
    STATUS_WITHDRAWN = 'withdrawn'
    STATUS_EXPIRED = 'expired'
    STATUS_CHOICES = [
        (STATUS_PENDING, 'Pending'), (STATUS_APPROVED, 'Approved'), (STATUS_REJECTED, 'Rejected'),
        (STATUS_SENT_BACK, 'Sent back'), (STATUS_INFO_REQUESTED, 'Info requested'),
        (STATUS_DELEGATED, 'Delegated'), (STATUS_REASSIGNED, 'Reassigned'),
        (STATUS_WITHDRAWN, 'Withdrawn'), (STATUS_EXPIRED, 'Expired'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    instance = models.ForeignKey(WorkflowInstance, on_delete=models.CASCADE, related_name='tasks')
    step = models.ForeignKey(WorkflowStep, on_delete=models.PROTECT, related_name='+')

    assignee = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='workflow_tasks')
    original_assignee = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='+')

    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_PENDING)
    due_at = models.DateTimeField(null=True, blank=True)
    escalation_level = models.PositiveIntegerField(default=0)

    acted_at = models.DateTimeField(null=True, blank=True)
    action = models.CharField(max_length=30, blank=True)
    remarks = models.TextField(blank=True)
    acted_on_behalf_of = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='+')

    # Idempotency: a client-supplied key so "an action submitted twice is
    # applied once" (Task B.2) is enforced even across network retries,
    # not just same-process double-clicks (which row-level locking in
    # services_workflow.act() already covers).
    idempotency_key = models.CharField(max_length=100, blank=True, db_index=True)

    class Meta:
        db_table = 'platform_workflow_tasks'
        ordering = ['-created_at']
        indexes = [models.Index(fields=['assignee', 'status'], name='pwt_assignee_status_idx')]

    def __str__(self):
        return f'{self.instance_id}:{self.step_id} -> {self.assignee_id} ({self.status})'


class WorkflowHistory(models.Model):
    """Append-only — same enforcement pattern as Phase 1's ChangeHistory
    (save()/delete() raise on update/delete)."""
    ACTION_STARTED = 'started'
    ACTION_TASK_CREATED = 'task_created'
    ACTION_APPROVED = 'approved'
    ACTION_REJECTED = 'rejected'
    ACTION_SENT_BACK = 'sent_back'
    ACTION_INFO_REQUESTED = 'info_requested'
    ACTION_DELEGATED = 'delegated'
    ACTION_REASSIGNED = 'reassigned'
    ACTION_WITHDRAWN = 'withdrawn'
    ACTION_CANCELLED = 'cancelled'
    ACTION_ESCALATED = 'escalated'
    ACTION_AUTO_ACTIONED = 'auto_actioned'
    ACTION_COMPLETED = 'completed'
    ACTION_CHOICES = [
        (ACTION_STARTED, 'Started'), (ACTION_TASK_CREATED, 'Task created'), (ACTION_APPROVED, 'Approved'),
        (ACTION_REJECTED, 'Rejected'), (ACTION_SENT_BACK, 'Sent back'), (ACTION_INFO_REQUESTED, 'Info requested'),
        (ACTION_DELEGATED, 'Delegated'), (ACTION_REASSIGNED, 'Reassigned'), (ACTION_WITHDRAWN, 'Withdrawn'),
        (ACTION_CANCELLED, 'Cancelled'), (ACTION_ESCALATED, 'Escalated'), (ACTION_AUTO_ACTIONED, 'Auto-actioned'),
        (ACTION_COMPLETED, 'Completed'),
    ]

    instance = models.ForeignKey(WorkflowInstance, on_delete=models.CASCADE, related_name='history')
    task = models.ForeignKey(WorkflowTask, on_delete=models.SET_NULL, null=True, blank=True, related_name='+')
    action = models.CharField(max_length=30, choices=ACTION_CHOICES)
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='+')
    remarks = models.TextField(blank=True)
    occurred_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'platform_workflow_history'
        ordering = ['occurred_at']

    def __str__(self):
        return f'{self.instance_id}:{self.action}'

    def save(self, *args, **kwargs):
        if self.pk is not None:
            raise ValueError('WorkflowHistory is append-only — it cannot be updated.')
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValueError('WorkflowHistory is append-only — it cannot be deleted.')
