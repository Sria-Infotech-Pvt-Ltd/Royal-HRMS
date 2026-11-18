"""Profile-change requests: an employee asks for a new value, HR / the System Admin approves and the value is applied in one step.

Names, dates and contact details feed payroll and statutory records, so the employee never edits them directly: the change is
validated when it is asked for, again when it is applied, written to the audit log with before and after, and the employee is
told the outcome. The joining date needs a System Admin (it drives attendance and payroll); the full-name lock that applies to
ordinary edits after onboarding does not apply to an approved correction.
"""
from __future__ import annotations

import datetime
import logging
import re

from django.db import transaction
from django.utils import timezone

from apps.accounts.models import AuditLog, EmployeeProfile, User
from apps.accounts.services_contact_change import ContactChangeError, check_mobile_unique, normalise_mobile
from core.permissions import has_perm

from .models import HR_HELP_RESOLVED, HRHelpRequest
from .profile_change_fields import (
    KIND_ACCOUNT, KIND_CHOICE, KIND_DATE, KIND_IFSC, KIND_PHONE, KIND_PIN, TARGET_PROFILE, ChangeField, display_value,
    mask_sensitive, spec_for_key, spec_for_label,
)
from .services_profile_correction import parse_profile_correction

logger = logging.getLogger(__name__)

DECISION_APPLIED = 'applied'
DECISION_REJECTED = 'rejected'
_PIN_RE = re.compile(r'^\d{6}$')
_IFSC_RE = re.compile(r'^[A-Z]{4}0[A-Z0-9]{6}$')   # the same rule as the bank-details serializer
BANK_CHANGE_PENDING_MESSAGE = 'A bank-detail change from the employee is already waiting for HR review. Decide that one first.'


class ProfileChangeError(Exception):
    """A change that cannot be asked for or applied; the message is shown to the person."""

    def __init__(self, message: str):
        super().__init__(message)
        self.message = message


def _target(employee: User, spec: ChangeField):
    if spec.target != TARGET_PROFILE:
        return employee
    profile, _created = EmployeeProfile.objects.get_or_create(user=employee)
    return profile


def current_value(employee: User, spec: ChangeField) -> str:
    value = getattr(_target(employee, spec), spec.attr, '')
    return '' if value is None else str(value)


def display_current(employee: User, spec: ChangeField) -> str:
    """The current value for showing (a ticket's "was"): the same as current_value, but bank numbers masked."""
    return display_value(spec, current_value(employee, spec))


def clean_new_value(employee: User, spec: ChangeField, raw: str) -> str:
    """The value to store, or ProfileChangeError saying what is wrong with it."""
    value = (raw or '').strip()
    if not value:
        raise ProfileChangeError(f'Enter the new {spec.label.lower()}.')
    if len(value) > spec.max_length:
        raise ProfileChangeError(f'{spec.label} can be at most {spec.max_length} characters.')
    if spec.kind == KIND_DATE:
        value = _clean_date(spec, value)
    elif spec.kind == KIND_PHONE:
        value = _clean_phone(employee, spec, value)
    elif spec.kind == KIND_PIN and not _PIN_RE.match(value):
        raise ProfileChangeError('Enter a 6-digit PIN code.')
    elif spec.kind == KIND_CHOICE and value not in {choice for choice, _label in spec.choices}:
        raise ProfileChangeError(f'Choose a valid {spec.label.lower()}.')
    elif spec.kind == KIND_ACCOUNT and not (value.isdigit() and 9 <= len(value) <= 18):
        raise ProfileChangeError('Account number must be 9 to 18 digits, with no spaces or letters.')
    elif spec.kind == KIND_IFSC:
        value = value.upper()
        if not _IFSC_RE.match(value):
            raise ProfileChangeError('Enter a valid IFSC code (for example SBIN0001234): 4 letters, the digit 0, then 6 letters or digits.')
    if value == current_value(employee, spec):
        raise ProfileChangeError(f'That is already the {spec.label.lower()} on the record.')
    return value


def _clean_date(spec: ChangeField, value: str) -> str:
    try:
        parsed = datetime.date.fromisoformat(value)
    except ValueError:
        raise ProfileChangeError(f'Enter a valid {spec.label.lower()}.') from None
    if spec.key == 'date_of_birth' and parsed >= datetime.date.today():
        raise ProfileChangeError('Date of birth must be in the past.')
    return parsed.isoformat()


def _clean_phone(employee: User, spec: ChangeField, value: str) -> str:
    try:
        number = normalise_mobile(value)
        if spec.key == 'phone':
            check_mobile_unique(employee, number)
        return number
    except ContactChangeError as exc:
        raise ProfileChangeError(exc.message) from None


def can_decide(user: User, spec: ChangeField) -> bool:
    """HR who answer tickets, and the System Admin; the joining date needs the System Admin."""
    if spec.full_access_only:
        return has_perm(user, 'settings.edit')
    return has_perm(user, 'hr_help.respond') or has_perm(user, 'settings.edit')


def suggested_spec(ticket: HRHelpRequest) -> ChangeField | None:
    """The field an older profile-correction ticket (raised before the new value was asked for) is about, read from its message."""
    if ticket.topic != 'profile_correction' or ticket.change_field:
        return None
    section, field, _reason = parse_profile_correction(ticket.message)
    return spec_for_label(section, field)


def apply_change(ticket: HRHelpRequest, decided_by: User, note: str = '', new_value: str = '') -> HRHelpRequest:
    """Approve: write the new value to the record, audit it, resolve the ticket, tell the employee.

    An older ticket has no stored new value, so HR types it (`new_value`) and it is stored on the ticket with the decision."""
    spec, employee = _open_change(ticket, decided_by)
    if not ticket.change_field:
        ticket.change_field = spec.key
        ticket.change_new_value = ''
    new_value = clean_new_value(employee, spec, ticket.change_new_value or new_value)   # re-checked: the record may have changed since the request
    ticket.change_new_value = new_value
    old_value = current_value(employee, spec)
    with transaction.atomic():
        target = _target(employee, spec)
        _refuse_if_bank_change_pending(target, spec)
        setattr(target, spec.attr, new_value)
        target._changed_by = decided_by
        target.save()
        # Bank numbers never go into the audit log or onto the ticket in full: the record itself now holds the value.
        AuditLog.objects.create(
            user=decided_by, action='employee_profile_corrected', module='employees', object_id=str(employee.id),
            changes={
                'employee_id': employee.employee_id,
                spec.key: {'from': display_value(spec, old_value), 'to': display_value(spec, new_value)},
                'ticket': ticket.request_number,
            },
            branch=employee.branch,
        )
        if spec.is_sensitive:
            ticket.change_new_value = display_value(spec, new_value)
        _close(ticket, DECISION_APPLIED, decided_by, note.strip() or 'Approved and updated on your record.', display_value(spec, old_value))
    logger.info('Profile change %s (%s) applied for employee %s by %s', ticket.request_number, spec.key, employee.pk, decided_by.pk)
    _tell_employee(ticket, f'Your {spec.label.lower()} was updated', 'HR approved your correction and updated your record.')
    return ticket


def reject_change(ticket: HRHelpRequest, decided_by: User, note: str) -> HRHelpRequest:
    spec, employee = _open_change(ticket, decided_by)
    if not (note or '').strip():
        raise ProfileChangeError('Write a short reason before declining, so the employee knows why.')
    with transaction.atomic():
        if spec.is_sensitive:
            ticket.change_new_value = mask_sensitive(ticket.change_new_value)   # a declined bank number is not kept in full
        _close(ticket, DECISION_REJECTED, decided_by, note.strip(), display_current(employee, spec))
    _tell_employee(ticket, f'Your {spec.label.lower()} correction was declined', note.strip())
    return ticket


def _refuse_if_bank_change_pending(profile: EmployeeProfile, spec: ChangeField) -> None:
    if spec.section == 'Bank details' and profile.bank_change_status == EmployeeProfile.BANK_CHANGE_PENDING:
        raise ProfileChangeError(BANK_CHANGE_PENDING_MESSAGE)


def _open_change(ticket: HRHelpRequest, decided_by: User) -> tuple[ChangeField, User]:
    spec = spec_for_key(ticket.change_field) or suggested_spec(ticket)
    if spec is None:
        raise ProfileChangeError('This request has no value to apply. Update the record by hand and resolve the ticket.')
    if ticket.change_decision:
        raise ProfileChangeError('This request has already been decided.')
    if not can_decide(decided_by, spec):
        raise ProfileChangeError(
            'Only a System Admin can change the date of joining.' if spec.full_access_only else 'You do not have permission to decide this request.'
        )
    return spec, ticket.submitted_by


def _close(ticket: HRHelpRequest, decision: str, decided_by: User, note: str, old_value: str) -> None:
    ticket.change_decision = decision
    ticket.change_old_value = old_value
    ticket.response = note
    ticket.status = HR_HELP_RESOLVED
    ticket.resolved_at = timezone.now()
    ticket.assigned_to = ticket.assigned_to or decided_by
    if decision == DECISION_APPLIED:
        ticket.change_applied_at = timezone.now()
    ticket.save()


def _tell_employee(ticket: HRHelpRequest, title: str, message: str) -> None:
    from apps.notifications.signals import _notify

    _notify(ticket.submitted_by, title, message, 'hr_help_request', 'system', 'profile-change')
