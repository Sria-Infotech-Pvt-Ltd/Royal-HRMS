"""Phase 3B Task G.4 — the 3 new job types' actual callables."""
from __future__ import annotations

from django.utils import timezone


def process_workflow_sla(**params) -> dict:
    """Task B.5 — escalation and reminders, processed idempotently every
    few minutes. Reminder sends are routed through services_notifications
    (not a direct email call) so they're subject to the same mute/dedup
    rules as everything else."""
    from apps.platform_core import services_events as events
    from apps.platform_core.models import WorkflowTask

    now = timezone.now()
    overdue_tasks = WorkflowTask.objects.filter(status=WorkflowTask.STATUS_PENDING, due_at__lt=now)
    escalated = 0
    for task in overdue_tasks:
        step = task.step
        if step.sla_escalation_after_hours and task.escalation_level == 0:
            events.emit('workflow.task.overdue', {'task_id': str(task.pk), 'instance_id': str(task.instance_id)}, actor=task.assignee)
            task.escalation_level += 1
            task.save(update_fields=['escalation_level'])
            escalated += 1
    return {'overdue_found': overdue_tasks.count(), 'escalated': escalated}


def drain_event_outbox(**params) -> dict:
    from apps.platform_core import services_events as events
    return events.drain_outbox(limit=params.get('limit', 100))


def send_notification_digests(**params) -> dict:
    """Task F.2's digest option — NOT fully implemented in this phase
    (would need to batch pending digest-mode NotificationRule matches
    per user per day, which needs a staging table this phase didn't
    build). Returns a zero-count result rather than silently pretending
    to have sent anything — see PHASE3B_REPORT.md."""
    return {'sent': 0, 'note': 'Digest batching not implemented in this phase.'}
