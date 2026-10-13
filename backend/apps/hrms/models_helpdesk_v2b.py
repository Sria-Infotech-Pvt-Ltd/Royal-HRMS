"""Phase 8B gap-closure — knowledge base, satisfaction rating, ticket merge, round-robin assignment."""
import uuid

from django.db import models


class KnowledgeBaseArticle(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    category = models.ForeignKey('hrms.HelpDeskCategory', on_delete=models.SET_NULL, null=True, blank=True, related_name='articles')
    title = models.CharField(max_length=200)
    body = models.TextField()
    version = models.PositiveSmallIntegerField(default=1)
    is_active = models.BooleanField(default=True)
    helpful_count = models.PositiveIntegerField(default=0)
    not_helpful_count = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'hrms_kb_articles_v2'
        ordering = ['title']

    def __str__(self):
        return self.title


class TicketSatisfactionRating(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    ticket = models.OneToOneField('hrms.HRHelpRequest', on_delete=models.CASCADE, related_name='satisfaction_rating')
    # Reuses the Phase 8A 1-5 rating scale convention rather than a new vocabulary.
    rating = models.PositiveSmallIntegerField(choices=[(1, '1'), (2, '2'), (3, '3'), (4, '4'), (5, '5')])
    comments = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'hrms_ticket_satisfaction_ratings_v2'

    def __str__(self):
        return f'{self.ticket_id}: {self.rating}/5'


class TicketMergeRecord(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    primary_ticket = models.ForeignKey('hrms.HRHelpRequest', on_delete=models.CASCADE, related_name='absorbed_tickets')
    merged_ticket = models.OneToOneField('hrms.HRHelpRequest', on_delete=models.CASCADE, related_name='merge_record')
    merged_by = models.ForeignKey('accounts.User', on_delete=models.SET_NULL, null=True, blank=True, related_name='ticket_merges_performed')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'hrms_ticket_merge_records_v2'

    def __str__(self):
        return f'{self.merged_ticket_id} -> {self.primary_ticket_id}'


class RoundRobinAssignmentState(models.Model):
    """One row per category — `last_assigned_index` into a caller-supplied
    agent list, so round-robin is stateful/deterministic across calls."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    category = models.OneToOneField('hrms.HelpDeskCategory', on_delete=models.CASCADE, related_name='rotation_state')
    last_assigned_index = models.SmallIntegerField(default=-1, help_text='-1 = nobody assigned yet (not a PositiveSmallIntegerField — that rejects -1).')

    class Meta:
        db_table = 'hrms_helpdesk_round_robin_state_v2'

    def __str__(self):
        return f'{self.category_id}: last={self.last_assigned_index}'
