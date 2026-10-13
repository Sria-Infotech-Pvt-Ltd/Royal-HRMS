"""Phase 8B Task C — ticket thread migration, SLA breach checking, reopen."""
import datetime

from django.db import transaction
from django.utils import timezone

from apps.hrms.models import HelpDeskCategory, HR_HELP_TOPIC_CHOICES, HRHelpRequest, TicketMessage, TicketThread


def seed_helpdesk_categories() -> dict:
    """Idempotent. Reproduces HR_HELP_TOPIC_CHOICES exactly."""
    created = {}
    for code, name in HR_HELP_TOPIC_CHOICES:
        category, _ = HelpDeskCategory.objects.get_or_create(
            legacy_topic_code=code, defaults={'code': code, 'name': name},
        )
        created[code] = category
    return created


@transaction.atomic
def migrate_ticket_to_thread(ticket: HRHelpRequest) -> TicketThread:
    """Idempotent. The old `response` (if any) becomes the first
    TicketMessage, exactly once."""
    existing = getattr(ticket, 'thread_v2', None)
    if existing is not None:
        return existing

    categories = seed_helpdesk_categories()
    category = categories.get(ticket.topic)
    thread = TicketThread.objects.create(ticket=ticket, category=category)

    if ticket.response:
        TicketMessage.objects.create(
            thread=thread, author=ticket.assigned_to, body=ticket.response, is_legacy_migrated=True,
        )
    return thread


def compute_sla_breach_at(thread: TicketThread, created_at) -> datetime.datetime | None:
    if thread.category is None or thread.category.sla_resolution_hours is None:
        return None
    return created_at + datetime.timedelta(hours=thread.category.sla_resolution_hours)


def check_sla_breach(thread: TicketThread) -> bool:
    if thread.sla_breach_at is None or thread.ticket.status == 'resolved':
        return False
    breached = timezone.now() > thread.sla_breach_at
    if breached and not thread.sla_breached:
        thread.sla_breached = True
        thread.save(update_fields=['sla_breached'])
    return breached


def reopen_ticket(ticket: HRHelpRequest, within_days: int = 7) -> bool:
    """True if reopened (resolved within `within_days`), False if the
    reopen window has passed — caller decides what to do in that case."""
    if ticket.status != 'resolved' or ticket.resolved_at is None:
        return False
    if (timezone.now() - ticket.resolved_at).days > within_days:
        return False

    ticket.status = 'in_progress'
    ticket.resolved_at = None
    ticket.save(update_fields=['status', 'resolved_at'])

    thread = migrate_ticket_to_thread(ticket)
    thread.reopened_count += 1
    thread.save(update_fields=['reopened_count'])
    return True
