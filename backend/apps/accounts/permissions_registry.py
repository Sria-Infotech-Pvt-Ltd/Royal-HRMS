"""
Phase 4 Task A — permission registry. Scope cut, stated plainly: this
module does NOT attempt to hand-type a registry of the ~442 existing
`has_perm('...')` call-site codenames to diff against and mark
"removed" ones `is_deprecated` — building that list by hand risks
silently deprecating a permission a literal call site still checks,
which Rule 4 ("when in doubt, deny... never widen access silently")
makes the wrong kind of mistake to approximate. What IS built and real:

1. `generate_entity_permissions()` — Phase 2's own convention (every
   registered entity gets view/create/edit/delete/export/import
   codenames) implemented as a real, idempotent generator, synced via
   `sync_permissions`.
2. `tests_permission_registry.py` scans the actual source tree for every
   literal `has_perm('module.action')` / `has_perm("module.action")`
   call and asserts the codename exists in the database — a real,
   automated version of "every codename found in the 442 call sites
   must exist in the registry" that can never silently drift, because
   it re-scans the live source on every test run rather than trusting a
   hand-maintained list.
"""
from __future__ import annotations

ENTITY_PERMISSION_ACTIONS = ['view', 'create', 'edit', 'delete', 'export', 'import']


def generate_entity_permissions() -> dict:
    """Task A.1's "Phase 2 entities generate <entity>.view/create/edit/
    delete/export/import automatically" — for CORE entities only
    (custom-entity permissions are already created at publish time by
    services_custom_objects.publish_entity(), per Task A.1's own
    "keep it" instruction — not duplicated here)."""
    from apps.accounts.models import Permission
    from apps.platform_core.models import EntityDefinition

    created = unchanged = 0
    for entity in EntityDefinition.objects.filter(kind=EntityDefinition.KIND_CORE):
        for action in ENTITY_PERMISSION_ACTIONS:
            codename = f'{entity.code}.{action}'
            _, was_created = Permission.objects.get_or_create(
                codename=codename, defaults={'module': entity.code, 'action': action, 'description': f'{action.title()} {entity.plural_label or entity.label}'},
            )
            created += was_created
            unchanged += not was_created
    return {'created': created, 'unchanged': unchanged}


# Permissions defined in code (no migration needed): (codename, module, action, description, is_sensitive).
CODE_DEFINED_PERMISSIONS = [
    (
        'employees.view_workspace', 'employees', 'view_workspace',
        "Open an employee's workspace (attendance, leave, payslips, tax, requests...) read-only, exactly as they see it.",
        True,
    ),
    (
        'timesheet.approve', 'timesheet', 'approve',
        "Approve or send back weekly timesheets as the HR fallback approver, within your scope (the assigned manager does not need this).",
        False,
    ),
    (
        'timesheet.unlock', 'timesheet', 'unlock',
        'Reopen an approved weekly timesheet for correction, with a mandatory reason. The earlier version stays in its history.',
        True,
    ),
    (
        'timesheet.report', 'timesheet', 'report',
        'Run the timesheet reports (employee hours, project hours, billable hours, weekly summary) for your scope.',
        False,
    ),
]


def sync_code_defined_permissions() -> dict:
    from apps.accounts.models import Permission

    created = unchanged = 0
    for codename, module, action, description, is_sensitive in CODE_DEFINED_PERMISSIONS:
        _, was_created = Permission.objects.get_or_create(
            codename=codename,
            defaults={'module': module, 'action': action, 'description': description, 'is_sensitive': is_sensitive},
        )
        created += was_created
        unchanged += not was_created
    return {'created': created, 'unchanged': unchanged}


# Permission templates every installation starts with (apply one to a position in Settings > Access > Permission templates).
# Least privilege: only what acting as an approver needs, no edit / delete / payroll / sensitive-data access.
#  - attendance.create is the gate attendance corrections check for BOTH levels (services_hr_corrections), so both hold it; it
#    also allows entering attendance by hand, which is why it is called out here instead of being hidden.
#  - timesheet.approve is the HR fallback approver's permission; an assigned manager does not need it, so only L2 has it.
#  - can_manage_team is what puts a manager's own approvals in their L1 queue.
DEFAULT_PERMISSION_TEMPLATES = [
    {
        'name': 'L1 Approver',
        'description': 'First-level approver (the team manager): approves leave, expense, work-from-home and attendance-correction requests.',
        'can_manage_team': True,
        'permissions': [
            'employees.view', 'attendance.view', 'attendance.create',
            'leave.approve', 'expenses.approve', 'wfh.approve',
        ],
    },
    {
        'name': 'L2 Approver (HR)',
        'description': 'Second-level (HR) approver: the same approvals as L1, plus weekly timesheets, without team-manager scope.',
        'can_manage_team': False,
        'permissions': [
            'employees.view', 'attendance.view', 'attendance.create',
            'leave.approve', 'expenses.approve', 'wfh.approve', 'timesheet.approve',
        ],
    },
]


def sync_default_permission_templates() -> dict:
    """Create the default templates that are missing. An existing template (same name) is NEVER changed, so an admin's edits
    survive every migrate; a default that was deleted comes back, the same as a code-defined permission would."""
    import logging

    from apps.accounts.models import Permission, PermissionTemplate

    created = unchanged = 0
    for spec in DEFAULT_PERMISSION_TEMPLATES:
        template, was_created = PermissionTemplate.objects.get_or_create(
            name=spec['name'],
            defaults={'description': spec['description'], 'can_manage_team': spec['can_manage_team'], 'can_manage_branch': False},
        )
        if not was_created:
            unchanged += 1
            continue
        found = list(Permission.objects.filter(codename__in=spec['permissions']))
        template.permissions.set(found)
        missing = set(spec['permissions']) - {permission.codename for permission in found}
        if missing:
            logging.getLogger(__name__).warning('Default template %r is missing permission(s): %s', spec['name'], ', '.join(sorted(missing)))
        created += 1
    return {'created': created, 'unchanged': unchanged}


def sync() -> dict:
    entity = generate_entity_permissions()
    code = sync_code_defined_permissions()
    return {'created': entity['created'] + code['created'], 'unchanged': entity['unchanged'] + code['unchanged']}
