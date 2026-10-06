"""
Phase 2 Task B.2/B.3 — one validator + one normaliser per data type, in a
registry, so adding a type later is one class (per the Master Prompt's
own instruction). Each entry raises `DataTypeError(field_code, message)`
on invalid input, or returns the normalised, JSON-storable value.

Declarative `validation` JSON options supported per type are documented
inline on each validator.
"""
from __future__ import annotations

import datetime
import re
from decimal import Decimal, InvalidOperation

_EMAIL_RE = re.compile(r'^[^\s@]+@[^\s@]+\.[^\s@]+$')
_URL_RE = re.compile(r'^https?://', re.IGNORECASE)
_E164_RE = re.compile(r'^\+[1-9]\d{6,14}$')
# A regex field can itself be attacker-influenced in theory (an admin
# writes a bad one) — length-capped rather than run through a timeout
# harness, which is simpler and sufficient for admin-authored patterns
# capped this short (no catastrophic-backtracking pattern fits in 200
# chars that isn't already obviously a typo).
_MAX_USER_REGEX_LENGTH = 200


class DataTypeError(Exception):
    def __init__(self, field_code: str, message: str):
        self.field_code = field_code
        self.message = message
        super().__init__(f'{field_code}: {message}')


def _require(condition: bool, field_code: str, message: str):
    if not condition:
        raise DataTypeError(field_code, message)


def _check_common_validation(field_code: str, value, validation: dict):
    regex = validation.get('regex')
    if regex and isinstance(value, str):
        _require(len(regex) <= _MAX_USER_REGEX_LENGTH, field_code, 'Configured pattern is too long.')
        try:
            compiled = re.compile(regex)
        except re.error as exc:
            raise DataTypeError(field_code, f'Field is misconfigured (invalid pattern): {exc}') from exc
        _require(bool(compiled.match(value)), field_code, 'Value does not match the required format.')


def _validate_text(field_code, value, validation, *, long=False):
    _require(isinstance(value, str), field_code, 'Must be text.')
    min_len = validation.get('min_length')
    max_len = validation.get('max_length')
    if min_len is not None:
        _require(len(value) >= min_len, field_code, f'Must be at least {min_len} characters.')
    if max_len is not None:
        _require(len(value) <= max_len, field_code, f'Must be at most {max_len} characters.')
    _check_common_validation(field_code, value, validation)
    return value.strip()


def _validate_rich_text(field_code, value, validation):
    _require(isinstance(value, str), field_code, 'Must be text.')
    # Server-side allow-list sanitisation — strips everything except a
    # small safe tag set, never trusts client-side sanitisation alone.
    import bleach
    allowed_tags = ['p', 'br', 'strong', 'em', 'u', 'ul', 'ol', 'li', 'a', 'h1', 'h2', 'h3']
    allowed_attrs = {'a': ['href', 'title']}
    return bleach.clean(value, tags=allowed_tags, attributes=allowed_attrs, strip=True)


def _validate_integer(field_code, value, validation):
    try:
        value = int(value)
    except (TypeError, ValueError):
        raise DataTypeError(field_code, 'Must be a whole number.')
    _min, _max = validation.get('min'), validation.get('max')
    if _min is not None:
        _require(value >= _min, field_code, f'Must be at least {_min}.')
    if _max is not None:
        _require(value <= _max, field_code, f'Must be at most {_max}.')
    return value


def _validate_decimal(field_code, value, validation):
    try:
        value = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        raise DataTypeError(field_code, 'Must be a number.')
    places = validation.get('decimal_places')
    if places is not None:
        value = value.quantize(Decimal(1).scaleb(-places))
    _min, _max = validation.get('min'), validation.get('max')
    if _min is not None:
        _require(value >= Decimal(str(_min)), field_code, f'Must be at least {_min}.')
    if _max is not None:
        _require(value <= Decimal(str(_max)), field_code, f'Must be at most {_max}.')
    return str(value)


def _validate_currency_amount(field_code, value, validation):
    _require(isinstance(value, dict) and 'amount' in value and 'currency' in value, field_code, 'Must be {"amount": ..., "currency": "XXX"}.')
    amount = _validate_decimal(field_code, value['amount'], validation)
    _require(isinstance(value['currency'], str) and len(value['currency']) == 3, field_code, 'Currency must be a 3-letter code.')
    return {'amount': amount, 'currency': value['currency'].upper()}


def _validate_percentage(field_code, value, validation):
    value = _validate_decimal(field_code, value, {**validation, 'min': validation.get('min', 0), 'max': validation.get('max', 100)})
    return value


def _validate_boolean(field_code, value, validation):
    if isinstance(value, bool):
        return value
    raise DataTypeError(field_code, 'Must be true or false.')


def _validate_date(field_code, value, validation):
    try:
        parsed = datetime.date.fromisoformat(value) if isinstance(value, str) else value
        _require(isinstance(parsed, datetime.date), field_code, 'Must be a date.')
    except ValueError:
        raise DataTypeError(field_code, 'Must be a valid date (YYYY-MM-DD).')

    if validation.get('not_future'):
        _require(parsed <= datetime.date.today(), field_code, 'Date cannot be in the future.')
    not_before = validation.get('not_before')
    if not_before:
        _require(parsed >= datetime.date.fromisoformat(not_before), field_code, f'Date cannot be before {not_before}.')
    min_age_years = validation.get('min_age_years')
    if min_age_years is not None:
        cutoff = datetime.date.today().replace(year=datetime.date.today().year - min_age_years)
        _require(parsed <= cutoff, field_code, f'Must indicate an age of at least {min_age_years} years.')
    return parsed.isoformat()


def _validate_datetime(field_code, value, validation):
    try:
        parsed = datetime.datetime.fromisoformat(value) if isinstance(value, str) else value
        _require(isinstance(parsed, datetime.datetime), field_code, 'Must be a date/time.')
    except ValueError:
        raise DataTypeError(field_code, 'Must be a valid ISO date/time.')
    # Stored UTC — naive input is assumed UTC rather than silently guessing
    # a timezone.
    if parsed.tzinfo is not None:
        parsed = parsed.astimezone(datetime.timezone.utc).replace(tzinfo=None)
    return parsed.isoformat() + 'Z'


def _validate_time(field_code, value, validation):
    try:
        parsed = datetime.time.fromisoformat(value) if isinstance(value, str) else value
        _require(isinstance(parsed, datetime.time), field_code, 'Must be a time.')
    except ValueError:
        raise DataTypeError(field_code, 'Must be a valid time (HH:MM[:SS]).')
    return parsed.isoformat()


def _validate_duration(field_code, value, validation):
    _require(isinstance(value, (int, float)) and value >= 0, field_code, 'Must be a non-negative number of minutes.')
    return int(value)


def _validate_email(field_code, value, validation):
    _require(isinstance(value, str), field_code, 'Must be a valid email address.')
    value = value.strip()
    _require(bool(_EMAIL_RE.match(value)), field_code, 'Must be a valid email address.')
    return value.lower()


def _validate_phone(field_code, value, validation):
    _require(isinstance(value, str) and bool(_E164_RE.match(value)), field_code, 'Must be a valid phone number in E.164 format (e.g. +919876543210).')
    return value


def _validate_url(field_code, value, validation):
    _require(isinstance(value, str) and bool(_URL_RE.match(value)), field_code, 'Must be a valid http(s) URL.')
    return value.strip()


def _validate_lookup(field_code, value, validation, *, field_def):
    from apps.platform_core import services_lookups as lookups
    if field_def.multiple:
        _require(isinstance(value, list), field_code, 'Must be a list of codes.')
        for code in value:
            _require(lookups.is_valid(field_def.lookup_type.code, code), field_code, f'"{code}" is not a valid option.')
        return value
    _require(lookups.is_valid(field_def.lookup_type.code, value), field_code, f'"{value}" is not a valid option.')
    return value


def _validate_reference(field_code, value, validation, *, field_def):
    from apps.platform_core.models import CustomRecord
    ids = value if isinstance(value, list) else [value]
    for record_id in ids:
        _require(CustomRecord.objects.filter(pk=record_id, is_deleted=False).exists(), field_code, f'Referenced record "{record_id}" does not exist.')
    return value if field_def.multiple else ids[0]


def _validate_user_reference(field_code, value, validation):
    from apps.accounts.models import User
    _require(User.objects.filter(pk=value).exists(), field_code, 'Referenced user does not exist.')
    return value


def _validate_json(field_code, value, validation):
    import json
    try:
        json.dumps(value)
    except (TypeError, ValueError):
        raise DataTypeError(field_code, 'Must be JSON-serializable.')
    return value


# file/image/geo_point are handled by services_attachments.py /
# dedicated geo validation, not this generic registry — they need
# multipart upload handling / lat-lng bounds respectively, not a simple
# value-in-value-out validator.
_VALIDATORS = {
    'text': lambda f, v, val, **kw: _validate_text(f, v, val),
    'long_text': lambda f, v, val, **kw: _validate_text(f, v, val, long=True),
    'rich_text': lambda f, v, val, **kw: _validate_rich_text(f, v, val),
    'integer': lambda f, v, val, **kw: _validate_integer(f, v, val),
    'decimal': lambda f, v, val, **kw: _validate_decimal(f, v, val),
    'currency_amount': lambda f, v, val, **kw: _validate_currency_amount(f, v, val),
    'percentage': lambda f, v, val, **kw: _validate_percentage(f, v, val),
    'boolean': lambda f, v, val, **kw: _validate_boolean(f, v, val),
    'date': lambda f, v, val, **kw: _validate_date(f, v, val),
    'datetime': lambda f, v, val, **kw: _validate_datetime(f, v, val),
    'time': lambda f, v, val, **kw: _validate_time(f, v, val),
    'duration': lambda f, v, val, **kw: _validate_duration(f, v, val),
    'email': lambda f, v, val, **kw: _validate_email(f, v, val),
    'phone': lambda f, v, val, **kw: _validate_phone(f, v, val),
    'url': lambda f, v, val, **kw: _validate_url(f, v, val),
    'lookup': lambda f, v, val, **kw: _validate_lookup(f, v, val, field_def=kw['field_def']),
    'reference': lambda f, v, val, **kw: _validate_reference(f, v, val, field_def=kw['field_def']),
    'user_reference': lambda f, v, val, **kw: _validate_user_reference(f, v, val),
    'json': lambda f, v, val, **kw: _validate_json(f, v, val),
}


def validate_and_normalise(field_def, value):
    """field_def: a FieldDefinition instance (or anything with .code,
    .data_type, .multiple, .lookup_type, .reference_entity)."""
    validator = _VALIDATORS.get(field_def.data_type)
    if validator is None:
        raise DataTypeError(field_def.code, f'No validator registered for data type "{field_def.data_type}" (file/image/geo_point are handled separately).')
    return validator(field_def.code, value, field_def.validation or {}, field_def=field_def)
