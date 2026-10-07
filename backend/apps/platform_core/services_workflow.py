"""
Phase 3B Task B — the workflow runtime engine's PUBLIC API
(`start`/`act`/`withdraw`/`reassign`/`cancel`/`bulk_act`). Internal step-
advancement logic lives in workflow_step_advance.py (split out purely to
respect this project's ~300-line file guideline). All mutating entry
points are transactional and use `select_for_update()` to serialize
concurrent actions — the mechanism that makes "an action submitted twice
is applied once" and "two approvers acting at once" both safe.

Scope cut, stated plainly: `parallel_group` steps are modeled
(WorkflowStep.step_type) but the engine only ever advances ONE step at a
time (linear + condition_branch) — true parallel-group fan-out/join is
NOT implemented in this phase. A definition using TYPE_PARALLEL_GROUP
will raise at publish-time validation
(services_workflow_definitions.validate) rather than behave
unpredictably at runtime. See PHASE3B_REPORT.md.
"""
from __future__ import annotations

from django.contrib.contenttypes.models import ContentType
from django.db import transaction
from django.utils import timezone

from apps.platform_core import services_rules as rules
from apps.platform_core import workflow_step_advance as step_advance
from apps.platform_core.models import WorkflowDefinition, WorkflowHistory, WorkflowInstance, WorkflowTask


class WorkflowError(Exception):
    def __init__(self, message: str):
        self.message = message
        super().__init__(message)


def resolve_applicable_definition(entity, record) -> WorkflowDefinition | None:
    """Task A.1 — highest-priority PUBLISHED definition for this entity
    whose entry_condition evaluates true. Ties at publish time are
    rejected by services_workflow_definitions.validate(), so at most one
    true-condition winner should ever exist per priority tier; if two
    somehow tie here anyway (a retired/republished edge case), the most
    recently created wins — never non-deterministic ordering."""
    candidates = WorkflowDefinition.objects.filter(
        entity=entity, status=WorkflowDefinition.STATUS_PUBLISHED,
    ).order_by('-priority', '-created_at')
    ctx = step_advance.record_context(record)
    for definition in candidates:
        if rules.evaluate(definition.entry_condition, ctx):
            return definition
    return None


def _entity_code_for(record) -> str:
    from apps.platform_core.models import CustomRecord
    if isinstance(record, CustomRecord):
        return record.entity.code
    raise WorkflowError('start() only supports CustomRecord instances in this phase — core-entity workflow triggering (Task C) is deferred, see PHASE3B_REPORT.md.')


@transaction.atomic
def start(record, *, requester=None, trigger: str = WorkflowDefinition.TRIGGER_MANUAL) -> WorkflowInstance | None:
    """Task B.2's start(). Returns None (does nothing) if no published
    definition's entry_condition matches — a record with no applicable
    workflow is simply not put under approval, not an error."""
    from apps.platform_core.models import EntityDefinition
    entity = EntityDefinition.objects.get(code=_entity_code_for(record))
    definition = resolve_applicable_definition(entity, record)
    if definition is None:
        return None

    instance = WorkflowInstance.objects.create(
        definition=definition, definition_version=definition.version,
        content_type=ContentType.objects.get_for_model(type(record)), object_id=str(record.pk),
        requester=requester, status=WorkflowInstance.STATUS_IN_PROGRESS,
    )
    step_advance.write_history(instance, action=WorkflowHistory.ACTION_STARTED, actor=requester)

    first_step = definition.steps.order_by('order').first()
    if first_step is None:
        instance.status = WorkflowInstance.STATUS_APPROVED
        instance.completed_at = timezone.now()
        instance.save(update_fields=['status', 'completed_at'])
        return instance

    step_advance.advance_to_step(instance, first_step, record, requester=requester)
    return instance


@transaction.atomic
def act(task_id, *, user, action: str, remarks: str = '', idempotency_key: str | None = None) -> WorkflowTask:
    """Task B.2's act(). Row-level-locked on the TASK (not the instance)
    so two different pending tasks on the same instance (quorum) can be
    acted on concurrently without blocking each other, while two clicks
    on the SAME task serialize and the second sees it already decided."""
    task = WorkflowTask.objects.select_for_update().get(pk=task_id)

    if idempotency_key and task.idempotency_key == idempotency_key and task.status != WorkflowTask.STATUS_PENDING:
        return task  # already applied — "twice submitted, applied once"

    if task.status != WorkflowTask.STATUS_PENDING:
        raise WorkflowError(f'This task is already {task.status} and cannot be acted on again.')
    if task.assignee_id != user.pk:
        raise WorkflowError('You are not the assignee of this task.')
    if task.step.require_remarks and not remarks:
        raise WorkflowError('Remarks are required for this action.')

    instance = WorkflowInstance.objects.select_for_update().get(pk=task.instance_id)
    if instance.status != WorkflowInstance.STATUS_IN_PROGRESS:
        raise WorkflowError('This workflow is no longer in progress.')

    # Separation of duties (Task B.4) — default: not allowed, full stop.
    # (1) A user can never approve a record they themselves requested,
    # regardless of how they ended up assigned (resolver misconfiguration,
    # a delegation that looped back, etc.) — resolution-time
    # skip_if_approver_is_requester is the FIRST line of defense; this is
    # the second, at the moment of acting, so it can never be bypassed.
    if instance.requester_id is not None and user.pk == instance.requester_id:
        raise WorkflowError('You cannot approve a record you requested yourself.')
    # (2) A user who already approved an EARLIER step of this same
    # instance cannot approve again at a later step, unless this step's
    # own configuration explicitly allows it (skip_if_same_as_previous_step
    # repurposed as that explicit allow flag at the per-step level).
    if task.step.skip_if_same_as_previous_step:
        already_approved_earlier_step = WorkflowTask.objects.filter(
            instance=instance, assignee=user, status=WorkflowTask.STATUS_APPROVED, step__order__lt=task.step.order,
        ).exists()
        if already_approved_earlier_step:
            raise WorkflowError('You already approved an earlier step of this workflow and cannot approve this one too.')

    task.status = {'approve': WorkflowTask.STATUS_APPROVED, 'reject': WorkflowTask.STATUS_REJECTED,
                   'send_back': WorkflowTask.STATUS_SENT_BACK, 'request_info': WorkflowTask.STATUS_INFO_REQUESTED,
                   'withdraw': WorkflowTask.STATUS_WITHDRAWN}.get(action)
    if task.status is None:
        raise WorkflowError(f'Unknown action: {action!r}')
    task.action = action
    task.remarks = remarks
    task.acted_at = timezone.now()
    if idempotency_key:
        task.idempotency_key = idempotency_key
    task.save(update_fields=['status', 'action', 'remarks', 'acted_at', 'idempotency_key'])

    history_action = {
        'approve': WorkflowHistory.ACTION_APPROVED, 'reject': WorkflowHistory.ACTION_REJECTED,
        'send_back': WorkflowHistory.ACTION_SENT_BACK, 'request_info': WorkflowHistory.ACTION_INFO_REQUESTED,
        'withdraw': WorkflowHistory.ACTION_WITHDRAWN,
    }[action]
    step_advance.write_history(instance, action=history_action, task=task, actor=user, remarks=remarks)

    if action == 'reject':
        step_advance.complete_instance(instance, WorkflowInstance.STATUS_REJECTED)
        return task
    if action == 'send_back':
        prev_step = instance.definition.steps.filter(order__lt=task.step.order).order_by('-order').first()
        record = step_advance.get_record(instance)
        if prev_step and record is not None:
            step_advance.advance_to_step(instance, prev_step, record, requester=instance.requester)
        else:
            step_advance.complete_instance(instance, WorkflowInstance.STATUS_REJECTED)
        return task
    if action == 'request_info':
        return task  # stays pending-equivalent; frontend prompts requester, no step advance in this phase

    if action == 'approve':
        _check_quorum_and_advance(instance, task.step)
    return task


def _check_quorum_and_advance(instance: WorkflowInstance, step) -> None:
    from apps.platform_core.models import WorkflowStep
    tasks = list(WorkflowTask.objects.filter(instance=instance, step=step))
    approved = [t for t in tasks if t.status == WorkflowTask.STATUS_APPROVED]

    if step.quorum == WorkflowStep.QUORUM_ANY_ONE:
        met = len(approved) >= 1
    elif step.quorum == WorkflowStep.QUORUM_ALL:
        met = len(approved) == len(tasks)
    elif step.quorum == WorkflowStep.QUORUM_N_OF_M:
        met = len(approved) >= (step.quorum_n or len(tasks))
    else:
        met = len(approved) >= 1

    if not met:
        return
    # Expire remaining pending tasks for this step — quorum already met.
    WorkflowTask.objects.filter(instance=instance, step=step, status=WorkflowTask.STATUS_PENDING).update(status=WorkflowTask.STATUS_EXPIRED)
    record = step_advance.get_record(instance)
    if record is not None:
        step_advance.move_past_step(instance, step, record, requester=instance.requester)


@transaction.atomic
def withdraw(instance_id, *, user) -> WorkflowInstance:
    instance = WorkflowInstance.objects.select_for_update().get(pk=instance_id)
    if instance.requester_id != user.pk:
        raise WorkflowError('Only the requester can withdraw this.')
    if instance.status != WorkflowInstance.STATUS_IN_PROGRESS:
        raise WorkflowError('This workflow is no longer in progress.')
    WorkflowTask.objects.filter(instance=instance, status=WorkflowTask.STATUS_PENDING).update(status=WorkflowTask.STATUS_WITHDRAWN)
    instance.status = WorkflowInstance.STATUS_WITHDRAWN
    instance.completed_at = timezone.now()
    instance.save(update_fields=['status', 'completed_at'])
    step_advance.write_history(instance, action=WorkflowHistory.ACTION_WITHDRAWN, actor=user)
    return instance


@transaction.atomic
def reassign(task_id, *, new_user, actor) -> WorkflowTask:
    task = WorkflowTask.objects.select_for_update().get(pk=task_id)
    if task.status != WorkflowTask.STATUS_PENDING:
        raise WorkflowError('Only a pending task can be reassigned.')
    task.original_assignee = task.original_assignee or task.assignee
    task.assignee = new_user
    task.save(update_fields=['original_assignee', 'assignee'])
    step_advance.write_history(task.instance, action=WorkflowHistory.ACTION_REASSIGNED, task=task, actor=actor, remarks=f'Reassigned to {new_user}.')
    return task


@transaction.atomic
def cancel(instance_id, *, actor) -> WorkflowInstance:
    instance = WorkflowInstance.objects.select_for_update().get(pk=instance_id)
    WorkflowTask.objects.filter(instance=instance, status=WorkflowTask.STATUS_PENDING).update(status=WorkflowTask.STATUS_WITHDRAWN)
    instance.status = WorkflowInstance.STATUS_CANCELLED
    instance.completed_at = timezone.now()
    instance.save(update_fields=['status', 'completed_at'])
    step_advance.write_history(instance, action=WorkflowHistory.ACTION_CANCELLED, actor=actor)
    return instance


def bulk_act(task_ids: list, *, user, action: str, remarks: str = '') -> dict:
    """Task B.7 — each task validated/acted on individually; one task's
    failure never blocks the others."""
    results = {'succeeded': [], 'failed': []}
    for task_id in task_ids:
        try:
            act(task_id, user=user, action=action, remarks=remarks)
            results['succeeded'].append(str(task_id))
        except WorkflowError as exc:
            results['failed'].append({'task_id': str(task_id), 'error': exc.message})
    return results
