"""Validation of a submitted `declared_investments` dict (see tax_declaration_schema).

Pure functions that raise ValueError with an employee-readable message, so the
serializer stays thin and these rules can be unit-tested without a database.
"""
from __future__ import annotations

from decimal import Decimal, InvalidOperation

from .tax_declaration_schema import (
    ALLOWED_KEYS,
    DETAILS_KEY,
    LANDLORD_RELATIONSHIPS,
    MAX_DECLARED_AMOUNT,
    PAN_PATTERN,
    RENT_LANDLORD_PAN_THRESHOLD,
)

_RELATIONSHIP_VALUES = {value for value, _label in LANDLORD_RELATIONSHIPS}


def _to_amount(value, label: str) -> Decimal:
    try:
        amount = Decimal(str(value))
    except (InvalidOperation, ValueError):
        raise ValueError(f'"{label}" must be a number.')
    if not amount.is_finite():
        raise ValueError(f'"{label}" must be a number.')
    if amount < 0:
        raise ValueError(f'"{label}" cannot be negative.')
    if amount > MAX_DECLARED_AMOUNT:
        raise ValueError(f'"{label}" is too large.')
    return amount


def _validate_hra_details(hra: dict) -> None:
    monthly_rent = _to_amount(hra.get('monthly_rent', 0) or 0, 'Monthly rent')
    if monthly_rent == 0:
        return
    months = hra.get('months', 12)
    if not isinstance(months, int) or isinstance(months, bool) or not 1 <= months <= 12:
        raise ValueError('Months of rent must be between 1 and 12.')
    if not str(hra.get('landlord_name', '')).strip():
        raise ValueError("Enter your landlord's name for the rent you are claiming.")
    if not str(hra.get('landlord_address', '')).strip():
        raise ValueError("Enter your landlord's address for the rent you are claiming.")
    relationship = hra.get('landlord_relationship', 'none')
    if relationship not in _RELATIONSHIP_VALUES:
        raise ValueError('Choose how you are related to your landlord.')
    pan = str(hra.get('landlord_pan', '')).strip().upper()
    if pan and not PAN_PATTERN.match(pan):
        raise ValueError("Landlord PAN must look like ABCDE1234F.")
    if monthly_rent * months > RENT_LANDLORD_PAN_THRESHOLD and not pan:
        raise ValueError("Landlord PAN is required when your yearly rent is above ₹1,00,000.")


def _validate_home_loan_details(details: dict, declared: dict) -> None:
    """Form 124 asks for the lender's name and PAN against home-loan interest."""
    if _to_amount(declared.get('24B', 0) or 0, 'Home loan interest') == 0:
        return
    loan = details.get('home_loan')
    if not isinstance(loan, dict) or not str(loan.get('lender_name', '')).strip():
        raise ValueError("Enter your home loan lender's name.")
    pan = str(loan.get('lender_pan', '')).strip().upper()
    if not pan:
        raise ValueError("Enter your home loan lender's PAN.")
    if not PAN_PATTERN.match(pan):
        raise ValueError("Lender PAN must look like ABCDE1234F.")


def _validate_details(details) -> None:
    if not isinstance(details, dict):
        raise ValueError('Declaration details must be an object.')
    hra = details.get('hra')
    if hra is not None:
        if not isinstance(hra, dict):
            raise ValueError('Rent details must be an object.')
        _validate_hra_details(hra)
    for flag in ('senior_self_family', 'senior_parents'):
        if flag in details and not isinstance(details[flag], bool):
            raise ValueError('Senior citizen answers must be yes or no.')
    previous = details.get('previous_employer')
    if previous is not None:
        if not isinstance(previous, dict):
            raise ValueError('Previous employer details must be an object.')
        _to_amount(previous.get('income', 0) or 0, 'Income from previous employer')
        _to_amount(previous.get('tds', 0) or 0, 'Tax deducted by previous employer')


def validate_declared_investments(value) -> None:
    if not isinstance(value, dict):
        raise ValueError('declared_investments must be an object of item -> amount.')
    details = value.get(DETAILS_KEY)
    _validate_home_loan_details(details if isinstance(details, dict) else {}, value)
    for key, amount in value.items():
        if key not in ALLOWED_KEYS:
            raise ValueError(f'"{key}" is not a recognised declaration item.')
        if key == DETAILS_KEY:
            _validate_details(amount)
        else:
            _to_amount(amount, key)
