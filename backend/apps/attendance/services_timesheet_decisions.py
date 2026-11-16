"""Deciding a timesheet: approve, send back, and (HR) unlock. Every action runs in one transaction under a row lock on the sheet,
so two approvers clicking at once, or an approve racing a send-back, produce one decision and one clear conflict, never two.
Each action writes a history event (with a snapshot) and an audit row inside the same transaction."""
from __future__ import annotations

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from apps.attendance.models_timesheet import (
    EVENT_APPROVED, EVENT_RETURNED, EVENT_UNLOCKED, STATUS_APPROVED, STATUS_RETURNED, STATUS_SUBMITTED, Timesheet,
)
from apps.attendance.services_timesheet_access import can_decide, can_unlock, can_view
from apps.attendance.services_timesheet_common import TimesheetConflict, TimesheetError, TimesheetForbidden, TimesheetNotFound
from apps.attendance.services_timesheet_history import record_event
from apps.attendance.services_timesheet_notify import notify_approved, notify_returned
from apps.attendance.services_timesheet_week import build_week_view, load_sheet

MAX_REASON_LENGTH = 1000
NOT_FOUND = 'Timesheet not found.'


def clean_reason(reason) -> str:
    text = reason.strip() if isinstance(reason, str) else ''
    if not text:
        raise TimesheetError('A reason is required.')
    if len(text) > MAX_REASON_LENGTH:
        raise TimesheetError(f'The reason can be at most {MAX_REASON_LENGTH} characters.')
    return text


def _locked(sheet_id) -> Timesheet:
    try:
        return Timesheet.objects.select_for_update(of=('self',)).select_related('employee', 'approver').get(pk=sheet_id)
    except (Timesheet.DoesNotExist, ValidationError, ValueError, TypeError):      # ValidationError: a malformed UUID
        raise TimesheetNotFound(NOT_FOUND) from None


def _require_submitted(sheet: Timesheet) -> None:
    if sheet.status != STATUS_SUBMITTED:
        raise TimesheetConflict(f'This timesheet is {sheet.get_status_display().lower()}, so it cannot be decided now.')


def _stamp(sheet: Timesheet, actor, status: str) -> str:
    previous = sheet.status
    sheet.status, sheet.decided_by, sheet.decided_at = status, actor, timezone.now()
    return previous


def _detail(actor, sheet_id) -> dict:
    sheet = load_sheet_by_id(sheet_id)
    return detail_for(actor, sheet)


def load_sheet_by_id(sheet_id) -> Timesheet:
    try:
        sheet = Timesheet.objects.select_related('employee', 'approver', 'decided_by').filter(pk=sheet_id).first()
    except (ValidationError, ValueError, TypeError):
        sheet = None
    if sheet is None:
        raise TimesheetNotFound(NOT_FOUND)
    return sheet


def detail_for(actor, sheet: Timesheet) -> dict:
    """The full read-only view of a sheet for a viewer who is allowed to see it, with what they may do next."""
    if not can_view(actor, sheet):
        raise TimesheetNotFound(NOT_FOUND)          # not 403: someone outside the scope learns nothing about its existence
    view = build_week_view(sheet.employee, sheet.week_start, load_sheet(sheet.employee, sheet.week_start))
    return {**view, 'can_decide': sheet.status == STATUS_SUBMITTED and can_decide(actor, sheet), 'can_unlock': can_unlock(actor, sheet)}


def approve(sheet_id, actor, *, ip_address: str | None = None) -> dict:
    with transaction.atomic():
        sheet = _locked(sheet_id)
        if not can_decide(actor, sheet):
            raise TimesheetNotFound(NOT_FOUND) if not can_view(actor, sheet) else TimesheetForbidden('You cannot approve this timesheet.')
        _require_submitted(sheet)
        previous = _stamp(sheet, actor, STATUS_APPROVED)
        sheet.save(update_fields=['status', 'decided_by', 'decided_at', 'updated_at'])
        record_event(sheet, EVENT_APPROVED, actor=actor, from_status=previous, ip_address=ip_address)
        notify_approved(sheet)
    return _detail(actor, sheet_id)


def return_to_employee(sheet_id, actor, reason, *, ip_address: str | None = None) -> dict:
    text = clean_reason(reason)
    with transaction.atomic():
        sheet = _locked(sheet_id)
        if not can_decide(actor, sheet):
            raise TimesheetNotFound(NOT_FOUND) if not can_view(actor, sheet) else TimesheetForbidden('You cannot send this timesheet back.')
        _require_submitted(sheet)
        previous = _stamp(sheet, actor, STATUS_RETURNED)
        sheet.return_reason = text
        sheet.save(update_fields=['status', 'decided_by', 'decided_at', 'return_reason', 'updated_at'])
        record_event(sheet, EVENT_RETURNED, actor=actor, from_status=previous, reason=text, ip_address=ip_address)
        notify_returned(sheet, text)
    return _detail(actor, sheet_id)


def unlock(sheet_id, actor, reason, *, ip_address: str | None = None) -> dict:
    """Reopen an APPROVED sheet for correction. It goes back to the employee as 'returned' with the reason shown; the approval
    and everything before it stay in the history, and the employee must resubmit for a fresh approval."""
    text = clean_reason(reason)
    with transaction.atomic():
        sheet = _locked(sheet_id)
        if sheet.status != STATUS_APPROVED:
            if not can_view(actor, sheet):
                raise TimesheetNotFound(NOT_FOUND)
            raise TimesheetConflict(f'Only an approved timesheet can be unlocked; this one is {sheet.get_status_display().lower()}.')
        if not can_unlock(actor, sheet):
            raise TimesheetNotFound(NOT_FOUND) if not can_view(actor, sheet) else TimesheetForbidden('You cannot unlock this timesheet.')
        previous = _stamp(sheet, actor, STATUS_RETURNED)
        sheet.return_reason = f'Reopened by HR: {text}'
        sheet.save(update_fields=['status', 'decided_by', 'decided_at', 'return_reason', 'updated_at'])
        record_event(sheet, EVENT_UNLOCKED, actor=actor, from_status=previous, reason=text, ip_address=ip_address)
        notify_returned(sheet, text, is_reopen=True)
    return _detail(actor, sheet_id)
