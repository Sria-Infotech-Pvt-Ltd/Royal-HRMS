"""
Phase 9B Task E — privacy: a real Data Subject Request (DSR) record and
an audit trail of what was done to fulfil it.

Scoped down, stated plainly: this builds the DSR intake + fulfilment-
tracking MECHANISM (one model, one status lifecycle, one evidence log)
and wires it to the ANONYMISATION logic that already exists for
candidates (apps.recruitment.services_recruitment_gaps.anonymise_candidate,
Phase 8A/8B gap-closure) and to a plain data-export reader across a
small, explicitly-named set of employee-linked tables. It does NOT
attempt a repo-wide "find every PII field automatically" scanner — that
is separate, larger scope and is named here as deferred, not silently
skipped.
"""
import uuid

from django.conf import settings
from django.db import models


class DataSubjectRequest(models.Model):
    TYPE_ACCESS = 'access'
    TYPE_EXPORT = 'export'
    TYPE_ERASURE = 'erasure'
    TYPE_CHOICES = [
        (TYPE_ACCESS, 'Access'), (TYPE_EXPORT, 'Export'), (TYPE_ERASURE, 'Erasure'),
    ]

    STATUS_OPEN = 'open'
    STATUS_IN_PROGRESS = 'in_progress'
    STATUS_FULFILLED = 'fulfilled'
    STATUS_REJECTED = 'rejected'
    STATUS_CHOICES = [
        (STATUS_OPEN, 'Open'), (STATUS_IN_PROGRESS, 'In progress'),
        (STATUS_FULFILLED, 'Fulfilled'), (STATUS_REJECTED, 'Rejected'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    request_type = models.CharField(max_length=10, choices=TYPE_CHOICES)
    subject_user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='data_subject_requests',
    )
    requested_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='data_subject_requests_filed',
    )
    status = models.CharField(max_length=15, choices=STATUS_CHOICES, default=STATUS_OPEN)
    reason = models.TextField(blank=True)
    rejection_reason = models.TextField(blank=True)
    fulfilment_evidence = models.JSONField(default=dict, blank=True)
    fulfilled_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='data_subject_requests_fulfilled',
    )
    fulfilled_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'platform_data_subject_requests_v2'
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.request_type} DSR for {self.subject_user_id} ({self.status})'
