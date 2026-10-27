"""Face ID policy: who registers a face ID, what an employee is told, and when a punch may go ahead without one.

One place decides all of it, so the punch error, the Profile card, the Face ID Registrations screen, the hire
completion screen and the welcome email can never disagree. The organisation picks the mode in Attendance Settings.
"""
from __future__ import annotations

import datetime
from typing import Optional

from django.utils import timezone

from apps.attendance.models import AttendanceFaceVerificationRules as Rules
from apps.attendance.models import FaceRegistrationRequest

STATE_APPROVED = 'approved'
STATE_PENDING = 'pending'
STATE_REJECTED = 'rejected'
STATE_NOT_REGISTERED = 'not_registered'

_APPROVED_MESSAGE = 'Your Face ID is registered. You will be asked to verify it when you clock in.'

# (state, mode) -> the single instruction shown to the employee.
_MESSAGES = {
    Rules.MODE_SELF_SERVICE: {
        STATE_NOT_REGISTERED: 'Register your Face ID from your Profile page (Register My Face). It takes effect immediately.',
        STATE_PENDING: 'Your Face ID is waiting for approval.',
        STATE_REJECTED: 'Your last Face ID registration was rejected. Register it again from your Profile page.',
    },
    Rules.MODE_HR_IN_PERSON: {
        STATE_NOT_REGISTERED: 'Your Face ID is registered in person by HR. Please ask HR to register it; you cannot register it yourself.',
        STATE_PENDING: 'Your Face ID is waiting for approval.',
        STATE_REJECTED: 'Your Face ID needs to be registered again. Please ask HR to register it in person.',
    },
    Rules.MODE_SELF_SERVICE_APPROVAL: {
        STATE_NOT_REGISTERED: 'Register your Face ID from your Profile page (Register My Face). HR will approve it before it can be used.',
        STATE_PENDING: 'Your Face ID has been submitted and is waiting for HR approval.',
        STATE_REJECTED: 'Your Face ID registration was rejected. Register it again from your Profile page.',
    },
}

# What HR / an admin is told on the Face ID Registrations screen and the onboarding screens.
_HR_NOTES = {
    Rules.MODE_SELF_SERVICE: (
        "Employees register their own Face ID from their Profile page and it is active immediately. "
        "Use this page to register or replace one on someone's behalf."
    ),
    Rules.MODE_HR_IN_PERSON: (
        'Face ID is registered in person by HR, on this page. Employees cannot register it themselves.'
    ),
    Rules.MODE_SELF_SERVICE_APPROVAL: (
        'Employees register their own Face ID from their Profile page and HR approves it here. '
        'You can also register one in person; it is approved immediately.'
    ),
}


def _rules() -> Optional[Rules]:
    from core.cache_service import AttendanceSettingsCacheService

    settings_obj = AttendanceSettingsCacheService.get()
    return getattr(settings_obj, 'face_verification', None) if settings_obj is not None else None


def is_mandatory() -> bool:
    rules = _rules()
    return bool(rules and rules.is_mandatory)


def registration_mode() -> str:
    rules = _rules()
    mode = rules.registration_mode if rules else Rules.MODE_SELF_SERVICE_APPROVAL
    return mode if mode in Rules.REGISTRATION_MODES else Rules.MODE_SELF_SERVICE_APPROVAL


def can_employee_self_register() -> bool:
    """Whether the organisation lets employees register their own Face ID at all."""
    return is_mandatory() and registration_mode() != Rules.MODE_HR_IN_PERSON


def employee_state(employee) -> str:
    """approved (an active registration exists) / pending / rejected / not_registered, for this employee."""
    if FaceRegistrationRequest.objects.filter(employee=employee, is_active=True).exists():
        return STATE_APPROVED
    latest = FaceRegistrationRequest.objects.filter(employee=employee).order_by('-created_at').first()
    if latest is None:
        return STATE_NOT_REGISTERED
    if latest.status == FaceRegistrationRequest.STATUS_PENDING:
        return STATE_PENDING
    if latest.status == FaceRegistrationRequest.STATUS_REJECTED:
        return STATE_REJECTED
    return STATE_NOT_REGISTERED


def fallback_until(employee) -> Optional[datetime.date]:
    """The last day a punch without a face ID is allowed for this employee, when the policy has a date limit."""
    rules = _rules()
    if rules is None or rules.fallback_policy != Rules.FALLBACK_DAYS_AFTER_JOINING:
        return None
    joined = getattr(employee, 'date_of_joining', None)
    return joined + datetime.timedelta(days=rules.fallback_days) if joined else None


def fallback_allows(employee, on_date: Optional[datetime.date] = None) -> bool:
    """True when this employee may punch from the office WITHOUT a face match today: face ID is mandatory, they have
    no approved face ID yet, and the organisation's fallback policy covers them."""
    rules = _rules()
    if rules is None or not rules.is_mandatory or rules.fallback_policy == Rules.FALLBACK_NONE:
        return False
    if employee_state(employee) == STATE_APPROVED:
        return False
    if rules.fallback_policy == Rules.FALLBACK_UNTIL_APPROVED:
        return True
    last_day = fallback_until(employee)
    return last_day is not None and (on_date or timezone.localdate()) <= last_day


def instruction_for(state: str, *, fallback_allowed: bool = False, until: Optional[datetime.date] = None) -> str:
    """The one sentence an employee is shown for their Face ID state under the current mode."""
    if state == STATE_APPROVED:
        return _APPROVED_MESSAGE
    mode = registration_mode()
    message = _MESSAGES[mode].get(state, _MESSAGES[mode][STATE_NOT_REGISTERED])
    if fallback_allowed:
        message += ' Until then you can still clock in from your office location; those punches are flagged for HR.'
        if until:
            message += f' This is allowed until {until.strftime("%d %b %Y")}.'
    return message


def guidance(employee) -> dict:
    """Everything a screen needs to explain Face ID to this employee, consistently."""
    mandatory = is_mandatory()
    if not mandatory:
        return {
            'is_mandatory': False, 'registration_mode': registration_mode(), 'state': STATE_NOT_REGISTERED,
            'can_self_register': False, 'requires_face_to_punch': False, 'message': '',
            'fallback_active': False, 'fallback_until': None, 'hr_note': _HR_NOTES[registration_mode()],
        }
    state = employee_state(employee)
    allowed = fallback_allows(employee)
    until = fallback_until(employee) if allowed else None
    return {
        'is_mandatory': True,
        'registration_mode': registration_mode(),
        'state': state,
        # Someone with a pending request waits for it rather than submitting another.
        'can_self_register': can_employee_self_register() and state != STATE_PENDING,
        'requires_face_to_punch': state == STATE_APPROVED,
        'message': instruction_for(state, fallback_allowed=allowed, until=until),
        'fallback_active': allowed,
        'fallback_until': until.isoformat() if until else None,
        'hr_note': _HR_NOTES[registration_mode()],
    }


def hire_summary(employee) -> dict:
    """Face ID status and next steps for the hire completion screen (HR) and the welcome email (the new hire)."""
    info = guidance(employee)
    name = employee.full_name or employee.employee_id or 'the new hire'
    if not info['is_mandatory']:
        hr_next_step = 'Face ID is not required for clock-in at the moment. Nothing to do.'
    elif info['registration_mode'] == Rules.MODE_SELF_SERVICE:
        hr_next_step = f'Nothing to do. {name} registers their own Face ID from their Profile page; it is active at once.'
    elif info['registration_mode'] == Rules.MODE_HR_IN_PERSON:
        hr_next_step = f"Register {name}'s Face ID in person from the Face ID Registrations page."
    else:
        hr_next_step = f'{name} registers their Face ID from their Profile page; approve it on the Face ID Registrations page.'
    return {
        'is_mandatory': info['is_mandatory'],
        'registration_mode': info['registration_mode'],
        'state': info['state'],
        'employee_message': info['message'],
        'hr_next_step': hr_next_step,
        'fallback_active': info['fallback_active'],
        'fallback_until': info['fallback_until'],
    }
