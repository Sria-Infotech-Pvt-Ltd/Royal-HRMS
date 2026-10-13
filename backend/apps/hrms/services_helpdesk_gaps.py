"""Phase 8B gap-closure — knowledge-base keyword suggestions, satisfaction rating, ticket merge, round-robin assignment."""
from django.db import transaction

from apps.hrms.models import (
    HelpDeskCategory, HRHelpRequest, KnowledgeBaseArticle, RoundRobinAssignmentState,
    TicketMergeRecord, TicketSatisfactionRating,
)


def suggest_articles(subject: str, limit: int = 5) -> list:
    """Simple keyword match — no external AI service, per the master
    prompt's own instruction. Splits the subject into words and finds
    articles whose title OR body contains any of them."""
    words = [w.strip().lower() for w in subject.split() if len(w.strip()) > 2]
    if not words:
        return []
    from django.db.models import Q
    query = Q()
    for word in words:
        query |= Q(title__icontains=word) | Q(body__icontains=word)
    return list(KnowledgeBaseArticle.objects.filter(query, is_active=True)[:limit])


def record_satisfaction(ticket: HRHelpRequest, rating: int, comments: str = '') -> TicketSatisfactionRating:
    if ticket.status != 'resolved':
        raise ValueError('Can only rate a resolved ticket.')
    return TicketSatisfactionRating.objects.create(ticket=ticket, rating=rating, comments=comments)


@transaction.atomic
def merge_tickets(primary: HRHelpRequest, duplicate: HRHelpRequest, merged_by) -> TicketMergeRecord:
    if primary.id == duplicate.id:
        raise ValueError('Cannot merge a ticket into itself.')
    from apps.hrms.services_helpdesk_v2 import migrate_ticket_to_thread
    primary_thread = migrate_ticket_to_thread(primary)
    duplicate_thread = migrate_ticket_to_thread(duplicate)
    duplicate_thread.messages.update(thread=primary_thread)
    duplicate.status = 'resolved'
    duplicate.save(update_fields=['status'])
    return TicketMergeRecord.objects.create(primary_ticket=primary, merged_ticket=duplicate, merged_by=merged_by)


def assign_round_robin(category: HelpDeskCategory, agents: list):
    """`agents` is the caller-supplied ordered agent list for this
    category (group membership resolution is a separate, real concern —
    this function only advances the rotation pointer and returns who's
    next)."""
    if not agents:
        raise ValueError('No agents available for round-robin assignment.')
    state, _ = RoundRobinAssignmentState.objects.get_or_create(category=category)
    next_index = (state.last_assigned_index + 1) % len(agents)
    state.last_assigned_index = next_index
    state.save(update_fields=['last_assigned_index'])
    return agents[next_index]
