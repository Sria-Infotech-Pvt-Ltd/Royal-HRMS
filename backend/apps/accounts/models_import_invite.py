"""
One activation invitation owed to one employee created by a bulk import.

This table is the durable to-do list for the invitation emails: it is written in the SAME transaction as the employees, so an
invitation is owed if and only if the employee exists, and it survives a closed browser, a restarted web server or worker, and an
unreachable Redis. Celery tasks (apps.accounts.tasks) work through it.

What it deliberately does NOT hold: the activation token (the existing PasswordResetToken row is the only place a token lives),
the email address, or any other personal data. Only a status, counters and a short reason code.

Delivery is AT-LEAST-ONCE, never claimed to be exactly-once: if a worker dies after the mail server accepted a message but before
that was recorded, the retry may send one more email. Such cases are counted in `ambiguous_attempts`. Sending a new invitation
replaces the previous activation link, so only the newest link ever works.
"""
from __future__ import annotations

import uuid

from django.db import models
from django.db.models import Q

STATUS_PENDING = 'pending'
STATUS_PROCESSING = 'processing'
STATUS_SENT = 'sent'
STATUS_FAILED = 'failed'
STATUS_SKIPPED = 'skipped'
OPEN_STATUSES = (STATUS_PENDING, STATUS_PROCESSING)


class EmployeeImportInvite(models.Model):
    STATUS_CHOICES = [
        (STATUS_PENDING, 'Pending'), (STATUS_PROCESSING, 'Processing'), (STATUS_SENT, 'Sent'),
        (STATUS_FAILED, 'Failed'), (STATUS_SKIPPED, 'Skipped'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    batch_id = models.UUIDField(db_index=True)
    user = models.ForeignKey('accounts.User', on_delete=models.CASCADE, related_name='import_invites')
    created_by = models.ForeignKey('accounts.User', on_delete=models.SET_NULL, null=True, blank=True, related_name='+')
    row_number = models.PositiveIntegerField(default=0)
    status = models.CharField(max_length=12, choices=STATUS_CHOICES, default=STATUS_PENDING)
    attempts = models.PositiveSmallIntegerField(default=0)
    ambiguous_attempts = models.PositiveSmallIntegerField(default=0)
    reason_code = models.CharField(max_length=40, blank=True)
    next_attempt_at = models.DateTimeField(null=True, blank=True)
    processing_started_at = models.DateTimeField(null=True, blank=True)
    sent_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'hrms_employee_import_invites'
        ordering = ['row_number']
        constraints = [
            models.UniqueConstraint(fields=['batch_id', 'user'], name='uniq_import_invite_per_batch_user'),
            # Across ALL batches an employee can have at most one invitation that is still waiting or being sent.
            models.UniqueConstraint(fields=['user'], condition=Q(status__in=OPEN_STATUSES), name='uniq_open_import_invite_per_user'),
        ]
        indexes = [models.Index(fields=['batch_id', 'status'], name='import_invite_batch_status_idx'),
                   models.Index(fields=['status', 'updated_at'], name='import_invite_status_age_idx')]

    def __str__(self) -> str:
        return f'import invite {self.id} ({self.status})'
