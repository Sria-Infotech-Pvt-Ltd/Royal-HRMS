"""Phase 2 Task E — custom object CRUD + lifecycle.

No runtime DDL anywhere in this file: every custom entity's records
live in the single `CustomRecord` table (entity FK + JSONB `data`).
Publishing a draft `EntityDefinition` of kind=custom creates the
Django Permission rows other custom entities will be gated by —
reusing the existing `core.permissions.has_perm` check, not a new
authorization mechanism.
"""
from __future__ import annotations

import re

from django.contrib.contenttypes.models import ContentType
from django.db import transaction

from apps.accounts.models import Permission
from apps.platform_core import services_attributes as attrs
from apps.platform_core.models import CustomRecord, EntityDefinition, FieldDefinition

PERMISSION_ACTIONS = ['view', 'add', 'change', 'delete']


def permission_codename(entity_code: str, action: str) -> str:
    """This codebase's own permission system (apps.accounts.models.Permission
    + core.permissions.has_perm) is "module.action" codenames checked
    against a user's Role — NOT Django's built-in auth Permission app,
    which has_perm() never looks at. Every caller that needs to check a
    custom entity's permission (views_meta.py, future import/export)
    must go through this helper rather than hand-building the string."""
    return f'custom_{entity_code}.{action}'


class CustomObjectError(Exception):
    def __init__(self, message, errors=None):
        super().__init__(message)
        self.message = message
        self.errors = errors or {}


_TEMPLATE_TOKEN_RE = re.compile(r'\{([a-z0-9_]+)\}')


def publish_entity(entity: EntityDefinition, *, actor=None) -> EntityDefinition:
    """Task E.2 — draft -> published transition for a CUSTOM entity.
    Creates the view/add/change/delete Permission rows for this entity's
    CustomRecord content type, scoped by entity code (so permissions for
    one custom entity never grant access to another's records), and
    flips status. Idempotent — safe to call on an already-published
    entity (get_or_create, no duplicate permissions)."""
    if entity.kind != EntityDefinition.KIND_CUSTOM:
        raise CustomObjectError('Only custom entities can be published through this service.')

    for action in PERMISSION_ACTIONS:
        Permission.objects.get_or_create(
            codename=permission_codename(entity.code, action),
            defaults={'module': f'custom_{entity.code}', 'action': action},
        )

    entity.status = EntityDefinition.STATUS_PUBLISHED
    entity.save(update_fields=['status', 'updated_at'])
    return entity


def _render_title(entity: EntityDefinition, data: dict) -> str:
    template = entity.title_template or ''
    if not template:
        return ''
    return _TEMPLATE_TOKEN_RE.sub(lambda m: str(data.get(m.group(1), '')), template)


@transaction.atomic
def create_record(entity: EntityDefinition, values: dict, *, actor=None, legal_entity=None, parent=None) -> CustomRecord:
    if entity.kind != EntityDefinition.KIND_CUSTOM:
        raise CustomObjectError('Not a custom entity.')
    record = CustomRecord(entity=entity, legal_entity=legal_entity, created_by=actor, updated_by=actor)
    if parent is not None:
        record.parent_content_type = ContentType.objects.get_for_model(parent)
        record.parent_object_id = str(parent.pk)
    record.save()  # need a pk before uniqueness-scope checks in services_attributes

    try:
        attrs.save(entity, record, values, partial=False, actor=actor)
    except attrs.AttributeValidationError:
        record.delete()
        raise

    record.refresh_from_db()
    record.title = _render_title(entity, record.data)
    record.save(update_fields=['title'])
    return record


@transaction.atomic
def update_record(record: CustomRecord, values: dict, *, actor=None, partial=True) -> CustomRecord:
    entity = record.entity
    attrs.save(entity, record, values, partial=partial, actor=actor)
    record.refresh_from_db()
    record.title = _render_title(entity, record.data)
    record.updated_by = actor
    record.save(update_fields=['title', 'updated_by', 'updated_at'])
    return record


def soft_delete_record(record: CustomRecord, *, actor=None) -> None:
    record.is_deleted = True
    record.updated_by = actor
    record.save(update_fields=['is_deleted', 'updated_by', 'updated_at'])


def read_record(record: CustomRecord, *, for_user=None) -> dict:
    return attrs.read(record.entity, record, for_user=for_user)


def list_records(entity: EntityDefinition, *, legal_entity=None, parent=None, include_deleted=False):
    qs = CustomRecord.objects.filter(entity=entity)
    if not include_deleted:
        qs = qs.filter(is_deleted=False)
    if legal_entity is not None:
        qs = qs.filter(legal_entity=legal_entity)
    if parent is not None:
        qs = qs.filter(
            parent_content_type=ContentType.objects.get_for_model(parent),
            parent_object_id=str(parent.pk),
        )
    return qs
