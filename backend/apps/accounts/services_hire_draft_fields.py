"""
Field-by-field validation of the values a hire draft is asked to save.

A draft is a work in progress: one bad value (a half-typed email, a UAN one digit short) must never stop the rest of the
form from being saved. Each checked field is therefore judged on its own. The valid ones are kept, and each rejected one
comes back with its own message so the wizard can say exactly which field was not saved and why.

Completing the hire (HireActionCompleteView) still enforces every required field and the duplicate checks; this module only
decides what may be written into draft_data.
"""
from __future__ import annotations

from django.core.exceptions import ValidationError as DjangoValidationError
from django.core.validators import validate_email

UAN_LENGTH = 12
EMAIL_FIELDS = ('email', 'work_email')


def validate_draft_fields(data: dict) -> tuple[dict, dict[str, str]]:
    """Return (values that may be saved, {field: message} for the values that may not).

    Checks only the fields that have a format rule: both emails, the mobile number (stored as 10 normalised digits) and
    the UAN. Anything else is passed through unchanged. A field the person cleared (empty) is always acceptable.
    """
    accepted = dict(data)
    rejected: dict[str, str] = {}

    for field in EMAIL_FIELDS:
        value = accepted.get(field)
        if not value:
            continue
        try:
            validate_email(str(value).strip())
        except DjangoValidationError:
            rejected[field] = f'Enter a valid {"work " if field == "work_email" else ""}email address.'
            accepted.pop(field)

    if str(accepted.get('phone') or '').strip():
        # The mobile follows the same rule as Edit full record and Edit my details.
        from apps.accounts.services_contact_change import ContactChangeError, normalise_mobile
        try:
            accepted['phone'] = normalise_mobile(str(accepted['phone']))
        except ContactChangeError as exc:
            rejected['phone'] = exc.message
            accepted.pop('phone')

    uan = str(accepted.get('uan_number') or '').strip()
    if uan and (len(uan) != UAN_LENGTH or not uan.isdigit()):
        rejected['uan_number'] = f'UAN must be {UAN_LENGTH} digits'
        accepted.pop('uan_number')

    # Reporting manager, L1 approver and L2 HR approver: each must be someone who can do that job (active, an employee, able to
    # approve leave). Checked now so the wizard says so beside the right box; completing the hire checks again.
    from apps.accounts.services_approver_assignment import FIELD_KINDS, AssignmentError, validate_assignments
    for field in FIELD_KINDS:
        if accepted.get(field):
            try:
                validate_assignments(None, {field: accepted[field]})
            except AssignmentError as exc:
                rejected[field] = exc.message
                accepted.pop(field)

    return accepted, rejected
