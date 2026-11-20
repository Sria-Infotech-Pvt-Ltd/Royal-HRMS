"""When HR or an admin punches someone in (or out) on the Attendance screen, the employee's own dashboard must follow.

The employee's Punch in / Punch out button reads the day's raw punch log (AttendancePunch): the last punch an IN means "Punch out", no
punch means "Punch in". HR's "mark attendance" and "edit" only wrote the day's summary line (AttendanceRecord), so the dashboard kept asking
a person HR had already punched in to punch in again. This adds the matching manual punches, the same way an approved correction does.

Deliberately narrow: only for TODAY (the dashboard button is about today; changing the raw punches of past days would let the nightly
recalculation overrule a status HR chose), only for a day marked as worked, and only what is missing: an IN when the person has no punch
today, an OUT when HR gives a clock-out and the person is still punched in. Existing punches are never changed or removed.
"""
from __future__ import annotations

import datetime

from django.utils import timezone

from apps.attendance.models import AttendancePunch, AttendanceRecord

WORKED_STATUSES = (
    AttendanceRecord.STATUS_PRESENT, AttendanceRecord.STATUS_LATE, AttendanceRecord.STATUS_HALF_DAY, AttendanceRecord.STATUS_INCOMPLETE,
)


def _punch(employee, moment: datetime.datetime, punch_type: str) -> AttendancePunch:
    punch, _created = AttendancePunch.objects.get_or_create(
        employee=employee, punched_at=moment, punch_type=punch_type,
        defaults={
            'source': AttendancePunch.SOURCE_MANUAL, 'attendance_mode': AttendancePunch.MODE_OFFICE,
            'branch': getattr(employee, 'branch_fk', None),
        },
    )
    return punch


def todays_clock_in_problem(employee, record_date: datetime.date, status: str, clock_in: datetime.time | None) -> str | None:
    """A message when HR marks TODAY as a worked day without a clock-in time, else None.

    The employee's Punch in button reads punches only, so a worked day marked without a time leaves it saying "Punch in" and the
    clock-in reminder email going out as if nothing was recorded. Requiring the time makes sync_manual_punches add the punch. Not asked
    for past days (nothing to punch any more) or when the person already has a punch today."""
    if record_date != timezone.localdate() or status not in WORKED_STATUSES or clock_in:
        return None
    if AttendancePunch.objects.filter(employee=employee, punched_at__date=record_date).exists():
        return None
    return "Enter the clock-in time. Today's attendance can only be marked as worked with a clock-in time, so the employee's dashboard and reminders follow it."


def sync_manual_punches(employee, record_date: datetime.date, clock_in: datetime.time | None, clock_out: datetime.time | None, status: str) -> int:
    """Add the punches HR's entry implies; returns how many were created."""
    if record_date != timezone.localdate() or status not in WORKED_STATUSES:
        return 0
    zone = timezone.get_current_timezone()
    created = 0
    todays = AttendancePunch.objects.filter(employee=employee, punched_at__date=record_date)

    if clock_in and not todays.exists():
        _punch(employee, timezone.make_aware(datetime.datetime.combine(record_date, clock_in), zone), AttendancePunch.PUNCH_IN)
        created += 1

    last = todays.order_by('-punched_at').first()
    if clock_out and last is not None and last.punch_type == AttendancePunch.PUNCH_IN:
        out_at = timezone.make_aware(datetime.datetime.combine(record_date, clock_out), zone)
        if out_at > last.punched_at:
            _punch(employee, out_at, AttendancePunch.PUNCH_OUT)
            created += 1
    return created
