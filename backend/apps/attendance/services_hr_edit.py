"""HR editing the punch times of an existing attendance day.

The edit screen opens with the day's CURRENT status already selected and sends it back with the new times, so "fix the missing
punch-out" arrived as "set the times, keep the status". A day stored as Late (or Incomplete) therefore stayed Late even when the
corrected times were a full day, and its hours were saved as the clock gap without the break. This applies the same rule live
punches use (AttendanceProcessorService.evaluate_times): when the times change and HR did NOT pick a different status, the status,
hours, overtime, shortfall and late / early-exit flags are recalculated. A status HR deliberately changes is always kept.
"""
from __future__ import annotations

from apps.attendance import services_attendance as attendance
from apps.attendance.models import AttendanceRecord

# Statuses that come from punch times, so a new set of times can change them. Leave, week off, holiday and absent are decisions.
RECALCULATED_FROM_TIMES = (
    AttendanceRecord.STATUS_PRESENT, AttendanceRecord.STATUS_LATE, AttendanceRecord.STATUS_HALF_DAY, AttendanceRecord.STATUS_INCOMPLETE,
)
# Notes the calculation writes itself; any other note was typed by a person and is kept.
_CALCULATED_NOTE_PREFIXES = ('Grace exceeded', 'Late arrival', 'Missing clock-out')


def _is_calculated_note(note: str) -> bool:
    return not note or note.startswith(_CALCULATED_NOTE_PREFIXES)


def apply_hr_edit(record: AttendanceRecord, data: dict) -> None:
    """Apply an HR edit (`status`, `clock_in`, `clock_out`, `note`) to `record` in memory; the caller saves it."""
    stored_status = record.status
    stored_times = (record.first_punch_in, record.last_punch_out)

    if 'status' in data:
        record.status = data['status']
    if 'clock_in' in data:
        record.first_punch_in = data['clock_in']
    if 'clock_out' in data:
        record.last_punch_out = data['clock_out']
    record.note = data.get('note', record.note)

    if not record.first_punch_in and not record.last_punch_out:
        record.total_working_minutes = 0
        return
    if not (record.first_punch_in and record.last_punch_out):
        return   # only one punch: nothing to calculate hours from

    calculated = attendance.AttendanceProcessorService.evaluate_times(record.first_punch_in, record.last_punch_out, attendance._get_settings())
    if calculated['status'] == AttendanceRecord.STATUS_ABSENT:
        return   # not a usable pair (out not after in)

    record.total_working_minutes = calculated['total_working_minutes']
    record.overtime_minutes = calculated['overtime_minutes']
    record.short_minutes = calculated['short_minutes']
    record.is_late = calculated['is_late']
    record.is_early_exit = calculated['is_early_exit']

    times_changed = (record.first_punch_in, record.last_punch_out) != stored_times
    status_chosen_by_hr = 'status' in data and data['status'] != stored_status
    if times_changed and not status_chosen_by_hr and stored_status in RECALCULATED_FROM_TIMES:
        record.status = calculated['status']
        if _is_calculated_note(record.note):
            record.note = calculated['note']
