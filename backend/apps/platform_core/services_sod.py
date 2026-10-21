"""Phase 4 Task F — segregation of duties."""
from __future__ import annotations

from apps.platform_core.models import SoDRule, SoDViolationLog


class SoDBlockedError(Exception):
    def __init__(self, message: str, rule: SoDRule):
        self.message = message
        self.rule = rule
        super().__init__(message)


def _user_codenames(user, *, including: set[str] | None = None) -> set[str]:
    from apps.accounts.models import RolePermission
    from core.permissions import effective_permission_codenames
    codenames = set(effective_permission_codenames(user))
    from apps.platform_core.models import RoleAssignment
    for assignment in RoleAssignment.objects.filter(user=user, is_active=True).select_related('role'):
        codenames.update(RolePermission.objects.filter(role=assignment.role).values_list('permission__codename', flat=True))
    if including:
        codenames |= including
    return codenames


def check(user, *, additional_codenames: set[str] | None = None, reason: str = '', actor=None) -> list[dict]:
    """Task F.2 — checked on granting a permission / assigning a role /
    creating a delegation. Returns a list of {rule, severity} dicts for
    every active SoDRule violated; raises SoDBlockedError for the FIRST
    block-severity violation (a block must stop the action outright —
    never just one of several). Warn-severity violations require
    `reason` and are logged but do not raise."""
    codenames = _user_codenames(user, including=additional_codenames)
    violations = []
    for rule in SoDRule.objects.filter(is_active=True):
        set_a = set(rule.conflicting_permissions_a)
        set_b = set(rule.conflicting_permissions_b)
        if (codenames & set_a) and (codenames & set_b):
            violations.append(rule)

    for rule in violations:
        if rule.severity == SoDRule.SEVERITY_BLOCK:
            SoDViolationLog.objects.create(rule=rule, user=user, was_blocked=True)
            raise SoDBlockedError(f'This action is blocked by segregation-of-duties rule "{rule.code}": {rule.description}', rule)

    for rule in violations:
        if rule.severity == SoDRule.SEVERITY_WARN:
            if not reason:
                raise SoDBlockedError(f'Segregation-of-duties rule "{rule.code}" requires a reason to proceed: {rule.description}', rule)
            SoDViolationLog.objects.create(rule=rule, user=user, was_blocked=False, reason=reason)

    return [{'rule': r.code, 'severity': r.severity} for r in violations]


def existing_violations_report() -> list[dict]:
    """Task F.4 — report of existing violations at any point in time;
    never auto-removes anything."""
    from apps.accounts.models import User
    report = []
    for rule in SoDRule.objects.filter(is_active=True):
        set_a, set_b = set(rule.conflicting_permissions_a), set(rule.conflicting_permissions_b)
        for user in User.objects.filter(is_active=True).select_related('role'):
            codenames = _user_codenames(user)
            if (codenames & set_a) and (codenames & set_b):
                report.append({'rule': rule.code, 'user_id': str(user.pk), 'severity': rule.severity})
    return report


SUGGESTED_RULES = [
    {
        'code': 'payroll_create_vs_approve', 'severity': SoDRule.SEVERITY_WARN,
        'description': 'Creating/running a payroll cycle and approving it should not be the same person.',
        'conflicting_permissions_a': ['payroll.create'], 'conflicting_permissions_b': ['payroll.edit'],
    },
    {
        'code': 'expense_create_vs_approve', 'severity': SoDRule.SEVERITY_WARN,
        'description': 'Creating an expense claim and approving expenses for the same scope should not be the same person.',
        'conflicting_permissions_a': ['expenses.approve'], 'conflicting_permissions_b': ['expenses.approve'],
    },
    {
        'code': 'edit_bank_details_vs_approve_payroll', 'severity': SoDRule.SEVERITY_BLOCK,
        'description': 'A user who can edit employee bank details should not also approve payroll (direct fraud vector).',
        'conflicting_permissions_a': ['employees.edit'], 'conflicting_permissions_b': ['payroll.edit'],
    },
    {
        'code': 'manage_roles_vs_approve_own_access',
        'severity': SoDRule.SEVERITY_WARN,
        'description': 'A user who manages roles should not also be the sole approver of their own access changes.',
        'conflicting_permissions_a': ['roles.manage'], 'conflicting_permissions_b': ['roles.manage'],
    },
]


def seed_suggested_rules() -> dict:
    """Task F.3 — seeded as SUGGESTIONS (is_suggestion=True, is_active=
    False) pending owner confirmation; never auto-activated."""
    created = unchanged = 0
    for spec in SUGGESTED_RULES:
        _, was_created = SoDRule.objects.get_or_create(
            code=spec['code'],
            defaults={
                'description': spec['description'], 'severity': spec['severity'],
                'conflicting_permissions_a': spec['conflicting_permissions_a'],
                'conflicting_permissions_b': spec['conflicting_permissions_b'],
                'is_suggestion': True, 'is_active': False,
            },
        )
        created += was_created
        unchanged += not was_created
    return {'created': created, 'unchanged': unchanged}
