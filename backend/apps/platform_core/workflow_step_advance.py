"""
Phase 3B Task B — internal step-advancement helpers, split out of
services_workflow.py purely to respect this project's ~300-line file
guideline. Self-contained (no import from services_workflow.py) so the
two modules depend on each other in only one direction:
services_workflow.py imports FROM here, never the reverse.
"""
from __future__ import annotations

import datetime

from django.utils import timezone

from apps.platform_core import approver_resolvers
from apps.platform_core import services_rules as rules
from apps.platform_core.models import (
    Delegation, WorkflowApproverOverride, WorkflowHistory, WorkflowInstance, WorkflowStep, WorkflowTask,
)


def record_context(record, requester=None) -> dict:
    employee = getattr(record, 'employee', record)
    ctx = {'record': record, 'requester': requester}
    for attr in ('employment_type', 'department', 'branch_id', 'legal_entity_id'):
        ctx[attr] = getattr(employee, attr, None)
    if hasattr(record, 'data') and isinstance(record.data, dict):
        ctx.update(record.data)
    return ctx


def _models_q_covers(as_of):
    from django.db.models import Q
    return Q(effective_to__isnull=True) | Q(effective_to__gte=as_of)


def _models_q_covers_delegation(as_of):
    from django.db.models import Q
    return Q(start__lte=as_of) & (Q(end__isnull=True) | Q(end__gte=as_of))


def _apply_overrides_and_delegation(users: list, *, employee, definition, step, as_of: datetime.date) -> list:
    """Task A.4 (per-employee override) then Task B.3 (delegation),
    applied in that order — an override changes WHO the assignee is;
    delegation then checks whether THAT assignee has delegated their
    workload."""
    override = WorkflowApproverOverride.objects.filter(
        employee=employee, definition=definition, step_code=step.code, effective_from__lte=as_of,
    ).filter(_models_q_covers(as_of)).first() if employee is not None else None
    if override:
        users = [override.user]

    resolved = []
    for user in users:
        delegation = Delegation.objects.filter(to_user__isnull=False, from_user=user).filter(_models_q_covers_delegation(as_of)).first()
        if delegation and delegation.covers(as_of, definition.entity.code):
            resolved.append(delegation.to_user)
        else:
            resolved.append(user)
    return resolved


def resolve_step_approvers(step: WorkflowStep, record, requester, definition) -> list:
    if not step.resolver:
        return []
    users = approver_resolvers.resolve(step.resolver, record, step.resolver_params, requester=requester)
    employee = getattr(record, 'employee', None)
    users = _apply_overrides_and_delegation(users, employee=employee, definition=definition, step=step, as_of=timezone.localdate())

    # Separation of duties / skip rules (Task A.2, B.4).
    if step.skip_if_approver_is_requester and requester is not None:
        users = [u for u in users if u.pk != requester.pk]
    return users


def write_history(instance, *, action, task=None, actor=None, remarks=''):
    WorkflowHistory.objects.create(instance=instance, task=task, action=action, actor=actor, remarks=remarks)


def emit_task_assigned(task):
    from apps.platform_core import services_events as events
    events.emit('workflow.task.assigned', {
        'task_id': str(task.pk), 'instance_id': str(task.instance_id),
        'assignee_id': str(task.assignee_id) if task.assignee_id else None,
        'step_label': task.step.label, 'due_at': task.due_at.isoformat() if task.due_at else None,
    }, actor=task.assignee)


def due_at_for_step(step: WorkflowStep):
    if not step.sla_due_in_hours:
        return None
    return timezone.now() + datetime.timedelta(hours=step.sla_due_in_hours)


def get_record(instance: WorkflowInstance):
    model = instance.content_type.model_class()
    return model.objects.filter(pk=instance.object_id).first()


def advance_to_step(instance: WorkflowInstance, step: WorkflowStep, record, *, requester=None):
    definition = instance.definition

    if step.step_type == WorkflowStep.TYPE_CONDITION_BRANCH:
        ctx = record_context(record, requester)
        next_code = step.branch_next_step_code_if_true if rules.evaluate(step.branch_condition, ctx) else step.branch_next_step_code_if_false
        next_step = definition.steps.filter(code=next_code).first() if next_code else None
        if next_step is None:
            complete_instance(instance, WorkflowInstance.STATUS_APPROVED)
            return
        advance_to_step(instance, next_step, record, requester=requester)
        return

    ctx = record_context(record, requester)
    if step.skip_condition and rules.evaluate(step.skip_condition, ctx):
        move_past_step(instance, step, record, requester=requester)
        return
    if step.auto_approve_condition and rules.evaluate(step.auto_approve_condition, ctx):
        instance.current_step_codes = [step.code]
        instance.save(update_fields=['current_step_codes'])
        write_history(instance, action=WorkflowHistory.ACTION_AUTO_ACTIONED, remarks=f'Step {step.code} auto-approved by condition.')
        move_past_step(instance, step, record, requester=requester)
        return

    if step.step_type == WorkflowStep.TYPE_NOTIFICATION_ONLY or step.step_type == WorkflowStep.TYPE_SYSTEM_ACTION:
        instance.current_step_codes = [step.code]
        instance.save(update_fields=['current_step_codes'])
        if step.step_type == WorkflowStep.TYPE_SYSTEM_ACTION:
            _run_system_action(step, record)
        move_past_step(instance, step, record, requester=requester)
        return

    approvers = resolve_step_approvers(step, record, requester, definition)
    if not approvers:
        handle_no_approver(instance, step, record, requester=requester)
        return

    instance.current_step_codes = [step.code]
    instance.save(update_fields=['current_step_codes'])
    due_at = due_at_for_step(step)
    for user in approvers:
        task = WorkflowTask.objects.create(instance=instance, step=step, assignee=user, due_at=due_at)
        write_history(instance, action=WorkflowHistory.ACTION_TASK_CREATED, task=task, actor=requester)
        emit_task_assigned(task)


def _run_system_action(step: WorkflowStep, record):
    """Task A.2's system_action step type — a tiny registered action
    catalogue (set_field only, in this phase; set_status/create_record/
    call_webhook are named by the prompt but NOT implemented — see
    PHASE3B_REPORT.md). Never arbitrary code: `resolver_params` names a
    fixed action key, same whitelist discipline as the rule engine."""
    action = step.resolver_params.get('action')
    if action == 'set_field' and hasattr(record, 'data'):
        field = step.resolver_params.get('field')
        value = step.resolver_params.get('value')
        if field:
            record.data[field] = value
            record.save(update_fields=['data'])


def handle_no_approver(instance: WorkflowInstance, step: WorkflowStep, record, *, requester=None):
    if step.no_approver_action == WorkflowStep.NO_APPROVER_SKIP:
        move_past_step(instance, step, record, requester=requester)
        return
    if step.no_approver_action == WorkflowStep.NO_APPROVER_FALLBACK_POSITION and step.no_approver_fallback_position_id:
        from core.access import holders_of_position
        fallback_users = list(holders_of_position(step.no_approver_fallback_position_id).filter(is_active=True))
        if fallback_users:
            instance.current_step_codes = [step.code]
            instance.save(update_fields=['current_step_codes'])
            due_at = due_at_for_step(step)
            for user in fallback_users:
                task = WorkflowTask.objects.create(instance=instance, step=step, assignee=user, due_at=due_at)
                write_history(instance, action=WorkflowHistory.ACTION_TASK_CREATED, task=task)
                emit_task_assigned(task)
            return
    # NO_APPROVER_BLOCK, or fallback also found nobody — never silent.
    instance.status = WorkflowInstance.STATUS_ERROR
    instance.save(update_fields=['status'])
    write_history(instance, action=WorkflowHistory.ACTION_CANCELLED, remarks=f'No approver found for step {step.code}; blocked per no_approver_action.')


def move_past_step(instance: WorkflowInstance, step: WorkflowStep, record, *, requester=None):
    next_step = instance.definition.steps.filter(order__gt=step.order).order_by('order').first()
    if next_step is None:
        complete_instance(instance, WorkflowInstance.STATUS_APPROVED)
        return
    advance_to_step(instance, next_step, record, requester=requester)


def complete_instance(instance: WorkflowInstance, status: str):
    instance.status = status
    instance.current_step_codes = []
    instance.completed_at = timezone.now()
    instance.save(update_fields=['status', 'current_step_codes', 'completed_at'])
    write_history(instance, action=WorkflowHistory.ACTION_COMPLETED, remarks=f'Instance {status}.')
    _sync_record_status(instance)
    _emit_completion_event(instance)


def _sync_record_status(instance: WorkflowInstance):
    """Task B.2's declared workflow-status -> record-status mapping."""
    definition = instance.definition
    if not definition.status_field_code or not definition.status_mapping:
        return
    status_code = definition.status_mapping.get(instance.status)
    if not status_code:
        return
    record = get_record(instance)
    if record is not None and hasattr(record, 'data'):
        record.data[definition.status_field_code] = status_code
        record.save(update_fields=['data'])


def _emit_completion_event(instance: WorkflowInstance):
    from apps.platform_core import services_events as events
    code = {'approved': 'workflow.approved', 'rejected': 'workflow.rejected'}.get(instance.status)
    if code:
        events.emit(code, {'instance_id': str(instance.pk), 'entity_code': instance.definition.entity.code}, actor=instance.requester)
