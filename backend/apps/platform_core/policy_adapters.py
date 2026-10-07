"""
Phase 3A Task G — a reusable adapter base that later phases (leave, WFH,
expense, separation, probation, notice period, payroll) use to read
policy-engine values without each module hand-rolling its own
flag-check-and-fallback logic. Every concrete adapter follows the same
shape:

    class SomeModulePolicyAdapter(PolicyAdapter):
        policy_type_code = 'SOME_TYPE'
        flag_code = 'policies.v2'  # the module's own cutover flag

        def legacy_resolve(self, employee, as_of):
            ...  # today's existing logic, UNCHANGED

This phase registers exactly ONE concrete adapter for real:
`LeavePlanPolicyAdapter` (Task G.2) — read-only, exposing the EXISTING
`LeavePolicy.applicable_*` lists through the explainer so admins can see
what applies today, without changing leave behavior at all (Task G.2's
explicit "do not change leave behaviour" instruction).
"""
from __future__ import annotations

import datetime

from apps.platform_core import services_flags
from apps.platform_core import services_policies as policies


class PolicyAdapter:
    """Subclasses set `policy_type_code` and `flag_code`, and implement
    `legacy_resolve(employee, as_of)` to reproduce today's existing
    resolution exactly. `get(employee, as_of)` is the ONE function the
    rest of the codebase should call — it never bypasses the flag."""
    policy_type_code: str = ''
    flag_code: str = ''

    def legacy_resolve(self, employee, as_of: datetime.date) -> dict:
        raise NotImplementedError

    def employee_context(self, employee, as_of: datetime.date) -> dict:
        """Subclasses override to supply resolve()'s targeting context
        (legal_entity_id/org_unit_id/etc.) — default is empty, meaning
        only TARGET_INDIVIDUAL/TARGET_LEGAL_ENTITY(null)/default
        assignments can ever match until a subclass wires real context."""
        return {}

    def get(self, employee, as_of: datetime.date | None = None) -> dict:
        as_of = as_of or datetime.date.today()
        if not services_flags.is_enabled(self.flag_code):
            return self.legacy_resolve(employee, as_of)
        return policies.resolve(self.policy_type_code, employee, as_of, employee_context=self.employee_context(employee, as_of))


class LeavePlanPolicyAdapter(PolicyAdapter):
    """Task G.2 — READ-ONLY. Exposes `LeavePolicy.applicable_*` through
    the explainer; `legacy_resolve` is the only path ever actually used
    in this phase (no flag flips this on for real writes anywhere), since
    leave behavior itself is explicitly out of scope until Phase 6."""
    policy_type_code = 'LEAVE_PLAN'
    flag_code = 'policies.v2'  # shared with the attendance cutover flag; leave never actually reads via the engine path in this phase

    def legacy_resolve(self, employee, as_of: datetime.date) -> dict:
        from apps.hrms.models import LeavePolicy
        applicable = []
        for policy in LeavePolicy.objects.all():
            if self._employee_matches_policy(employee, policy):
                applicable.append({
                    'code': policy.pk, 'name': getattr(policy, 'name', str(policy)),
                    'leave_type': getattr(policy, 'leave_type', None),
                })
        return {'applicable_policies': applicable}

    @staticmethod
    def _employee_matches_policy(employee, policy) -> bool:
        """Read-only inspection of the EXISTING applicable_* JSON lists —
        empty list conventionally means "no restriction" for that
        dimension, matching how this codebase's other applicable_* JSON
        fields are already read elsewhere (same convention noted in
        docs/MIGRATION_PLAN.md for LeavePolicy)."""
        list_checks = [
            ('applicable_branches', getattr(employee, 'branch_id', None)),
            ('applicable_employment_types', getattr(employee, 'employee_type', None)),
        ]
        for field_name, employee_value in list_checks:
            values = getattr(policy, field_name, None)
            if values and employee_value is not None and str(employee_value) not in [str(v) for v in values]:
                return False

        # applicable_gender is a single CharField (not a list, unlike the
        # others above) with 'all' meaning no restriction.
        policy_gender = getattr(policy, 'applicable_gender', 'all')
        employee_gender = getattr(getattr(employee, 'profile', None), 'gender', None)
        if policy_gender and policy_gender != 'all' and employee_gender is not None and str(employee_gender) != str(policy_gender):
            return False
        return True
