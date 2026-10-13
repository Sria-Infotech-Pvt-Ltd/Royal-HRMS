"""
Phase 9A Task H — configuration transport: registry, export, dry-run
diff, conflict detection, atomic apply, rollback.

CORE_REGISTRY registers a real, small, proven subset (PayComponent,
RatingScale) rather than every configuration model in this codebase — see
models/transport.py's own docstring for why. seed_registry() writes these
into ConfigObjectType rows so the mechanism is driven by real DB data, not
a hardcoded dict at runtime (an admin could add more types the same way).
"""
import hashlib
import hmac
import importlib

from django.apps import apps as django_apps
from django.conf import settings
from django.db import transaction

from apps.platform_core.models import ConfigApplySnapshot, ConfigObjectType, ConfigPackage

# code -> (app_label, model_name, natural_key_fields, excluded_field_names, depends_on_type_codes)
CORE_REGISTRY = {
    'PAY_COMPONENT':  ('payroll', 'PayComponent', ['code'], [], []),
    'RATING_SCALE':   ('performance', 'RatingScale', ['code'], [], []),
}

# Field-name substrings that must NEVER appear on a registered model —
# the automated "no personal data" guard Task H.1 requires.
_FORBIDDEN_FIELD_SUBSTRINGS = [
    'ssn', 'aadhaar', 'pan_number', 'salary', 'bank_account', 'account_number',
    'phone', 'email', 'address', 'date_of_birth', 'passport',
]


class PersonalDataInRegistryError(Exception):
    pass


class TransportConflictError(Exception):
    pass


class SignatureInvalidError(Exception):
    pass


def assert_no_personal_data(model) -> None:
    for field in model._meta.get_fields():
        field_name = getattr(field, 'name', '').lower()
        for forbidden in _FORBIDDEN_FIELD_SUBSTRINGS:
            if forbidden in field_name:
                raise PersonalDataInRegistryError(
                    f'{model.__name__}.{field.name} looks like personal/business data '
                    f'({forbidden!r}) — must not be registered for config transport.'
                )


def seed_registry() -> list:
    created = []
    for code, (app_label, model_name, natural_key_fields, excluded, depends_on) in CORE_REGISTRY.items():
        model = django_apps.get_model(app_label, model_name)
        assert_no_personal_data(model)
        obj_type, _ = ConfigObjectType.objects.update_or_create(
            code=code,
            defaults={
                'app_label': app_label, 'model_name': model_name, 'natural_key_fields': natural_key_fields,
                'excluded_field_names': excluded, 'depends_on_type_codes': depends_on,
            },
        )
        created.append(obj_type)
    return created


def _get_model(obj_type: ConfigObjectType):
    return django_apps.get_model(obj_type.app_label, obj_type.model_name)


def _natural_key_dict(instance, obj_type: ConfigObjectType) -> dict:
    return {f: getattr(instance, f) for f in obj_type.natural_key_fields}


def _serialize_field_value(field, value):
    """JSON-serializable round-trip-safe form for storing in
    ConfigPackage.contents (itself a JSONField) — Decimal/date become
    strings (restored by type on apply via _deserialize_field_value());
    JSONField/BooleanField/plain scalars are already JSON-safe and kept
    as-is, NEVER stringified (stringifying a list/dict would corrupt it
    on the way back in)."""
    if value is None:
        return None
    internal_type = field.get_internal_type()
    if internal_type == 'JSONField':
        return value
    if internal_type in ('DecimalField', 'DateField', 'DateTimeField', 'UUIDField'):
        return str(value)
    return value


def _deserialize_field_value(field, value):
    if value is None:
        return None
    internal_type = field.get_internal_type()
    if internal_type == 'DecimalField':
        from decimal import Decimal
        return Decimal(value)
    if internal_type == 'DateField':
        import datetime
        return datetime.date.fromisoformat(value)
    if internal_type == 'DateTimeField':
        from django.utils.dateparse import parse_datetime
        return parse_datetime(value)
    return value


def _field_values(instance, obj_type: ConfigObjectType) -> dict:
    excluded = set(obj_type.excluded_field_names) | set(obj_type.natural_key_fields) | {'id'}
    values = {}
    for field in instance._meta.get_fields():
        if not hasattr(field, 'attname') or field.name in excluded:
            continue
        if field.is_relation:
            continue  # FK config dependencies are resolved via depends_on_type_codes, not auto-serialized here
        raw_value = getattr(instance, field.attname, None)
        values[field.name] = _serialize_field_value(field, raw_value)
    return values


def _content_hash(fields: dict) -> str:
    return hashlib.sha256(repr(sorted(fields.items())).encode('utf-8')).hexdigest()


@transaction.atomic
def export_package(name: str, type_codes: list, created_by, description: str = '') -> ConfigPackage:
    objects = []
    for type_code in type_codes:
        obj_type = ConfigObjectType.objects.get(code=type_code)
        model = _get_model(obj_type)
        for instance in model.objects.all():
            fields = _field_values(instance, obj_type)
            objects.append({
                'type_code': type_code,
                'natural_key': _natural_key_dict(instance, obj_type),
                'fields': fields,
                'content_hash': _content_hash(fields),
            })

    contents = {'format_version': 1, 'objects': objects}
    package = ConfigPackage.objects.create(
        name=name, description=description, created_by=created_by,
        contents=contents, status=ConfigPackage.STATUS_EXPORTED,
    )
    package.checksum_sha256 = hashlib.sha256(repr(contents).encode('utf-8')).hexdigest()
    package.hmac_signature = _sign(contents)
    package.save(update_fields=['checksum_sha256', 'hmac_signature'])
    return package


def _transport_key() -> bytes:
    key = getattr(settings, 'CONFIG_TRANSPORT_KEY', None) or 'dev-only-insecure-transport-key'
    return key.encode('utf-8')


def _sign(contents: dict) -> str:
    return hmac.new(_transport_key(), repr(contents).encode('utf-8'), hashlib.sha256).hexdigest()


def verify_signature(package: ConfigPackage) -> bool:
    return hmac.compare_digest(package.hmac_signature, _sign(package.contents))


def dry_run_diff(package: ConfigPackage) -> dict:
    """Returns {'create': [...], 'update': [...], 'unchanged': [...], 'conflict': [...]}
    — never writes anything."""
    if not verify_signature(package):
        raise SignatureInvalidError(f'Package {package.id} failed signature verification — refusing to diff.')

    result = {'create': [], 'update': [], 'unchanged': [], 'conflict': []}
    for obj in package.contents['objects']:
        obj_type = ConfigObjectType.objects.get(code=obj['type_code'])
        model = _get_model(obj_type)
        lookup = {k: v for k, v in obj['natural_key'].items()}
        existing = model.objects.filter(**lookup).first()

        if existing is None:
            result['create'].append(obj)
            continue

        existing_fields = _field_values(existing, obj_type)
        existing_hash = _content_hash(existing_fields)
        if existing_hash == obj['content_hash']:
            result['unchanged'].append(obj)
        else:
            result['update'].append({**obj, 'target_fields': existing_fields})
    return result


@transaction.atomic
def apply_package(package: ConfigPackage, *, resolve_conflicts: dict | None = None) -> list:
    """Atomic, in dependency order (natural_key-based upsert). Every
    touched object gets a ConfigApplySnapshot BEFORE it's changed, so
    rollback_package() can restore it exactly."""
    if package.status != ConfigPackage.STATUS_APPROVED:
        raise ValueError(f'Package {package.id} is {package.status}, not approved — cannot apply.')
    if not verify_signature(package):
        raise SignatureInvalidError(f'Package {package.id} failed signature verification — refusing to apply.')

    resolve_conflicts = resolve_conflicts or {}
    diff = dry_run_diff(package)

    type_order = sorted(
        {o['type_code'] for o in package.contents['objects']},
        key=lambda code: len(ConfigObjectType.objects.get(code=code).depends_on_type_codes),
    )

    snapshots = []
    for type_code in type_order:
        for obj in [o for o in package.contents['objects'] if o['type_code'] == type_code]:
            obj_type = ConfigObjectType.objects.get(code=type_code)
            model = _get_model(obj_type)
            existing = model.objects.filter(**obj['natural_key']).first()

            if existing is not None:
                existing_hash = _content_hash(_field_values(existing, obj_type))
                if existing_hash != obj['content_hash']:
                    key = f"{type_code}:{obj['natural_key']}"
                    resolution = resolve_conflicts.get(key, 'take_package')
                    if resolution == 'abort':
                        raise TransportConflictError(f'Unresolved conflict on {key}.')
                    if resolution == 'keep_target':
                        continue

            was_created = existing is None
            previous_values = None if was_created else _field_values(existing, obj_type)
            instance = existing or model(**obj['natural_key'])
            fields_by_name = {f.name: f for f in model._meta.get_fields() if hasattr(f, 'attname')}
            for field_name, value in obj['fields'].items():
                setattr(instance, field_name, _deserialize_field_value(fields_by_name[field_name], value))
            instance.save()

            snapshot = ConfigApplySnapshot.objects.create(
                package=package, type_code=type_code, natural_key=obj['natural_key'],
                was_created=was_created, previous_field_values=previous_values, object_pk=str(instance.pk),
            )
            snapshots.append(snapshot)

    from django.utils import timezone
    package.status = ConfigPackage.STATUS_APPLIED
    package.applied_at = timezone.now()
    package.save(update_fields=['status', 'applied_at'])
    return snapshots


@transaction.atomic
def rollback_package(package: ConfigPackage) -> None:
    if package.status != ConfigPackage.STATUS_APPLIED:
        raise ValueError(f'Package {package.id} is {package.status}, not applied — nothing to roll back.')

    for snapshot in package.apply_snapshots.all().order_by('-id'):
        obj_type = ConfigObjectType.objects.get(code=snapshot.type_code)
        model = _get_model(obj_type)
        instance = model.objects.filter(**snapshot.natural_key).first()
        if instance is None:
            continue
        if snapshot.was_created:
            instance.delete()
        else:
            fields_by_name = {f.name: f for f in model._meta.get_fields() if hasattr(f, 'attname')}
            for field_name, value in (snapshot.previous_field_values or {}).items():
                setattr(instance, field_name, _deserialize_field_value(fields_by_name[field_name], value))
            instance.save()

    package.status = ConfigPackage.STATUS_ROLLED_BACK
    package.save(update_fields=['status'])
