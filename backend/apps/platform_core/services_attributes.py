"""
Phase 2 Task C.4 — custom attribute storage service. One place every
caller (generic data API, import/export, forms) goes through to
validate/save/read custom field values on a core entity's record — never
direct JSONB manipulation, so uniqueness/masking/applicability stay
correct regardless of caller.

Employee entity design note (Task A.3's "design and document how"):
User itself has no JSONB column — EmployeeProfile (a separate table,
OneToOne to User via `related_name='profile'`) already has
`custom_field_values`. Rather than adding a SECOND attributes column on
User (which would split one employee's custom data across two places)
or moving EmployeeProfile's existing data (explicitly forbidden — Master
Prompt rule: never move/rename custom_field_values), the employee
EntityDefinition's `attributes_column` is the dotted path
`"profile__custom_field_values"`. `_get_attributes_container`/
`_set_attributes_container` below special-case any dotted path by
walking the relation; every other entity's `attributes_column` is a
plain column name on the record itself.
"""
from __future__ import annotations

import hashlib

from django.core.exceptions import ObjectDoesNotExist
from django.db import transaction

from apps.platform_core import services_conditions as conditions
from apps.platform_core import services_datatypes as datatypes
from apps.platform_core.models import FieldDefinition, FieldValueUniqueness


class AttributeValidationError(Exception):
    def __init__(self, errors: dict):
        self.errors = errors
        super().__init__(str(errors))


def _get_attributes_container(record, attributes_column: str):
    """Returns (owner_object, column_name) — owner_object.column_name is
    the actual dict to read/write. Walks a dotted path (the employee
    entity's "profile__custom_field_values") one hop at a time; Phase 2
    only ever needs one hop in practice, but this isn't hardcoded to
    exactly one."""
    parts = attributes_column.split('__')
    owner = record
    for part in parts[:-1]:
        owner = getattr(owner, part)
    return owner, parts[-1]


def _applicable_fields(entity_def, *, country=None, legal_entity=None, employment_type=None):
    fields = FieldDefinition.objects.filter(entity=entity_def, status=FieldDefinition.STATUS_PUBLISHED)
    result = []
    for f in fields:
        app = f.applicability or {}
        if app.get('countries') and country and getattr(country, 'iso2', country) not in app['countries']:
            continue
        if app.get('legal_entities') and legal_entity and str(getattr(legal_entity, 'pk', legal_entity)) not in [str(x) for x in app['legal_entities']]:
            continue
        if app.get('employment_types') and employment_type and employment_type not in app['employment_types']:
            continue
        result.append(f)
    return result


def _mask(field_def, value):
    if value is None:
        return None
    fingerprint = hashlib.sha256(str(value).encode('utf-8')).hexdigest()[:8]
    return f'***{fingerprint}'


def validate(entity_def, record, values: dict, *, partial: bool = False, context: dict | None = None) -> dict:
    """Validates+normalises `values` (field_code -> raw value) against
    every applicable, published field on `entity_def`. Returns the
    cleaned dict on success; raises AttributeValidationError(field_code
    -> message) otherwise. `partial=True` (PATCH semantics) skips the
    required-field check for fields simply absent from `values`."""
    context = context or {}
    applicable = _applicable_fields(entity_def, **context)
    applicable_by_code = {f.code: f for f in applicable}

    unknown = set(values) - set(applicable_by_code)
    errors = {code: 'This field does not exist or is not currently applicable.' for code in unknown}

    cleaned = {}
    existing_values = read(entity_def, record, for_user=None, _skip_mask=True) if record is not None else {}
    merged_for_conditions = {**existing_values, **values}

    for field_def in applicable:
        code = field_def.code
        has_value = code in values
        required_when = field_def.validation.get('required_when') or {}
        # An EMPTY required_when means "no additional condition" (i.e. it
        # contributes nothing), not "always required" — conditions.evaluate
        # returns True for an empty dict because THAT function's contract is
        # "empty means always visible/active", which is the right default
        # for visible_when but the wrong one here, so it's only consulted
        # when a real condition is actually configured.
        is_required = field_def.required or (bool(required_when) and conditions.evaluate(required_when, merged_for_conditions))

        if not has_value:
            if partial:
                continue
            if is_required:
                errors[code] = 'This field is required.'
            continue

        value = values[code]
        if value in (None, ''):
            if is_required:
                errors[code] = 'This field is required.'
            else:
                cleaned[code] = value
            continue

        try:
            cleaned[code] = datatypes.validate_and_normalise(field_def, value)
        except datatypes.DataTypeError as exc:
            errors[code] = exc.message

    if errors:
        raise AttributeValidationError(errors)
    return cleaned


def _uniqueness_scope_key(field_def, record, legal_entity) -> str:
    if field_def.unique_scope == FieldDefinition.UNIQUE_SCOPE_LEGAL_ENTITY:
        return str(getattr(legal_entity, 'pk', legal_entity) or '')
    if field_def.unique_scope == FieldDefinition.UNIQUE_SCOPE_PARENT:
        parent_id = getattr(record, 'parent_object_id', None)
        return str(parent_id or '')
    return ''


def _check_and_record_uniqueness(entity_def, record, cleaned: dict, applicable_by_code: dict, *, legal_entity=None):
    for code, value in cleaned.items():
        field_def = applicable_by_code.get(code)
        if field_def is None or not field_def.is_unique or value in (None, ''):
            continue
        value_hash = hashlib.sha256(str(value).encode('utf-8')).hexdigest()
        scope_key = _uniqueness_scope_key(field_def, record, legal_entity)
        record_id = str(record.pk)
        existing = FieldValueUniqueness.objects.filter(
            entity=entity_def, field=field_def, scope_key=scope_key, value_hash=value_hash,
        ).exclude(record_id=record_id).first()
        if existing:
            raise AttributeValidationError({code: 'This value is already in use.'})
        FieldValueUniqueness.objects.update_or_create(
            entity=entity_def, field=field_def, scope_key=scope_key, value_hash=value_hash,
            defaults={'record_id': record_id},
        )


@transaction.atomic
def save(entity_def, record, values: dict, *, partial: bool = False, context: dict | None = None, actor=None) -> dict:
    applicable = _applicable_fields(entity_def, **(context or {}))
    applicable_by_code = {f.code: f for f in applicable}

    cleaned = validate(entity_def, record, values, partial=partial, context=context)

    owner, column = _get_attributes_container(record, entity_def.attributes_column)
    current = dict(getattr(owner, column) or {})

    legal_entity = (context or {}).get('legal_entity')
    _check_and_record_uniqueness(entity_def, record, cleaned, applicable_by_code, legal_entity=legal_entity)

    # Sensitive values are stored encrypted (Phase 1's own encryption
    # service) rather than in clear — reusing the exact same Fernet
    # service apps.accounts.core.encrypted_fields already wraps, not a
    # second encryption implementation.
    from core.encrypted_fields import _fernet
    for code, value in cleaned.items():
        field_def = applicable_by_code.get(code)
        if field_def and field_def.is_sensitive and value not in (None, ''):
            current[code] = {'__encrypted__': _fernet().encrypt(str(value).encode('utf-8')).decode('ascii')}
        else:
            current[code] = value

    setattr(owner, column, current)
    owner.save(update_fields=[column])

    # Logged explicitly here, not via history.py's generic per-model
    # registry — attribute changes live inside a JSON blob on another
    # model (e.g. EmployeeProfile for the employee entity), not as a
    # real column on `record` itself, so the generic pre_save diff
    # mechanism has nothing to compare against.
    _log_attribute_change(entity_def, record, cleaned, actor)

    return read(entity_def, record, for_user=actor)


def _log_attribute_change(entity_def, record, cleaned: dict, actor):
    from django.contrib.contenttypes.models import ContentType
    from apps.platform_core.models import ChangeHistory
    from apps.platform_core import request_context

    if not cleaned:
        return
    ctx = request_context.get_context()
    changes = [{'field': code, 'old': None, 'new': ('***' if _is_sensitive_code(entity_def, code) else value)} for code, value in cleaned.items()]
    ChangeHistory.objects.create(
        actor_id=getattr(actor, 'pk', None) or ctx.actor_id,
        channel=ctx.channel, request_id=ctx.request_id, ip_address=ctx.ip_address, user_agent=ctx.user_agent,
        content_type=ContentType.objects.get_for_model(type(record)),
        object_id=str(record.pk), object_repr=str(record)[:200],
        action=ChangeHistory.ACTION_UPDATE, changes=changes, legal_entity=None,
    )


def _is_sensitive_code(entity_def, code: str) -> bool:
    return FieldDefinition.objects.filter(entity=entity_def, code=code, is_sensitive=True).exists()


def read(entity_def, record, *, for_user, _skip_mask: bool = False) -> dict:
    """Archived fields are excluded. Sensitive values are masked unless
    for_user holds employees.view_sensitive (reusing the existing
    permission — Phase 2 introduces no new sensitive-view permission)."""
    owner, column = _get_attributes_container(record, entity_def.attributes_column)
    raw = dict(getattr(owner, column) or {})

    published_codes = set(FieldDefinition.objects.filter(entity=entity_def, status=FieldDefinition.STATUS_PUBLISHED).values_list('code', flat=True))
    sensitive_codes = set(FieldDefinition.objects.filter(entity=entity_def, is_sensitive=True).values_list('code', flat=True))

    can_view_sensitive = _skip_mask
    if for_user is not None and not _skip_mask:
        from core.permissions import has_perm
        can_view_sensitive = has_perm(for_user, 'employees.view_sensitive')

    from core.encrypted_fields import _fernet
    result = {}
    for code, value in raw.items():
        if code not in published_codes:
            continue  # archived/unknown — excluded from reads, data untouched in storage
        if code in sensitive_codes:
            if isinstance(value, dict) and '__encrypted__' in value:
                if can_view_sensitive or _skip_mask:
                    try:
                        value = _fernet().decrypt(value['__encrypted__'].encode('ascii')).decode('utf-8')
                    except Exception:
                        value = None
                else:
                    value = '***'
            elif not can_view_sensitive:
                value = '***'
        result[code] = value
    return result
