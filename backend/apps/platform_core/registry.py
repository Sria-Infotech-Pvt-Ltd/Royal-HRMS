"""
Phase 2 Task A — entity registry. Core entities are registered from CODE
(here, at import time of each app's own registrations — see
`sync_entity_registry` management command and apps.py hooks), then
synced into the `EntityDefinition` table so the rest of the engine
(fields, layouts, attributes) has one place to look regardless of
whether an entity is core or custom.
"""
from __future__ import annotations

_CORE_ENTITY_REGISTRATIONS: list[dict] = []


def register_entity(*, code: str, label: str, app_label: str, model_name: str,
                     attributes_column: str, module: str = '', plural_label: str = '',
                     legal_entity_scoped: bool = False, owner_field: str = ''):
    """Called once per core entity, typically from an AppConfig.ready().
    Does NOT touch the database — see sync_entity_registry for that, so
    this stays safe to call at import time."""
    _CORE_ENTITY_REGISTRATIONS.append({
        'code': code, 'label': label, 'plural_label': plural_label or f'{label}s',
        'module': module, 'app_label': app_label, 'model_name': model_name,
        'attributes_column': attributes_column, 'legal_entity_scoped': legal_entity_scoped,
        'owner_field': owner_field,
    })


def get_core_registrations() -> list[dict]:
    return list(_CORE_ENTITY_REGISTRATIONS)


def register_builtin_core_entities():
    """The 6 entities Phase 2 registers (Task A.3). Idempotent — safe to
    call more than once (e.g. once per test run) since register_entity
    just appends to a list and sync_entity_registry itself is the
    idempotent, DB-touching half."""
    register_entity(
        code='employee', label='Employee', plural_label='Employees', module='accounts',
        app_label='accounts', model_name='User', attributes_column='profile__custom_field_values',
        legal_entity_scoped=False, owner_field='',
    )
    register_entity(
        code='branch', label='Branch', module='branch',
        app_label='branch', model_name='Branch', attributes_column='attributes',
    )
    register_entity(
        code='org_unit', label='Org Unit', module='accounts',
        app_label='accounts', model_name='OrgUnit', attributes_column='attributes',
    )
    register_entity(
        code='position', label='Position', module='accounts',
        app_label='accounts', model_name='Position', attributes_column='attributes',
    )
    register_entity(
        code='legal_entity', label='Legal Entity', module='platform_core',
        app_label='platform_core', model_name='LegalEntity', attributes_column='attributes',
    )
    register_entity(
        code='candidate', label='Candidate', module='recruitment',
        app_label='recruitment', model_name='Candidate', attributes_column='attributes',
    )
