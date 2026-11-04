"""
Field validators shared by the SaaS & Subscriptions APIs (plans, manual
assignment, payments, website registrations). Each raises a DRF
ValidationError with a message meant for the Platform Admin / customer.
frontend/lib/saasValidation.ts applies the same rules in the forms.
"""
from __future__ import annotations

import re

from rest_framework import serializers

PLAN_CODE_RE = re.compile(r'^[a-z][a-z0-9-]{1,39}$')
# Letters in any script, plus space . ' -  (e.g. "D'Souza", "R. K. Sharma").
PERSON_NAME_RE = re.compile(r"^[^\W\d_](?:[^\W\d_]|[ .'\-])*$")
# Company / plan names: letters, digits and common punctuation; at least one letter.
NAME_CHARS_RE = re.compile(r"^[\w &.,'()/+\-]+$")
HAS_LETTER_RE = re.compile(r'[^\W\d_]')
PHONE_RE = re.compile(r'^[0-9+\-\s()]{7,20}$')
REFERENCE_RE = re.compile(r'^[A-Za-z0-9 ./_#:-]+$')
MAX_EMPLOYEES = 100000


def person_name(value: str) -> str:
    value = ' '.join((value or '').split())
    if value and not PERSON_NAME_RE.match(value):
        raise serializers.ValidationError("Use letters only (spaces, . ' - allowed).")
    return value


def business_name(value: str, what: str = 'Name') -> str:
    value = ' '.join((value or '').split())
    if value and (not NAME_CHARS_RE.match(value) or not HAS_LETTER_RE.search(value)):
        raise serializers.ValidationError(
            f"{what} must contain letters and only letters, digits, spaces and & . , ' ( ) / + -")
    return value


def phone(value: str) -> str:
    value = (value or '').strip()
    if value and (not PHONE_RE.match(value) or len(re.sub(r'\D', '', value)) < 7):
        raise serializers.ValidationError('Enter a valid phone number (digits, spaces, + - ( ) only).')
    return value


def plan_code(value: str) -> str:
    value = (value or '').strip().lower()
    if not PLAN_CODE_RE.match(value):
        raise serializers.ValidationError(
            'Plan code must be 2–40 lowercase letters, digits or hyphens, starting with a letter (e.g. growth).')
    return value


def payment_reference(value: str) -> str:
    value = (value or '').strip()
    if value and not REFERENCE_RE.match(value):
        raise serializers.ValidationError('Reference can contain letters, digits, spaces and . / _ # : - only.')
    return value


def employee_count_in_plan(count: int | None, plan) -> None:
    """The plan's own employee range (when it has one)."""
    if count is None:
        return
    if plan.min_employees and count < plan.min_employees:
        raise serializers.ValidationError(f'The {plan.name} plan needs at least {plan.min_employees} employees.')
    if plan.max_employees and count > plan.max_employees:
        raise serializers.ValidationError(f'The {plan.name} plan allows at most {plan.max_employees} employees.')
