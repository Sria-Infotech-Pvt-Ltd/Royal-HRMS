"""
Duplicate check for a hire: the same email or mobile as an existing employee, or as another open hire draft.

Reuses the email/mobile normalisation of the HR contact edit (services_contact_change). Rules:
- an active, onboarding or notice-period employee is a hard error (the person already works here);
- an EXITED employee is only a warning, because a rehire is a legitimate case: the message names them so HR can open the old
  record instead of creating a duplicate;
- another open draft using the same email or mobile is a hard error (two people hiring the same person).
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date

from apps.accounts.models import EmployeeProfile, HireAction, User

SEVERITY_ERROR = 'error'
SEVERITY_WARNING = 'warning'


@dataclass
class DuplicateHit:
    field: str       # 'email' or 'phone': the request key the message belongs next to
    severity: str
    message: str

    def as_dict(self) -> dict:
        return {'field': self.field, 'severity': self.severity, 'message': self.message}


def _last_ten_digits(raw: str) -> str:
    return re.sub(r'\D', '', raw or '')[-10:]


def employee_status_label(user: User) -> str:
    """active / onboarding / notice period / exited: the same buckets as the headcount service."""
    from apps.hrms.models import SEP_APPROVED, SeparationRequest

    if not user.is_active:
        return 'exited'
    if SeparationRequest.objects.filter(
        employee=user, status=SEP_APPROVED, proposed_last_working_day__gte=date.today(),
    ).exists():
        return 'notice period'
    return 'active' if user.onboarding_status == User.ONBOARDING_COMPLETE else 'onboarding'


def _hit(field: str, label: str, user: User) -> DuplicateHit:
    status = employee_status_label(user)
    who = user.employee_id or 'an account without an employee id'
    if status == 'exited':
        return DuplicateHit(
            field, SEVERITY_WARNING,
            f'This {label} belonged to {who} (exited). If this is a rehire, open that record instead of creating a new one.',
        )
    return DuplicateHit(field, SEVERITY_ERROR, f'This {label} already belongs to {who} ({status}).')


def check_hire_duplicates(email: str = '', phone: str = '', exclude_action: HireAction | None = None) -> list[DuplicateHit]:
    hits: list[DuplicateHit] = []
    email = (email or '').strip().lower()
    mobile = _last_ten_digits(phone)

    if email:
        owner = User.objects.filter(email__iexact=email).first()
        if owner is None:
            profile = EmployeeProfile.objects.filter(personal_email__iexact=email).select_related('user').first()
            owner = profile.user if profile else None
        if owner is not None:
            hits.append(_hit('email', 'email', owner))
    if len(mobile) == 10:
        for candidate in User.objects.exclude(phone='').only('id', 'phone', 'employee_id', 'is_active', 'onboarding_status'):
            if _last_ten_digits(candidate.phone) == mobile:
                hits.append(_hit('phone', 'mobile number', candidate))
                break

    drafts = HireAction.objects.filter(status=HireAction.STATUS_DRAFT)
    if exclude_action is not None:
        drafts = drafts.exclude(pk=exclude_action.pk)
    for draft in drafts:
        data = draft.draft_data or {}
        draft_email = str(data.get('email') or '').strip().lower()
        if email and draft_email == email:
            hits.append(DuplicateHit('email', SEVERITY_ERROR, 'Another open hire draft already uses this email.'))
        if len(mobile) == 10 and _last_ten_digits(str(data.get('phone') or '')) == mobile:
            hits.append(DuplicateHit('phone', SEVERITY_ERROR, 'Another open hire draft already uses this mobile number.'))
    return hits


def blocking_message(hits: list[DuplicateHit]) -> tuple[str, dict]:
    """(first error message, {field: message}) for the hard errors, or ('', {}) when there are none."""
    errors = [hit for hit in hits if hit.severity == SEVERITY_ERROR]
    if not errors:
        return '', {}
    return errors[0].message, {hit.field: hit.message for hit in errors}
