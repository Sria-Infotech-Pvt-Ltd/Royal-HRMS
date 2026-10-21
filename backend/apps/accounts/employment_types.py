"""Canonical employment types and tolerant matching of free-text input (imports, API clients)."""
from __future__ import annotations

import re

from apps.accounts.models import User

# Alias (lower-case, letters only) -> canonical User.EMPLOYMENT_TYPE_* value.
_ALIASES = {
    'permanent': User.EMPLOYMENT_TYPE_PERMANENT, 'fulltime': User.EMPLOYMENT_TYPE_PERMANENT,
    'regular': User.EMPLOYMENT_TYPE_PERMANENT, 'employee': User.EMPLOYMENT_TYPE_PERMANENT,
    'contract': User.EMPLOYMENT_TYPE_CONTRACT, 'contractor': User.EMPLOYMENT_TYPE_CONTRACT,
    'contractual': User.EMPLOYMENT_TYPE_CONTRACT, 'fixedterm': User.EMPLOYMENT_TYPE_CONTRACT,
    'freelancer': User.EMPLOYMENT_TYPE_FREELANCER, 'freelance': User.EMPLOYMENT_TYPE_FREELANCER,
    'consultant': User.EMPLOYMENT_TYPE_CONSULTANT, 'consulting': User.EMPLOYMENT_TYPE_CONSULTANT,
    'parttime': User.EMPLOYMENT_TYPE_PART_TIME,
    'temporary': User.EMPLOYMENT_TYPE_TEMPORARY, 'temp': User.EMPLOYMENT_TYPE_TEMPORARY,
    'intern': User.EMPLOYMENT_TYPE_INTERN, 'internship': User.EMPLOYMENT_TYPE_INTERN,
    'trainee': User.EMPLOYMENT_TYPE_INTERN,
}

VALID_EMPLOYMENT_TYPES = [value for value, _label in User.EMPLOYMENT_TYPE_CHOICES]


def normalize_employment_type(raw: object) -> str | None:
    """Return the canonical employment type for `raw` ("full time", "PERMANENT", "Part time"...), or None."""
    key = re.sub(r'[^a-z]', '', str(raw or '').lower())
    return _ALIASES.get(key)


def invalid_employment_type_message() -> str:
    return f'Employment type must be one of: {", ".join(VALID_EMPLOYMENT_TYPES)}.'
