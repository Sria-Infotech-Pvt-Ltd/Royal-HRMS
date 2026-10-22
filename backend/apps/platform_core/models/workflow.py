"""
Phase 3B Task A — workflow DEFINITIONS (the design-time graph an admin
builds). Runtime state (instances/tasks/history) is in
models/workflow_runtime.py — split purely to respect this project's
~300-line file guideline.
"""
from __future__ import annotations

from django.conf import settings
from django.core.serializers.json import DjangoJSONEncoder
from django.db import models

from .fields import EntityDefinition
from .phase1 import LegalEntity, TimestampedModel


class WorkflowDefinition(TimestampedModel):
    TRIGGER_ON_SUBMIT = 'on_submit'
    TRIGGER_ON_CREATE = 'on_create'
    TRIGGER_ON_FIELD_CHANGE = 'on_field_change'
    TRIGGER_MANUAL = 'manual'
    TRIGGER_CHOICES = [
        (TRIGGER_ON_SUBMIT, 'On submit'), (TRIGGER_ON_CREATE, 'On create'),
        (TRIGGER_ON_FIELD_CHANGE, 'On field change'), (TRIGGER_MANUAL, 'Manual'),
    ]

    STATUS_DRAFT = 'draft'
    STATUS_PUBLISHED = 'published'
    STATUS_RETIRED = 'retired'
    STATUS_CHOICES = [(STATUS_DRAFT, 'Draft'), (STATUS_PUBLISHED, 'Published'), (STATUS_RETIRED, 'Retired')]

    code = models.CharField(max_length=100, unique=True)
    name = models.CharField(max_length=150)
    entity = models.ForeignKey(EntityDefinition, on_delete=models.CASCADE, related_name='workflow_definitions')

    trigger = models.CharField(max_length=20, choices=TRIGGER_CHOICES, default=TRIGGER_ON_SUBMIT)
    trigger_fields = models.JSONField(default=list, blank=True, help_text='Field codes — only for trigger=on_field_change.')
    entry_condition = models.JSONField(default=dict, blank=True, help_text='Rule expression (services_rules format); empty = always matches.')
    priority = models.PositiveIntegerField(default=0, help_text='Highest priority with a true entry_condition wins among matching definitions for the same entity.')

    legal_entity = models.ForeignKey(LegalEntity, on_delete=models.SET_NULL, null=True, blank=True, related_name='+')

    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_DRAFT)
    version = models.PositiveIntegerField(default=1)
    effective_from = models.DateField(null=True, blank=True)

    # Declared mapping workflow-status -> record-status lookup code, so
    # the engine can update the record's own status field without each
    # entity hardcoding engine knowledge (Task B.2's "declared mapping").
    status_field_code = models.CharField(max_length=64, blank=True, help_text='Record field code the engine writes a status lookup code into, if any.')
    status_mapping = models.JSONField(default=dict, blank=True, help_text='{"approved": "APPROVED", "rejected": "REJECTED", ...}')

    class Meta:
        db_table = 'platform_workflow_definitions'
        ordering = ['entity', '-priority']

    def __str__(self):
        return f'{self.code} v{self.version}'


class WorkflowStep(TimestampedModel):
    TYPE_APPROVAL = 'approval'
    TYPE_REVIEW = 'review'
    TYPE_NOTIFICATION_ONLY = 'notification_only'
    TYPE_SYSTEM_ACTION = 'system_action'
    TYPE_CONDITION_BRANCH = 'condition_branch'
    TYPE_PARALLEL_GROUP = 'parallel_group'
    TYPE_CHOICES = [
        (TYPE_APPROVAL, 'Approval'), (TYPE_REVIEW, 'Review (acknowledge only)'),
        (TYPE_NOTIFICATION_ONLY, 'Notification only'), (TYPE_SYSTEM_ACTION, 'System action'),
        (TYPE_CONDITION_BRANCH, 'Condition branch'), (TYPE_PARALLEL_GROUP, 'Parallel group'),
    ]

    QUORUM_ANY_ONE = 'any_one'
    QUORUM_ALL = 'all'
    QUORUM_N_OF_M = 'n_of_m'
    QUORUM_CHOICES = [(QUORUM_ANY_ONE, 'Any one'), (QUORUM_ALL, 'All'), (QUORUM_N_OF_M, 'N of M')]

    NO_APPROVER_FALLBACK_POSITION = 'fallback_position'
    NO_APPROVER_SKIP = 'skip'
    NO_APPROVER_BLOCK = 'block_and_alert'
    NO_APPROVER_CHOICES = [
        (NO_APPROVER_FALLBACK_POSITION, 'Fall back to a position'), (NO_APPROVER_SKIP, 'Skip this step'),
        (NO_APPROVER_BLOCK, 'Block and alert admin'),
    ]

    definition = models.ForeignKey(WorkflowDefinition, on_delete=models.CASCADE, related_name='steps')
    code = models.CharField(max_length=64, help_text='Unique within the definition — used for send-back-to-step and status_mapping targets.')
    label = models.CharField(max_length=150)
    order = models.PositiveIntegerField(default=0)
    step_type = models.CharField(max_length=30, choices=TYPE_CHOICES, default=TYPE_APPROVAL)

    # Approver resolution — see approver_resolvers.py's registry. `resolver`
    # names a registered function; `resolver_params` is whatever that
    # resolver needs (role code, level N, field code, rule code, etc.).
    resolver = models.CharField(max_length=50, blank=True)
    # encoder=DjangoJSONEncoder — resolver_params routinely holds a raw
    # user/position/role pk (e.g. {"user_id": ...}), and every pk in this
    # codebase is a UUID (CLAUDE.md §7: "Primary keys are always
    # UUIDField"), which plain JSONField's default encoder cannot
    # serialize. Same bug class as ChangeHistory.changes (Phase 1,
    # fixed in migration 0011) — caught here before it ever shipped.
    resolver_params = models.JSONField(default=dict, blank=True, encoder=DjangoJSONEncoder)
    quorum = models.CharField(max_length=20, choices=QUORUM_CHOICES, default=QUORUM_ANY_ONE)
    quorum_n = models.PositiveIntegerField(null=True, blank=True, help_text='Only for quorum=n_of_m.')

    skip_if_approver_is_requester = models.BooleanField(default=True)
    skip_if_same_as_previous_step = models.BooleanField(default=True)
    skip_condition = models.JSONField(default=dict, blank=True)
    auto_approve_condition = models.JSONField(default=dict, blank=True)
    no_approver_action = models.CharField(max_length=20, choices=NO_APPROVER_CHOICES, default=NO_APPROVER_BLOCK)
    no_approver_fallback_position = models.ForeignKey('accounts.Position', on_delete=models.SET_NULL, null=True, blank=True, related_name='+')

    # condition_branch only: rule expression -> next WorkflowStep.code
    branch_condition = models.JSONField(default=dict, blank=True)
    branch_next_step_code_if_true = models.CharField(max_length=64, blank=True)
    branch_next_step_code_if_false = models.CharField(max_length=64, blank=True)

    require_remarks = models.BooleanField(default=False)
    editable_field_codes = models.JSONField(default=list, blank=True)

    # SLA
    sla_due_in_hours = models.PositiveIntegerField(null=True, blank=True)
    sla_business_hours_only = models.BooleanField(default=False)
    sla_reminder_hours = models.JSONField(default=list, blank=True, help_text='Hours-before-due to send a reminder, e.g. [24, 4].')
    sla_escalation_after_hours = models.PositiveIntegerField(null=True, blank=True)
    sla_escalation_resolver = models.CharField(max_length=50, blank=True)
    sla_escalation_resolver_params = models.JSONField(default=dict, blank=True, encoder=DjangoJSONEncoder)
    sla_timeout_action = models.CharField(max_length=20, blank=True, choices=[('approve', 'Auto-approve'), ('reject', 'Auto-reject'), ('', 'None')])

    class Meta:
        db_table = 'platform_workflow_steps'
        ordering = ['definition', 'order']
        constraints = [
            models.UniqueConstraint(fields=['definition', 'code'], name='uniq_workflow_step_code_per_definition'),
        ]

    def __str__(self):
        return f'{self.definition_id}:{self.code}'


class WorkflowApproverOverride(TimestampedModel):
    """Task A.4 — generalises EmployeeApprovalOverride beyond the 4 fixed
    legacy workflow types to any (definition, step)."""
    employee = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='workflow_approver_overrides')
    definition = models.ForeignKey(WorkflowDefinition, on_delete=models.CASCADE, related_name='approver_overrides')
    step_code = models.CharField(max_length=64)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='+')
    effective_from = models.DateField()
    effective_to = models.DateField(null=True, blank=True)

    class Meta:
        db_table = 'platform_workflow_approver_overrides'
        ordering = ['employee', 'definition', 'step_code']

    def __str__(self):
        return f'{self.employee_id}:{self.definition_id}:{self.step_code} -> {self.user_id}'


class Delegation(TimestampedModel):
    """Task B.3. `scope_entities` empty list = all entities."""
    from_user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='delegations_given')
    to_user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='delegations_received')
    scope_entities = models.JSONField(default=list, blank=True, help_text='EntityDefinition codes; empty = all.')
    start = models.DateField()
    end = models.DateField(null=True, blank=True)
    reason = models.CharField(max_length=255, blank=True)
    apply_to_already_open_tasks = models.BooleanField(default=False)

    class Meta:
        db_table = 'platform_delegations'
        ordering = ['-start']

    def __str__(self):
        return f'{self.from_user_id} -> {self.to_user_id} ({self.start}..{self.end or "open"})'

    def covers(self, as_of, entity_code: str | None) -> bool:
        if self.start > as_of or (self.end and self.end < as_of):
            return False
        if self.scope_entities and entity_code not in self.scope_entities:
            return False
        return True
