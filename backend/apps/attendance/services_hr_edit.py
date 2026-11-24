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


def _follow_a_corrected_clock_in(record: AttendanceRecord, stored_status: str, stored_times: tuple, data: dict) -> None:
    """HR changed only the clock-in of a Present / Late day: the late flag and the Present / Late status follow the new time.

    The edit screen sends the day's current status back with the new time, so without this a day first stored as Late stayed Late
    after HR corrected the clock-in to an on-time one (the record showed "09:00" and still "Late"). A status HR picked on purpose is
    kept, and only a clock-in that actually changed is acted on."""
    if record.first_punch_in is None or record.first_punch_in == stored_times[0]:
        return
    if stored_status not in (AttendanceRecord.STATUS_PRESENT, AttendanceRecord.STATUS_LATE):
        return
    if 'status' in data and data['status'] != stored_status:
        return
    cfg = attendance._get_settings()
    processor = attendance.AttendanceProcessorService
    is_late = processor._check_late(record.first_punch_in, cfg)
    record.is_late = is_late
    record.status = processor._resolve_status(0, is_late, cfg, has_open_session=True)
    if _is_calculated_note(record.note):
        grace = cfg.working_hours.grace_period_minutes if cfg and hasattr(cfg, 'working_hours') else 0
        record.note = ('Grace exceeded' if grace else 'Late arrival') if is_late else ''


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
        # Only a clock-in (the person is still clocked in, or HR gave no clock-out): there are no hours to work out, but a corrected
        # clock-in still decides whether the person was late.
        _follow_a_corrected_clock_in(record, stored_status, stored_times, data)
        return

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
