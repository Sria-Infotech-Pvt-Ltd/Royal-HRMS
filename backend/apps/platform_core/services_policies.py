"""
Phase 3A Task D+E — policy resolution and the effective-policy explainer.

Cache invalidation design (Task D.4's "a wrong cached policy is a
payroll risk" warning, taken seriously): every resolved (employee, type,
date) result is cached under Phase 1's versioned `policies` metadata-
cache namespace. A version bump on that namespace invalidates EVERY
cached resolution at once (cheap, correct) rather than trying to compute
which individual cache keys a given Policy/PolicyAssignment change could
affect (expensive, and easy to get subtly wrong when a condition rule
references an employee field that just changed). The namespace is bumped
by Policy/PolicyAssignment/RuleVersion post_save signals (see signals.py)
— NOT on every employee field write, which would be a cache-invalidation
storm; instead, resolve() is given a short TTL-free cache keyed by date,
so a same-day re-resolution after an employee's own field change still
needs an explicit call to bust the cache for correctness-critical
callers (documented limitation, not silently wrong — see
PHASE3A_REPORT.md).
"""
from __future__ import annotations

import datetime

from django.db.models import Q

from apps.platform_core import cache as metadata_cache
from apps.platform_core import services_rules as rules
from apps.platform_core.models import Policy, PolicyAssignment, PolicyType


class PolicyResolutionError(Exception):
    def __init__(self, message: str):
        self.message = message
        super().__init__(message)


def _target_matches(assignment: PolicyAssignment, employee, employee_context: dict) -> bool:
    target_type, target_id = assignment.target_type, assignment.target_id

    if target_type == PolicyAssignment.TARGET_INDIVIDUAL:
        return str(employee.pk) == target_id
    if target_type == PolicyAssignment.TARGET_LEGAL_ENTITY:
        return not target_id or str(employee_context.get('legal_entity_id') or '') == target_id
    if target_type == PolicyAssignment.TARGET_POSITION:
        return str(employee_context.get('position_id') or '') == target_id
    if target_type == PolicyAssignment.TARGET_ORG_UNIT:
        if assignment.include_children:
            return target_id in (employee_context.get('org_unit_ancestor_ids') or [])
        return str(employee_context.get('org_unit_id') or '') == target_id
    if target_type == PolicyAssignment.TARGET_DESIGNATION:
        return str(employee_context.get('designation') or '') == target_id
    if target_type == PolicyAssignment.TARGET_GRADE:
        return str(employee_context.get('grade') or '') == target_id
    if target_type == PolicyAssignment.TARGET_EMPLOYMENT_TYPE:
        return str(employee_context.get('employment_type') or '') == target_id
    if target_type == PolicyAssignment.TARGET_LOCATION:
        return str(employee_context.get('branch_id') or '') == target_id
    if target_type == PolicyAssignment.TARGET_EMPLOYEE_GROUP:
        # Saved-filter employee groups (Phase 2 ListViewDefinition-style
        # filters) are not built in this phase's PolicyAssignment — no
        # group-membership source exists yet to evaluate against.
        # Refusing to silently match everyone/no one; documented deferral.
        raise PolicyResolutionError('TARGET_EMPLOYEE_GROUP assignments are not resolvable yet (no saved-filter engine built in Phase 3A).')
    return False


def _specificity_rank(policy_type: PolicyType, target_type: str) -> int:
    order = policy_type.get_specificity_order()
    try:
        return order.index(target_type)
    except ValueError:
        return len(order)


def resolve(policy_type_code: str, employee, as_of: datetime.date, *, employee_context: dict | None = None, _explain: bool = False):
    """Returns the winning Policy's parameters (STRATEGY_SINGLE) — or
    raises PolicyResolutionError if nothing resolves and no default
    exists. `employee_context` supplies the targeting fields
    (legal_entity_id/position_id/org_unit_id/org_unit_ancestor_ids/
    designation/grade/employment_type/branch_id) since this phase does
    not hardcode which core-entity columns back them (kept generic so
    later phases can wire real org-chart traversal without changing this
    function's signature)."""
    policy_type = PolicyType.objects.get(code=policy_type_code)
    employee_context = employee_context or {}
    suffix = f'{policy_type_code}:{employee.pk}:{as_of.isoformat()}'

    def _load():
        candidates = []
        rejected = []
        assignments = PolicyAssignment.objects.filter(
            policy_type=policy_type, effective_from__lte=as_of,
        ).filter(Q(effective_to__isnull=True) | Q(effective_to__gte=as_of)).select_related('policy').filter(
            policy__status=Policy.STATUS_PUBLISHED,
        )

        for assignment in assignments:
            try:
                target_ok = _target_matches(assignment, employee, employee_context)
            except PolicyResolutionError as exc:
                rejected.append({'assignment_id': assignment.pk, 'reason': str(exc)})
                continue
            if not target_ok:
                rejected.append({'assignment_id': assignment.pk, 'reason': 'Target does not match.'})
                continue
            if assignment.condition:
                try:
                    condition_ok = bool(rules.evaluate(assignment.condition, employee_context))
                except Exception as exc:
                    rejected.append({'assignment_id': assignment.pk, 'reason': f'Condition error: {exc}'})
                    continue
                if not condition_ok:
                    rejected.append({'assignment_id': assignment.pk, 'reason': 'Condition evaluated false.'})
                    continue
            candidates.append(assignment)

        default_policy = Policy.objects.filter(
            type=policy_type, is_default=True, status=Policy.STATUS_PUBLISHED, effective_from__lte=as_of,
        ).filter(Q(effective_to__isnull=True) | Q(effective_to__gte=as_of))
        if employee_context.get('legal_entity_id'):
            default_policy = default_policy.filter(Q(legal_entity_id=employee_context['legal_entity_id']) | Q(legal_entity__isnull=True))
        default_policy = default_policy.order_by('legal_entity_id').first()  # non-null (specific) legal_entity wins over null (global) at equal priority

        def sort_key(a):
            return (-_specificity_rank(policy_type, a.target_type), a.priority, a.effective_from)
        # Lower specificity_rank index = more specific = should win => sort
        # descending by "more specific first": negate rank so Python's
        # ascending sort still puts the most-specific candidate last,
        # then take the LAST one as the winner (ties broken by priority
        # then most-recent effective_from, both ascending — last wins).
        candidates_sorted = sorted(candidates, key=sort_key)
        winner_assignment = candidates_sorted[-1] if candidates_sorted else None

        result = {
            'winner_assignment_id': winner_assignment.pk if winner_assignment else None,
            'winner_policy_id': winner_assignment.policy_id if winner_assignment else (default_policy.pk if default_policy else None),
            'parameters': winner_assignment.policy.parameters if winner_assignment else (default_policy.parameters if default_policy else None),
            'used_default': winner_assignment is None and default_policy is not None,
            'candidates_considered': len(assignments) if hasattr(assignments, '__len__') else assignments.count(),
            'rejected': rejected,
        }
        if result['parameters'] is None:
            raise PolicyResolutionError(f'No policy of type {policy_type_code!r} resolves for this employee on {as_of}, and no default exists.')
        return result

    if _explain:
        return _load()  # explainer always needs the full detail, never the cached summary-only result
    return metadata_cache.cached('policies', suffix, _load)['parameters']


def resolve_many(policy_type_code: str, employees: list, as_of: datetime.date, *, employee_contexts: dict | None = None) -> dict:
    """Task D.5 — bulk resolution with a BOUNDED query count regardless
    of employee count: all assignments/policies for this type+date are
    fetched ONCE (2 queries), matched against each employee's context in
    Python, not per-employee queries."""
    policy_type = PolicyType.objects.get(code=policy_type_code)
    employee_contexts = employee_contexts or {}

    assignments = list(
        PolicyAssignment.objects.filter(policy_type=policy_type, effective_from__lte=as_of)
        .filter(Q(effective_to__isnull=True) | Q(effective_to__gte=as_of))
        .select_related('policy').filter(policy__status=Policy.STATUS_PUBLISHED)
    )
    default_policy = Policy.objects.filter(
        type=policy_type, is_default=True, status=Policy.STATUS_PUBLISHED, effective_from__lte=as_of,
    ).filter(Q(effective_to__isnull=True) | Q(effective_to__gte=as_of)).order_by('legal_entity_id').first()

    def sort_key(a):
        return (-_specificity_rank(policy_type, a.target_type), a.priority, a.effective_from)

    results = {}
    for employee in employees:
        ctx = employee_contexts.get(employee.pk, {})
        matching = []
        for assignment in assignments:
            try:
                if not _target_matches(assignment, employee, ctx):
                    continue
            except PolicyResolutionError:
                continue
            if assignment.condition and not bool(rules.evaluate(assignment.condition, ctx)):
                continue
            matching.append(assignment)
        matching.sort(key=sort_key)
        winner = matching[-1] if matching else None
        results[employee.pk] = winner.policy.parameters if winner else (default_policy.parameters if default_policy else None)

    return results


def explain(policy_type_code: str, employee, as_of: datetime.date, *, employee_context: dict | None = None) -> dict:
    """Task E — the effective-policy explainer: winning policy/assignment,
    every candidate considered and why it lost, final parameters."""
    return resolve(policy_type_code, employee, as_of, employee_context=employee_context, _explain=True)
