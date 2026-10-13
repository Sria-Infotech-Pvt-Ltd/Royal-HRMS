"""Phase 8A Task B — checklist instance creation from a template, with relative due-date resolution and dependency-aware status."""
import datetime

from django.db import transaction

from apps.hrms.models import ChecklistInstance, ChecklistTaskInstance, ChecklistTaskTemplate, ChecklistTemplate

_ASSIGNEE_RESOLVERS = {
    ChecklistTaskTemplate.ASSIGNEE_EMPLOYEE: lambda employee: employee,
    ChecklistTaskTemplate.ASSIGNEE_MANAGER: lambda employee: getattr(employee, 'reporting_manager', None),
    ChecklistTaskTemplate.ASSIGNEE_HR: lambda employee: getattr(employee, 'hr', None),
    ChecklistTaskTemplate.ASSIGNEE_BUDDY: lambda employee: None,  # BUDDY relationship type not built this pass — see module docstring
}


@transaction.atomic
def create_instance_from_template(template: ChecklistTemplate, employee, anchor_date: datetime.date) -> ChecklistInstance:
    """Idempotent per (template, employee, anchor_date) is NOT enforced at
    the DB level (an employee could legitimately go through the same
    onboarding template twice across a rehire) — callers that want
    idempotency should check for an existing in-progress instance first."""
    instance = ChecklistInstance.objects.create(template=template, employee=employee, anchor_date=anchor_date)

    task_templates = list(template.task_templates.order_by('order'))
    for task_template in task_templates:
        due_date = anchor_date + datetime.timedelta(days=task_template.due_offset_days)
        resolver = _ASSIGNEE_RESOLVERS.get(task_template.assignee_resolver)
        assignee = resolver(employee) if resolver else None

        # A task with a dependency is ALWAYS created blocked — the
        # dependency's own instance was just created too (or will be),
        # and is never already "done" at the moment this instance is
        # first created, regardless of creation order.
        status = ChecklistTaskInstance.STATUS_BLOCKED if task_template.depends_on_id else ChecklistTaskInstance.STATUS_PENDING

        ChecklistTaskInstance.objects.create(
            checklist=instance, task_template=task_template, assignee=assignee, due_date=due_date, status=status,
        )

    return instance


def complete_task(task_instance: ChecklistTaskInstance, completed_by) -> ChecklistTaskInstance:
    from django.utils import timezone

    task_instance.status = ChecklistTaskInstance.STATUS_DONE
    task_instance.completed_by = completed_by
    task_instance.completed_at = timezone.now()
    task_instance.save(update_fields=['status', 'completed_by', 'completed_at'])

    # Unblock any task whose depends_on is this one.
    dependents = ChecklistTaskInstance.objects.filter(
        checklist=task_instance.checklist, task_template__depends_on=task_instance.task_template,
        status=ChecklistTaskInstance.STATUS_BLOCKED,
    )
    dependents.update(status=ChecklistTaskInstance.STATUS_PENDING)

    checklist = task_instance.checklist
    if not checklist.tasks.exclude(status=ChecklistTaskInstance.STATUS_DONE).exists():
        checklist.status = ChecklistInstance.STATUS_COMPLETED
        checklist.completed_at = timezone.now()
        checklist.save(update_fields=['status', 'completed_at'])

    return task_instance
