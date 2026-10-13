"""
Phase 8B Task C — HR help desk conversation thread + categories with SLA.
`HRHelpRequest` itself is untouched; `response` stays populated (migrated
as the first TicketMessage — see services_helpdesk_v2).

Scoped down: no round-robin assignment resolver, no knowledge-base
articles/suggestions, no satisfaction rating, no merge-duplicates. SLA is
a plain hour count from ticket creation (`sla_breach_at`), not calendar-
aware business hours from a 6A calendar — stated plainly as a
simplification, not a silent approximation.
"""
import uuid

from django.db import models


class HelpDeskCategory(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    code = models.CharField(max_length=40, unique=True)
    name = models.CharField(max_length=100)
    parent = models.ForeignKey('self', on_delete=models.SET_NULL, null=True, blank=True, related_name='children')
    default_priority = models.CharField(max_length=10, default='normal')
    sla_first_response_hours = models.PositiveSmallIntegerField(null=True, blank=True)
    sla_resolution_hours = models.PositiveSmallIntegerField(null=True, blank=True)
    is_confidential = models.BooleanField(default=False, help_text='e.g. grievances/POSH — visible only to designated roles (view-layer enforced, not by this model).')
    legacy_topic_code = models.CharField(max_length=40, blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        db_table = 'hrms_helpdesk_categories_v2'
        ordering = ['code']

    def __str__(self):
        return self.code


class TicketThread(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    ticket = models.OneToOneField('hrms.HRHelpRequest', on_delete=models.CASCADE, related_name='thread_v2')
    category = models.ForeignKey(HelpDeskCategory, on_delete=models.SET_NULL, null=True, blank=True, related_name='tickets')
    first_response_at = models.DateTimeField(null=True, blank=True)
    sla_breach_at = models.DateTimeField(null=True, blank=True)
    sla_breached = models.BooleanField(default=False)
    reopened_count = models.PositiveSmallIntegerField(default=0)

    class Meta:
        db_table = 'hrms_ticket_threads_v2'

    def __str__(self):
        return f'Thread for {self.ticket_id}'


class TicketMessage(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    thread = models.ForeignKey(TicketThread, on_delete=models.CASCADE, related_name='messages')
    author = models.ForeignKey('accounts.User', on_delete=models.SET_NULL, null=True, blank=True, related_name='helpdesk_messages')
    body = models.TextField()
    is_internal_note = models.BooleanField(default=False)
    is_legacy_migrated = models.BooleanField(default=False, help_text='True for the one message created from the old HRHelpRequest.response field.')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'hrms_ticket_messages_v2'
        ordering = ['created_at']

    def __str__(self):
        return f'{self.thread_id}: {self.body[:40]}'
