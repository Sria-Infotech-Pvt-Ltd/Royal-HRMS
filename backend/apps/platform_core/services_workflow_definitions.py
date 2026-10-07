"""Phase 3B Task A.3 — publish-time validation for WorkflowDefinition."""
from __future__ import annotations

from django.utils import timezone

from apps.platform_core import approver_resolvers
from apps.platform_core import services_rules as rules
from apps.platform_core.models import WorkflowDefinition, WorkflowStep
from apps.platform_core.rule_errors import RuleError


class WorkflowValidationError(Exception):
    def __init__(self, message: str, errors: list[str] | None = None):
        self.message = message
        self.errors = errors or []
        super().__init__(message)


def _check_condition_parses(expr: dict, label: str, errors: list[str]) -> None:
    if not expr:
        return
    try:
        rules.evaluate(expr, {})
    except RuleError as exc:
        errors.append(f'{label}: {exc.message}')
    except Exception as exc:
        errors.append(f'{label}: {exc}')


def validate(definition: WorkflowDefinition) -> list[str]:
    """Returns a list of errors (empty = valid). Never raises — mirrors
    services_rule_definitions.type_check()'s contract."""
    errors: list[str] = []
    steps = list(definition.steps.order_by('order'))
    if not steps:
        errors.append('A workflow must have at least one step.')
        return errors

    step_codes = {s.code for s in steps}

    for step in steps:
        if step.step_type == WorkflowStep.TYPE_PARALLEL_GROUP:
            errors.append(f'Step {step.code}: parallel_group steps are not supported by the runtime engine in this phase.')

        if step.step_type == WorkflowStep.TYPE_APPROVAL and step.resolver:
            if step.resolver not in approver_resolvers.RESOLVERS:
                errors.append(f'Step {step.code}: unknown resolver {step.resolver!r}.')
        if step.step_type == WorkflowStep.TYPE_APPROVAL and not step.resolver:
            errors.append(f'Step {step.code}: an approval step must declare a resolver.')

        if step.step_type == WorkflowStep.TYPE_CONDITION_BRANCH:
            for target_code in (step.branch_next_step_code_if_true, step.branch_next_step_code_if_false):
                if target_code and target_code not in step_codes:
                    errors.append(f'Step {step.code}: branch target {target_code!r} does not exist in this definition.')
            _check_condition_parses(step.branch_condition, f'Step {step.code} branch_condition', errors)

        _check_condition_parses(step.skip_condition, f'Step {step.code} skip_condition', errors)
        _check_condition_parses(step.auto_approve_condition, f'Step {step.code} auto_approve_condition', errors)

        if step.quorum == WorkflowStep.QUORUM_N_OF_M and not step.quorum_n:
            errors.append(f'Step {step.code}: quorum=n_of_m requires quorum_n.')

    _check_condition_parses(definition.entry_condition, 'entry_condition', errors)

    # Priority-tie configuration error (Task A.1's "ties are a
    # configuration error caught at publish time").
    tied = WorkflowDefinition.objects.filter(
        entity=definition.entity, status=WorkflowDefinition.STATUS_PUBLISHED, priority=definition.priority,
    ).exclude(pk=definition.pk)
    if tied.exists():
        errors.append(f'Another published definition for this entity already uses priority {definition.priority} — priorities must be unique per entity among published definitions.')

    return errors


def publish(definition: WorkflowDefinition, *, effective_from=None) -> WorkflowDefinition:
    errors = validate(definition)
    if errors:
        raise WorkflowValidationError('Validation failed.', errors)
    definition.status = WorkflowDefinition.STATUS_PUBLISHED
    definition.effective_from = effective_from or timezone.localdate()
    definition.save(update_fields=['status', 'effective_from'])
    return definition


def impact_preview(definition: WorkflowDefinition) -> int:
    """Task A.3's "an impact preview (how many open records would
    match)" — for a custom entity, counts non-deleted CustomRecord rows
    of this entity whose entry_condition would currently evaluate true."""
    from apps.platform_core import services_custom_objects as custom_objects
    count = 0
    for record in custom_objects.list_records(definition.entity):
        ctx = {'record': record, **(record.data if isinstance(record.data, dict) else {})}
        if rules.evaluate(definition.entry_condition, ctx):
            count += 1
    return count
