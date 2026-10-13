"""
Phase 7A Task H — map EmployeeTaxDeclaration.declared_investments JSON keys
to real TaxSection codes, and report what doesn't map.

Read-only: NEVER mutates EmployeeTaxDeclaration.declared_investments itself
— that field is live data the legacy engine (services_income_tax.py) reads
directly today; rewriting its keys would be a real behavior change this
task has no business making. This only reports what the real data looks
like against the Task G TaxSection catalogue.
"""
from decimal import Decimal

from apps.payroll.models import TaxSection

# A few historically-plausible spelling variants, mapped to the real
# TaxSection codes seeded by Task G. Every key actually found in this
# company's real declared_investments data today (confirmed via
# `EmployeeTaxDeclaration.objects.values_list('declared_investments')`
# before writing this) is already an exact match for '80C'/'80D'/
# '80CCD1B'/'HRA' — these aliases are a safety net for any future/external
# data using a different spelling, not evidence that any exists today.
_KEY_ALIASES = {
    'section80c': '80C', '80c': '80C',
    'section80d': '80D', '80d': '80D',
    '80ccd1b': '80CCD1B', 'section80ccd1b': '80CCD1B', '80ccd(1b)': '80CCD1B',
    'hra_exemption': 'HRA', 'hra': 'HRA',
}


def map_declared_investments(declared_investments: dict) -> dict:
    """Returns {'matched': {section_code: Decimal}, 'unmapped': {original_key: value}}.
    Matched amounts are NOT capped here — that's compute_monthly_tds's job
    (via TaxSection.cap_amount); this is purely a key-identity report."""
    declared_investments = declared_investments or {}
    known_codes = set(TaxSection.objects.values_list('code', flat=True))

    matched = {}
    unmapped = {}
    for key, value in declared_investments.items():
        code = key if key in known_codes else _KEY_ALIASES.get(key.lower())
        if code and code in known_codes:
            try:
                matched[code] = Decimal(str(value))
            except (ValueError, ArithmeticError):
                unmapped[key] = value
        else:
            unmapped[key] = value

    return {'matched': matched, 'unmapped': unmapped}


def report_unmapped_keys_across_all_declarations() -> dict:
    """Read-only sweep for the Task H report — which real
    EmployeeTaxDeclaration rows have a declared_investments key that
    doesn't map to a known TaxSection code. Returns
    {declaration_id: {'employee_id': ..., 'unmapped': {...}}} for rows with
    at least one unmapped key; empty dict means every real key maps
    cleanly."""
    from apps.payroll.models import EmployeeTaxDeclaration

    report = {}
    for declaration in EmployeeTaxDeclaration.objects.exclude(declared_investments={}):
        result = map_declared_investments(declaration.declared_investments)
        if result['unmapped']:
            report[str(declaration.id)] = {
                'employee_id': declaration.employee_id, 'unmapped': result['unmapped'],
            }
    return report
