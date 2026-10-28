"""
One readable sentence per audit event, shared by the employee drawer's Audit Trail card and Settings > Audit Log.

Only field NAMES are described, never the old/new values: those stay in AuditLog.changes for the record, and a screen that
lists who did what should not also print a mobile number or a login email.
"""
from __future__ import annotations

REVEALED_FIELD_LABELS = {
    'pan_number': 'PAN',
    'aadhaar_number': 'Aadhaar',
    'name_as_per_aadhar': 'name as per Aadhaar',
    'account_number': 'bank account',
    'ifsc_code': 'IFSC code',
    'uan_number': 'UAN',
    'esi_number': 'ESI number',
    'pf_number': 'PF number',
    'passport_number': 'passport number',
}

UPDATED_FIELD_LABELS = {
    'phone': 'mobile number',
    'email': 'login email',
    'full_name': 'name',
    'date_of_joining': 'date of joining',
    'date_of_birth': 'date of birth',
    'employee_type': 'employment type',
    'work_location': 'work location',
    'work_mode': 'work mode',
}

# Keys of AuditLog.changes for employee_updated that describe the employee or the edit, not a changed field.
_CONTEXT_KEYS = {'employee_id', 'reason'}


def _humanise(key: str) -> str:
    return key.replace('_', ' ')


def describe_audit_event(actor_name: str, action: str, changes: dict | None) -> str:
    """'Admin revealed PAN, bank account' / 'Admin updated mobile number, login email' / the plain action otherwise."""
    changes = changes or {}
    if action == 'sensitive_reveal':
        labels = [REVEALED_FIELD_LABELS.get(key, _humanise(key)) for key in changes.get('fields', [])]
        return f'{actor_name} revealed {", ".join(labels)}' if labels else f'{actor_name} revealed sensitive fields'
    if action == 'employee_updated':
        # `full_name` is also stored as the employee's display name; it only counts as an edit when it is a from/to pair.
        keys = [key for key, value in changes.items() if key not in _CONTEXT_KEYS and isinstance(value, dict)]
        labels = [UPDATED_FIELD_LABELS.get(key, _humanise(key)) for key in keys]
        return f'{actor_name} updated {", ".join(labels)}' if labels else f'{actor_name} updated the record'
    if action in ('document_uploaded', 'document_replaced'):
        verb = 'replaced' if action == 'document_replaced' else 'uploaded'
        return f'{actor_name} {verb} {_humanise(changes.get("document_type", "a document"))}'
    if action == 'profile_viewed_self':
        return f'{actor_name} viewed their own record'
    return ''
