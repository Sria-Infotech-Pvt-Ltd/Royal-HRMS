"""
Phase 5A — validation/derivation services for the new structured
employee master data. Pure functions, no model writes — callers (future
Task L call-site migration, not built in this pass) decide when/whether
to persist. Kept deliberately separate from any existing
call site so nothing in production reads through these yet.
"""
from __future__ import annotations

import datetime
import re
from decimal import Decimal

_E164_RE = re.compile(r'^\+[1-9]\d{6,14}$')
_PHONE_FORMAT_CHARS_RE = re.compile(r'[\s\-()./]')
_IFSC_RE = re.compile(r'^[A-Z]{4}0[A-Z0-9]{6}$')
_IBAN_RE = re.compile(r'^[A-Z]{2}\d{2}[A-Z0-9]{10,30}$')
_SWIFT_RE = re.compile(r'^[A-Z]{6}[A-Z0-9]{2}([A-Z0-9]{3})?$')


class NameSplit:
    __slots__ = ('first_name', 'middle_name', 'last_name', 'is_ambiguous')

    def __init__(self, first_name, middle_name, last_name, is_ambiguous):
        self.first_name = first_name
        self.middle_name = middle_name
        self.last_name = last_name
        self.is_ambiguous = is_ambiguous


def split_full_name(full_name: str) -> NameSplit:
    """Task B.1's "documented best-effort rule": single word -> first
    name only (ambiguous — no last name to split out); two words ->
    first + last; three or more -> first + middle(s) + last. Never
    raises, never loses data — the original string is the caller's to
    keep regardless of this split's quality."""
    parts = [p for p in full_name.strip().split() if p]
    if not parts:
        return NameSplit('', '', '', is_ambiguous=True)
    if len(parts) == 1:
        return NameSplit(parts[0], '', '', is_ambiguous=True)
    if len(parts) == 2:
        return NameSplit(parts[0], '', parts[1], is_ambiguous=False)
    return NameSplit(parts[0], ' '.join(parts[1:-1]), parts[-1], is_ambiguous=False)


def normalize_phone(raw: str, *, country_phone_code: str | None = None) -> tuple[str | None, bool]:
    """Returns (e164_value_or_none, was_normalized). Task B.2's "phones
    that cannot be normalised are kept as entered and flagged" — this
    function never raises; the CALLER keeps the original on a None
    result and adds it to the data-quality report."""
    if not raw:
        return None, False
    if _E164_RE.match(raw):
        return raw, False  # already E.164 — nothing to do

    stripped = _PHONE_FORMAT_CHARS_RE.sub('', raw)
    if stripped.startswith('+') and _E164_RE.match(stripped):
        return stripped, True

    digits = re.sub(r'\D', '', stripped)
    if country_phone_code and digits.startswith(country_phone_code.lstrip('+')):
        candidate = '+' + digits
        if _E164_RE.match(candidate):
            return candidate, True
    if country_phone_code and len(digits) == 10:  # bare national number, e.g. India's 10-digit mobiles
        candidate = '+' + country_phone_code.lstrip('+') + digits
        if _E164_RE.match(candidate):
            return candidate, True

    return None, False  # not normalisable — report it, never guess


def validate_address(data: dict, country) -> dict:
    """Task C.2 — validates against `country.address_format` (Phase 1's
    JSON field; empty = no declared format yet, so only postal_code's
    regex if present is checked). Returns a {field: error} dict."""
    errors: dict[str, str] = {}
    fmt = country.address_format or {}
    required_fields = fmt.get('required_fields', [])
    for field in required_fields:
        if not data.get(field):
            errors[field] = 'This field is required for this country\'s address format.'

    postal_regex = fmt.get('postal_code_regex')
    postal_code = data.get('postal_code')
    if postal_regex and postal_code and not re.match(postal_regex, postal_code):
        errors['postal_code'] = 'Does not match this country\'s postal code format.'
    return errors


def normalize_identity_document_number(raw: str, doc_type) -> str:
    value = raw or ''
    if doc_type.normalisation in (doc_type.NORMALISATION_STRIP_SPACES, doc_type.NORMALISATION_UPPERCASE_STRIP):
        value = re.sub(r'\s+', '', value)
    if doc_type.normalisation in (doc_type.NORMALISATION_UPPERCASE, doc_type.NORMALISATION_UPPERCASE_STRIP):
        value = value.upper()
    return value


def validate_routing_code(code: str, routing_type: str) -> bool:
    code = (code or '').strip().upper()
    from apps.accounts.models_identity_bank import BankAccount
    if routing_type == BankAccount.ROUTING_IFSC:
        return bool(_IFSC_RE.match(code))
    if routing_type == BankAccount.ROUTING_IBAN:
        return bool(_IBAN_RE.match(code))
    if routing_type == BankAccount.ROUTING_SWIFT:
        return bool(_SWIFT_RE.match(code))
    return True  # sort_code/aba_routing/other — no format verified in this pass, never rejected on a guess


class NominationError(Exception):
    def __init__(self, message: str):
        self.message = message
        super().__init__(message)


def validate_nomination_shares(shares: list[Decimal]) -> None:
    """Task F.4 — shares per scheme must total exactly 100%."""
    total = sum(shares, Decimal('0'))
    if total != Decimal('100'):
        raise NominationError(f'Nomination shares for this scheme must total 100% — currently {total}%.')


def compute_total_experience_years(periods: list[tuple]) -> Decimal:
    """Task G.3's documented overlap rule: overlapping periods are
    counted once; gaps are not counted. `periods` is a list of
    (start_date, end_date_or_None) — an open end is treated as "ongoing
    as of today" by the caller (pass today's date, not None, if that's
    the desired cutoff — this function never reads the clock itself)."""
    intervals = sorted((s, e) for s, e in periods if s is not None and e is not None and e >= s)
    if not intervals:
        return Decimal('0')

    merged = [intervals[0]]
    for start, end in intervals[1:]:
        last_start, last_end = merged[-1]
        if start <= last_end:
            merged[-1] = (last_start, max(last_end, end))
        else:
            merged.append((start, end))

    total_days = sum((end - start).days for start, end in merged)
    return (Decimal(total_days) / Decimal('365.25')).quantize(Decimal('0.1'))


def derive_highest_qualification(education_records: list, rank_by_level: dict) -> object | None:
    """Task G.3 — picks the record whose `level` has the highest
    `rank_by_level` value (ties broken by most recent `end_date`).
    Returns None for an empty list rather than raising."""
    if not education_records:
        return None
    return max(
        education_records,
        key=lambda r: (rank_by_level.get(r.level, 0), r.end_date or r.start_date or datetime.date.min),
    )
