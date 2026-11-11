"""
Approval escalation and delegation, shared by the leave and attendance
(correction / late-justification) approval chains.

ApprovalEscalationSettings  per company (one row per tenant schema): reminder
                            and escalation timings in working days. Off by
                            default — a company switches it on.
ApprovalEscalation          append-only log of reminders / escalations; the
                            unique key (kind, request, stage, level) is what
                            stops a step happening twice.
ApprovalDelegation          an approver hands their approvals to a colleague
                            for a date range; kept after revocation for audit.
"""
from __future__ import annotations

import uuid

from django.conf import settings
from django.db import models


KIND_LEAVE = 'leave'
KIND_ATTENDANCE = 'attendance'
KIND_CHOICES = [(KIND_LEAVE, 'Leave'), (KIND_ATTENDANCE, 'Attendance requests')]


class ApprovalEscalationSettings(models.Model):
    is_enabled = models.BooleanField(default=False)
    # Working days the request has waited at its current stage.
    reminder_after_days = models.PositiveSmallIntegerField(default=1)
    first_escalation_after_days = models.PositiveSmallIntegerField(default=2)
    # Additional working days after the first escalation.
    second_escalation_after_days = models.PositiveSmallIntegerField(default=3)
    # Second escalation target (e.g. HR Head / Admin Head). Empty = no second level.
    escalation_head = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
                                        related_name='+')
    applies_to_leave = models.BooleanField(default=True)
    applies_to_attendance = models.BooleanField(default=True)
    updated_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
                                   related_name='+')
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'approvals_escalation_settings'

    @classmethod
    def current(cls) -> 'ApprovalEscalationSettings':
        """The company's row, or the defaults (unsaved) when never configured."""
        return cls.objects.select_related('escalation_head').first() or cls()

    def applies_to(self, kind: str) -> bool:
        return self.applies_to_leave if kind == KIND_LEAVE else self.applies_to_attendance


class ApprovalEscalation(models.Model):
    ACTION_REMINDER = 'reminder'
    ACTION_ESCALATED = 'escalated'
    ACTION_SKIPPED = 'skipped'
    ACTION_CHOICES = [(ACTION_REMINDER, 'Reminder sent'), (ACTION_ESCALATED, 'Escalated'),
                      (ACTION_SKIPPED, 'Skipped (no one to escalate to)')]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    kind = models.CharField(max_length=20, choices=KIND_CHOICES)
    request_id = models.UUIDField()
    stage = models.CharField(max_length=2)            # 'l1' | 'l2'
    level = models.PositiveSmallIntegerField()        # 0 reminder, 1 first, 2 second escalation
    action = models.CharField(max_length=12, choices=ACTION_CHOICES)
    target = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
                               related_name='approval_escalations')
    working_days_waited = models.PositiveSmallIntegerField(default=0)
    note = models.CharField(max_length=300, blank=True, default='')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'approvals_escalation_log'
        ordering = ['-created_at']
        constraints = [models.UniqueConstraint(fields=['kind', 'request_id', 'stage', 'level'],
                                               name='uniq_escalation_step')]
        indexes = [models.Index(fields=['target', 'kind', 'action'], name='esc_target_idx')]


class ApprovalDelegation(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    delegator = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='delegations_given')
    delegate = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='delegations_received')
    start_date = models.DateField()
    end_date = models.DateField()
    workflows = models.JSONField(default=list)        # ['leave', 'attendance']
    reason = models.CharField(max_length=300, blank=True, default='')
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name='+')
    created_at = models.DateTimeField(auto_now_add=True)
    revoked_at = models.DateTimeField(null=True, blank=True)
    revoked_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
                                   related_name='+')

    class Meta:
        db_table = 'approvals_delegation'
        ordering = ['-start_date', '-created_at']
        indexes = [models.Index(fields=['delegate', 'start_date', 'end_date'], name='deleg_delegate_idx')]

    def is_active_on(self, day) -> bool:
        return self.revoked_at is None and self.start_date <= day <= self.end_date
