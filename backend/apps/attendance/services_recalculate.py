"""
Recalculate Present / Late / Half Day for EXISTING days using the attendance settings as they are now.

Changing Punch Rules (full-day / half-day minimum hours, break, grace) only affects days processed afterwards: a day keeps
its stored status until something re-processes it. The generic reprocess endpoint rebuilds a day purely from the punch log,
so a day with no punches (leave, an HR import, a manual entry) would turn Absent. This module is the safe alternative.

It only ever touches a day that:
  - already has a Present / Late / Half Day record, and
  - has real IN and OUT punches (no open session), OR was created by the HR CSV import (it has an IMPORTED audit entry and
    stored IN / OUT times but no punch rows - those are recomputed from the stored times), and
  - was not edited by hand (no MANUALLY_EDITED audit entry), and
  - is not inside a Paid or Closed payroll cycle.
Everything else (leave, manual entries, days still clocked in) is counted as skipped and left alone. The status is computed by
the same function live punches use (AttendanceProcessorService._calculate / evaluate_times), so there is one rule, not two.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import date
from typing import Optional

from django.utils import timezone

from apps.attendance.models import AttendanceAuditLog, AttendancePunch, AttendanceRecord
from apps.attendance.services_attendance import AttendanceProcessorService, _get_settings
from apps.attendance.services_audit_log import write_audit_log

logger = logging.getLogger(__name__)

RECALCULABLE_STATUSES = (
    AttendanceRecord.STATUS_PRESENT,
    AttendanceRecord.STATUS_LATE,
    AttendanceRecord.STATUS_HALF_DAY,
)
_TRACKED_FIELDS = ('status', 'total_working_minutes', 'overtime_minutes', 'short_minutes', 'is_late', 'is_early_exit')
# Notes written by the calculation itself; any other note was written by a person and is kept.
_CALCULATED_NOTE_PREFIXES = ('Grace exceeded', 'Late arrival')
SOURCE_PUNCHES = 'punches'
SOURCE_IMPORT = 'imported times'


@dataclass
class RecalcChange:
    record_id: object
    employee_code: str
    employee_name: str
    day: date
    old_status: str
    new_status: str
    old_minutes: int
    new_minutes: int
    fields: dict = field(default_factory=dict)
    source: str = SOURCE_PUNCHES


@dataclass
class RecalcPlan:
    changes: list = field(default_factory=list)
    unchanged: int = 0
    skipped: dict = field(default_factory=dict)

    def skip(self, reason: str) -> None:
        self.skipped[reason] = self.skipped.get(reason, 0) + 1


def _is_calculated_note(note: str) -> bool:
    return not note or note.startswith(_CALCULATED_NOTE_PREFIXES)


def plan_record_change(record, punches: list, cfg) -> Optional[dict]:
    """Return {field: new_value} for what would change on this record, or None to leave it alone.

    Pure function: no database access. `punches` must be that employee's punches for that day, oldest first.
    """
    if not punches:
        return None
    if punches[-1].punch_type != AttendancePunch.PUNCH_OUT:
        return None   # still clocked in (open session) - the live path owns this day
    return _diff(record, AttendanceProcessorService._calculate(punches, record.date, cfg))


def plan_imported_change(record, cfg) -> Optional[dict]:
    """Like plan_record_change, for a day made by the HR import: recompute from the stored IN / OUT times (no punch rows).

    Pure function. A day without a usable IN and OUT pair is left alone (it would only come out Absent).
    """
    if not record.first_punch_in or not record.last_punch_out:
        return None
    calculated = AttendanceProcessorService.evaluate_times(record.first_punch_in, record.last_punch_out, cfg)
    if calculated['status'] == AttendanceRecord.STATUS_ABSENT:
        return None
    return _diff(record, calculated)


def _diff(record, calculated: dict) -> Optional[dict]:
    """The tracked fields whose value differs from the freshly calculated day (a person's note is never overwritten)."""
    changes = {name: calculated[name] for name in _TRACKED_FIELDS if getattr(record, name) != calculated[name]}
    if changes and _is_calculated_note(record.note) and calculated['note'] != record.note:
        changes['note'] = calculated['note']
    return changes or None


def _locked_ranges(start: date, end: date) -> list:
    from apps.payroll.models import PayrollCycle
    return list(
        PayrollCycle.objects
        .filter(status__in=[PayrollCycle.STATUS_PAID, PayrollCycle.STATUS_CLOSED], cycle_start__lte=end, cycle_end__gte=start)
        .values_list('cycle_start', 'cycle_end')
    )


def _manually_edited(start: date, end: date) -> set:
    rows = AttendanceAuditLog.objects.filter(
        event=AttendanceAuditLog.EVENT_MANUALLY_EDITED, date__gte=start, date__lte=end,
    ).values_list('employee_id', 'date')
    return set(rows)


def _imported_days(start: date, end: date) -> set:
    """{(employee_id, date)} that the HR CSV import wrote (its IMPORTED audit entry)."""
    rows = AttendanceAuditLog.objects.filter(
        event=AttendanceAuditLog.EVENT_IMPORTED, date__gte=start, date__lte=end,
    ).values_list('employee_id', 'date')
    return set(rows)


def _punches_by_day(start: date, end: date, employee_ids: set) -> dict:
    """{(employee_id, local date): [punches oldest first]}, grouped the same way process_day filters (punched_at__date)."""
    grouped: dict = {}
    punches = (
        AttendancePunch.objects
        .filter(employee_id__in=employee_ids, punched_at__date__gte=start, punched_at__date__lte=end)
        .order_by('punched_at')
    )
    for punch in punches:
        grouped.setdefault((punch.employee_id, timezone.localtime(punch.punched_at).date()), []).append(punch)
    return grouped


def build_plan(start: date, end: date, employee_code: str = '') -> RecalcPlan:
    """Work out what would change between `start` and `end` (inclusive). Reads only; writes nothing."""
    plan = RecalcPlan()
    cfg = _get_settings()
    records = AttendanceRecord.objects.filter(date__gte=start, date__lte=end, status__in=RECALCULABLE_STATUSES)
    if employee_code:
        records = records.filter(employee__employee_id=employee_code)
    records = list(records.select_related('employee').order_by('date', 'employee__employee_id'))
    if not records:
        return plan

    locked = _locked_ranges(start, end)
    edited = _manually_edited(start, end)
    imported = _imported_days(start, end)
    punches = _punches_by_day(start, end, {record.employee_id for record in records})

    for record in records:
        key = (record.employee_id, record.date)
        if any(first <= record.date <= last for first, last in locked):
            plan.skip('inside a paid/closed payroll cycle')
        elif key in edited:
            plan.skip('edited by hand')
        else:
            _plan_one(plan, record, punches.get(key, []), key in imported, cfg)
    return plan


def _plan_one(plan: RecalcPlan, record, day_punches: list, was_imported: bool, cfg) -> None:
    """Add this record to the plan (or count why it was left alone). Punch rows win over stored import times."""
    if day_punches:
        if day_punches[-1].punch_type != AttendancePunch.PUNCH_OUT:
            plan.skip('still clocked in')
            return
        changes, source = plan_record_change(record, day_punches, cfg), SOURCE_PUNCHES
    elif was_imported:
        changes, source = plan_imported_change(record, cfg), SOURCE_IMPORT
    else:
        plan.skip('no punches and not from the import (leave, manual entry)')
        return
    if changes is None:
        plan.unchanged += 1
        return
    plan.changes.append(_to_change(record, changes, source))


def _to_change(record, changes: dict, source: str = SOURCE_PUNCHES) -> RecalcChange:
    return RecalcChange(
        record_id=record.pk, employee_code=record.employee.employee_id, employee_name=record.employee.full_name or '',
        day=record.date, old_status=record.status, new_status=changes.get('status', record.status),
        old_minutes=record.total_working_minutes,
        new_minutes=changes.get('total_working_minutes', record.total_working_minutes),
        fields=changes, source=source,
    )


def apply_plan(plan: RecalcPlan) -> int:
    """Write the planned changes and one RECALCULATED audit entry each. Returns how many records were updated."""
    updated = 0
    for change in plan.changes:
        # status must still be what the plan saw, so a record changed since the preview is left alone.
        rows = AttendanceRecord.objects.filter(pk=change.record_id, status=change.old_status).update(
            **change.fields, updated_at=timezone.now(),
        )
        if not rows:
            logger.warning('Recalculate skipped record %s: it changed after the preview', change.record_id)
            continue
        record = AttendanceRecord.objects.select_related('employee').get(pk=change.record_id)
        write_audit_log(
            employee=record.employee, date=record.date, event=AttendanceAuditLog.EVENT_RECALCULATED, record=record,
            old_value=f'{change.old_status} | {change.old_minutes} min', new_value=f'{change.new_status} | {change.new_minutes} min',
            action=f'Recalculated with the current attendance settings (from {change.source})',
        )
        updated += 1
    return updated
