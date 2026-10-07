"""
Phase 3B Task E.1 — event types registered in code, synced via
`sync_event_types` (idempotent, same get_or_create convention as
sync_entity_registry/sync_policy_types), also run on post_migrate.

Custom-object events (created/updated/status_changed) are generated
automatically per published custom entity by `sync_custom_entity_events()`
— called from the same places `services_custom_objects.publish_entity()`
already runs, so publishing a custom entity always gets its 3 events
without a manual step.
"""
from __future__ import annotations

CORE_EVENT_TYPES = [
    {'code': 'leave.submitted', 'module': 'hrms', 'description': 'A leave request was submitted.'},
    {'code': 'leave.approved', 'module': 'hrms', 'description': 'A leave request was approved.'},
    {'code': 'leave.rejected', 'module': 'hrms', 'description': 'A leave request was rejected.'},
    {'code': 'workflow.task.assigned', 'module': 'platform_core', 'description': 'A workflow task was assigned to a user.'},
    {'code': 'workflow.task.overdue', 'module': 'platform_core', 'description': 'A workflow task passed its SLA due date.'},
    {'code': 'workflow.approved', 'module': 'platform_core', 'description': 'A workflow instance completed approved.'},
    {'code': 'workflow.rejected', 'module': 'platform_core', 'description': 'A workflow instance completed rejected.'},
    {'code': 'employee.joined', 'module': 'accounts', 'description': 'An employee\'s joining date arrived.'},
    {'code': 'employee.birthday', 'module': 'accounts', 'description': 'An employee\'s birthday.'},
    {'code': 'employee.work_anniversary', 'module': 'accounts', 'description': 'An employee\'s work anniversary.'},
    {'code': 'document.expiring', 'module': 'accounts', 'description': 'A document is expiring soon.'},
    {'code': 'attendance.absent_streak', 'module': 'attendance', 'description': 'An employee has an absence streak.'},
    {'code': 'attendance.missing_clockout', 'module': 'attendance', 'description': 'A missing clock-out was detected.'},
    {'code': 'payroll.approval_pending', 'module': 'payroll', 'description': 'A payroll cycle is awaiting approval.'},
]

# Named by the prompt's own catalogue (Section 2) but NOT instrumented in
# this phase — see PHASE3B_REPORT.md's notification-trigger catalogue for
# which legacy notification/email call sites were found and which were
# actually wired to events.emit() vs left as future work.


def sync() -> dict:
    from apps.platform_core.models import EventType
    created = unchanged = 0
    for spec in CORE_EVENT_TYPES:
        obj, was_created = EventType.objects.get_or_create(
            code=spec['code'], defaults={'module': spec['module'], 'description': spec['description'], 'is_system': True},
        )
        if was_created:
            created += 1
        else:
            unchanged += 1
    return {'created': created, 'unchanged': unchanged}


def sync_custom_entity_events(entity) -> None:
    """Called from services_custom_objects.publish_entity() — Task E.1's
    "Custom-object events (created, updated, status_changed) are
    generated automatically on publish." """
    from apps.platform_core.models import EventType
    for action in ('created', 'updated', 'status_changed'):
        EventType.objects.get_or_create(
            code=f'custom.{entity.code}.{action}', entity=entity,
            defaults={'module': 'platform_core', 'description': f'A {entity.label} record was {action}.', 'is_system': False},
        )
