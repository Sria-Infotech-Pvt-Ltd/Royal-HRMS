"""
Phase 3B Task A.2 — approver resolver registry. Each resolver is code
(choosing WHICH one, and its params, is admin configuration via
WorkflowStep.resolver/resolver_params). Resolvers return a list of users
(quorum decides how many must act).

Resolvers marked "real parity" reproduce apps/accounts/services_approval.py's
existing behavior exactly (verified by reading that module, not guessed),
so a migrated legacy workflow (Task C, deferred — see PHASE3B_REPORT.md)
can reuse them unchanged. Resolvers marked "new" have no legacy
equivalent to match and are free-form Phase 3B capability.
"""
from __future__ import annotations


class ResolverError(Exception):
    def __init__(self, message: str):
        self.message = message
        super().__init__(message)


def _specific_user(record, params, *, requester=None):
    """New. params: {"user_id": ...}"""
    from apps.accounts.models import User
    user = User.objects.filter(pk=params.get('user_id')).first()
    return [user] if user else []


def _position_scoped(record, params, *, requester=None):
    """New — Task A.2's "whoever holds a position (with scope: same branch, same org unit,
    same legal entity, global)". params: {"position_id": ..., "scope":
    "global"|"branch"|"org_unit"|"legal_entity"}. The employee whose
    record this is comes from `record.employee` / `record` itself if it
    IS a User (custom-entity convention: records needing an employee
    scope declare an `employee` FK)."""
    from apps.accounts.models import User
    position_id = params.get('position_id')
    scope = params.get('scope', 'global')
    employee = getattr(record, 'employee', record if isinstance(record, User) else None)

    from core.access import holders_of_position

    qs = holders_of_position(position_id).filter(is_active=True)
    if scope == 'global' or employee is None:
        return list(qs)
    if scope == 'branch':
        return list(qs.filter(branch_id=getattr(employee, 'branch_id', None)))
    if scope == 'legal_entity':
        return list(qs.filter(legal_entity_id=getattr(employee, 'legal_entity_id', None)))
    if scope == 'org_unit':
        return list(qs.filter(placements__position__org_unit_id=getattr(employee, 'org_unit_id', None)).distinct())
    raise ResolverError(f'Unknown position scope: {scope!r}')


def _reporting_manager_level_n(record, params, *, requester=None):
    """Real parity with services_approval.resolve_approver's
    can_manage_team branch (reporting_manager), generalised to level N
    (Task A.2's explicit ask — the legacy code only ever used level 1).
    params: {"level": 1}"""
    from apps.accounts.models import User
    employee = getattr(record, 'employee', record if isinstance(record, User) else None)
    if employee is None:
        return []
    level = int(params.get('level', 1))
    current = employee
    for _ in range(level):
        current = getattr(current, 'reporting_manager', None)
        if current is None:
            return []
    return [current]


def _dotted_line_manager(record, params, *, requester=None):
    """Real field (User.dotted_line_manager exists), new as an approver
    resolver (services_approval.py never used it — only reporting_manager/hr)."""
    from apps.accounts.models import User
    employee = getattr(record, 'employee', record if isinstance(record, User) else None)
    manager = getattr(employee, 'dotted_line_manager', None) if employee else None
    return [manager] if manager else []


def _org_unit_chief(record, params, *, requester=None):
    """Real parity with services_approval.resolve_employee_org_unit_chief —
    calls that EXACT function, not a reimplementation, so this resolver
    can never silently drift from the legacy behavior it reproduces."""
    from apps.accounts.models import User
    from apps.accounts.services_approval import resolve_employee_org_unit_chief
    employee = getattr(record, 'employee', record if isinstance(record, User) else None)
    if employee is None:
        return []
    chief = resolve_employee_org_unit_chief(employee)
    return [chief] if chief else []


def _hr_business_partner(record, params, *, requester=None):
    """Real parity with services_approval.resolve_approver's non-
    can_manage_team branch (`employee.hr`)."""
    from apps.accounts.models import User
    employee = getattr(record, 'employee', record if isinstance(record, User) else None)
    hr = getattr(employee, 'hr', None) if employee else None
    return [hr] if hr else []


def _position_holder(record, params, *, requester=None):
    """New. params: {"position_id": ...} or {"position_field": "position_id"}
    (read the position id off the record itself)."""
    from django.utils import timezone
    from django.db.models import Q
    from apps.accounts.models import Placement
    position_id = params.get('position_id') or getattr(record, params.get('position_field', ''), None)
    if not position_id:
        return []
    today = timezone.localdate()
    placement = Placement.objects.filter(position_id=position_id, effective_from__lte=today).filter(
        Q(effective_to__isnull=True) | Q(effective_to__gte=today)
    ).select_related('employee').first()
    return [placement.employee] if placement else []


def _record_field(record, params, *, requester=None):
    """New — Task A.2's "a user taken from a field on the record".
    params: {"field": "manager_id"}"""
    field = params.get('field')
    value = getattr(record, field, None) if field else None
    if value is None:
        return []
    from apps.accounts.models import User
    if isinstance(value, User):
        return [value]
    user = User.objects.filter(pk=value).first()
    return [user] if user else []


def _rule_expression(record, params, *, requester=None):
    """New — Task A.2's "a rule expression returning users". params:
    {"rule_code": ...}. The rule's declared return is a user id or list
    of user ids; `employee.field` and other context the rule needs comes
    from the same employee_context convention services_policies.py uses."""
    from apps.accounts.models import User
    from apps.platform_core import services_rule_definitions as rule_defs
    employee = getattr(record, 'employee', None)
    context = {'record': record, 'employee': employee, 'requester': requester}
    result = rule_defs.evaluate_effective(params['rule_code'], context, __import__('datetime').date.today())
    ids = result if isinstance(result, list) else [result]
    return list(User.objects.filter(pk__in=[i for i in ids if i is not None]))


RESOLVERS = {
    'specific_user': _specific_user,
    'position_scoped': _position_scoped,
    'reporting_manager_level_n': _reporting_manager_level_n,
    'dotted_line_manager': _dotted_line_manager,
    'org_unit_chief': _org_unit_chief,
    'hr_business_partner': _hr_business_partner,
    'position_holder': _position_holder,
    'record_field': _record_field,
    'rule_expression': _rule_expression,
}

# Named by the prompt, NOT implemented in this phase: "department head (as
# today)" is covered by org_unit_chief (services_approval.py's own
# resolve_employee_org_unit_chief IS the department-head concept per its
# own docstring — "Replaces the retired Department.manager concept").
# "branch admin of the employee's branch" has no single existing function
# to call (would need a guessed definition of "branch admin" — which
# Role/permission combination counts) — left unregistered rather than
# guessed; calling it raises the same clean "unknown resolver" error as
# an unregistered rule-engine data provider.


def resolve(resolver_name: str, record, params: dict, *, requester=None) -> list:
    fn = RESOLVERS.get(resolver_name)
    if fn is None:
        raise ResolverError(f'Unknown or unregistered approver resolver: {resolver_name!r}')
    return [u for u in fn(record, params, requester=requester) if u is not None]
