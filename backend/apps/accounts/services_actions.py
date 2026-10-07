"""
Phase 5B Task D.3 — the employment action engine: validate, apply effects
atomically, emit events. Each handler is idempotent (re-applying an
already-`applied` action is a documented no-op, checked once in
`apply_employment_action` itself rather than in every handler) and
returns the `previous_values` fragment needed to reverse it later.

Only two effect handlers are built in this pass — `set_placement`
(Position/Transfer/Promotion-style moves, via Phase 5A's
services_placement.assign_position) and `set_employment_status` (status
transitions, e.g. Confirmation) — enough to prove the framework end to
end and to carry Task E's Confirmation/Transfer/Promotion action types
for real. The remaining effects named in the prompt (org unit, location/
branch, relationship, grade/designation, legal entity, custom attributes,
salary-revision-as-data, separation-link) are NOT registered — calling
an ActionType with an unregistered handler code raises a clear
`UnknownEffectHandler` rather than silently doing nothing.
"""
from __future__ import annotations

from django.db import transaction
from django.utils import timezone

from apps.accounts.models_actions import EmploymentAction


class UnknownEffectHandler(Exception):
    pass


class ActionConflictError(Exception):
    pass


def _handle_set_placement(action: EmploymentAction, effect: dict) -> dict:
    from apps.accounts.models import Position
    from apps.accounts.services_placement import assign_position

    position_id = effect.get('position_id') or action.payload.get('position_id')
    position = Position.objects.get(pk=position_id)

    prior = action.employee.placements.filter(effective_to__isnull=True).select_related('position').first()
    previous = {'position_id': str(prior.position_id), 'effective_from': prior.effective_from.isoformat()} if prior else None

    assign_position(action.employee, position, effective_from=action.effective_date, created_by=action.applied_by)
    return {'set_placement': previous}


def _handle_set_employment_status(action: EmploymentAction, effect: dict) -> dict:
    from apps.accounts.models import User

    new_status = effect.get('status') or action.action_type.resulting_status
    previous_status = action.employee.employment_status
    User.objects.filter(pk=action.employee_id).update(employment_status=new_status, updated_at=timezone.now())
    action.employee.employment_status = new_status
    return {'set_employment_status': previous_status}


EFFECT_HANDLERS = {
    'set_placement': _handle_set_placement,
    'set_employment_status': _handle_set_employment_status,
}


def validate_employment_action(action: EmploymentAction) -> None:
    action_type = action.action_type
    allowed = action_type.allowed_from_statuses or []
    if allowed and action.employee.employment_status not in allowed:
        raise ActionConflictError(
            f'{action_type.code} cannot be applied from employment_status={action.employee.employment_status!r}.'
        )
    if not action_type.allow_backdating and action.effective_date < timezone.localdate():
        raise ActionConflictError(f'{action_type.code} does not allow back-dating.')
    if action_type.allow_backdating and action_type.max_backdate_days is not None:
        days_back = (timezone.localdate() - action.effective_date).days
        if days_back > action_type.max_backdate_days:
            raise ActionConflictError(
                f'{action_type.code} cannot be back-dated more than {action_type.max_backdate_days} days.'
            )
    if not action_type.allow_future_dating and action.effective_date > timezone.localdate():
        raise ActionConflictError(f'{action_type.code} does not allow future-dating.')

    conflicting = EmploymentAction.objects.filter(
        employee=action.employee, effective_date=action.effective_date, action_type=action_type,
        status__in=[EmploymentAction.STATUS_PENDING_APPROVAL, EmploymentAction.STATUS_APPROVED, EmploymentAction.STATUS_SCHEDULED],
    ).exclude(pk=action.pk)
    if conflicting.exists():
        raise ActionConflictError(
            f'Another {action_type.code} action is already pending for this employee on {action.effective_date}.'
        )


def apply_employment_action(action: EmploymentAction) -> EmploymentAction:
    """Applies an action's effects atomically. Idempotent: calling this on
    an already-`applied` action is a no-op (returns it unchanged) rather
    than re-running handlers a second time."""
    if action.status == EmploymentAction.STATUS_APPLIED:
        return action

    validate_employment_action(action)

    with transaction.atomic():
        action = EmploymentAction.objects.select_for_update().select_related('employee', 'action_type').get(pk=action.pk)
        if action.status == EmploymentAction.STATUS_APPLIED:
            return action

        previous_values = dict(action.previous_values or {})
        for effect in action.action_type.effects:
            handler_code = effect.get('handler')
            handler = EFFECT_HANDLERS.get(handler_code)
            if handler is None:
                raise UnknownEffectHandler(f'No effect handler registered for {handler_code!r}.')
            previous_values.update(handler(action, effect))

        action.previous_values = previous_values
        action.status = EmploymentAction.STATUS_APPLIED
        action.applied_at = timezone.now()
        action.save(update_fields=['previous_values', 'status', 'applied_at', 'updated_at'])

    from apps.platform_core.services_events import emit
    emit('employment_action.applied', {
        'employment_action_id': str(action.id), 'employee_id': str(action.employee_id),
        'action_type_code': action.action_type.code,
    }, actor=action.applied_by)
    if action.action_type.code == 'PROMOTION':
        emit('employee.promoted', {'employee_id': str(action.employee_id), 'employment_action_id': str(action.id)})
    if action.effective_date < timezone.localdate():
        emit('employment_action.backdated', {
            'employment_action_id': str(action.id), 'employee_id': str(action.employee_id),
        })
    return action


def reverse_employment_action(action: EmploymentAction, *, reason: str, created_by=None) -> EmploymentAction:
    """Creates and applies a correction EmploymentAction that restores
    `action.previous_values` — never edits or deletes the original row.
    Blocked if a later action for the same employee has already been
    applied on top of this one's effects (the prompt's own "blocked
    unless those are reversed first" rule), checked narrowly as "any
    other action applied for this employee on a later-or-equal effective
    date" since this pass only tracks two effect kinds."""
    if action.status != EmploymentAction.STATUS_APPLIED:
        raise ActionConflictError('Only an applied action can be reversed.')

    later_action_exists = EmploymentAction.objects.filter(
        employee=action.employee, effective_date__gte=action.effective_date, status=EmploymentAction.STATUS_APPLIED,
    ).exclude(pk=action.pk).exists()
    if later_action_exists:
        raise ActionConflictError(
            'A later employment action exists for this employee — reverse that one first.'
        )

    correction_type, _ = _get_or_create_correction_action_type()
    correction = EmploymentAction.objects.create(
        employee=action.employee, action_type=correction_type, reason=reason,
        effective_date=action.effective_date, payload={'reversal_of': str(action.id)},
        reversal_of=action, created_by=created_by, status=EmploymentAction.STATUS_DRAFT,
    )

    with transaction.atomic():
        if 'set_placement' in action.previous_values and action.previous_values['set_placement']:
            from apps.accounts.models import Position
            from apps.accounts.services_placement import assign_position
            prev = action.previous_values['set_placement']
            assign_position(
                action.employee, Position.objects.get(pk=prev['position_id']),
                effective_from=action.effective_date, created_by=created_by,
            )
        if 'set_employment_status' in action.previous_values:
            from apps.accounts.models import User
            User.objects.filter(pk=action.employee_id).update(
                employment_status=action.previous_values['set_employment_status'], updated_at=timezone.now(),
            )

        correction.status = EmploymentAction.STATUS_APPLIED
        correction.applied_at = timezone.now()
        correction.applied_by = created_by
        correction.save(update_fields=['status', 'applied_at', 'applied_by', 'updated_at'])

        action.status = EmploymentAction.STATUS_REVERSED
        action.save(update_fields=['status', 'updated_at'])

    return correction


def _get_or_create_correction_action_type():
    from apps.accounts.models_actions import ActionType
    return ActionType.objects.get_or_create(
        code='DATA_CORRECTION', defaults={
            'name': 'Data Correction', 'category': 'correction', 'effects': [],
            'requires_effective_date': True, 'is_system': True,
        },
    )
