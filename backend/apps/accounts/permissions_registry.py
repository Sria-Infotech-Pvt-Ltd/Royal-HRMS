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


def sync() -> dict:
    entity = generate_entity_permissions()
    code = sync_code_defined_permissions()
    return {'created': entity['created'] + code['created'], 'unchanged': entity['unchanged'] + code['unchanged']}
