"""Repair days that were saved before the punch-pairing fix: a day whose hours do not match what its punches say.

An approved "I forgot to punch in" correction adds a manual IN at the corrected time. Before the fix the saved day could still start from
the later punch, so the employee's dashboard showed hours short. The live calculation is right now, but a day that was ALREADY saved keeps
the old figures until it is calculated again. This calculates again the days that need it, and only those.

Deliberately careful, because the calculation overwrites the saved day:
  - only days that have at least one MANUAL punch (an approved correction, or HR punching someone in): that is where the old rule went wrong;
  - only a day whose saved status is one that comes from punch times (present / late / half day / incomplete), never leave, holiday, week off
    or absent, which are decisions;
  - never a day HR edited by hand (it has a "manually edited" audit entry), so a deliberate HR figure is not undone;
  - never a day inside a paid or closed payroll cycle;
  - only a day whose saved figures actually differ from what its punches give, so running it again changes nothing.
"""
from __future__ import annotations

import datetime

from django.utils import timezone

from apps.attendance.models import AttendanceAuditLog, AttendancePunch, AttendanceRecord
from apps.attendance.services_attendance import AttendanceProcessorService, _get_settings
from apps.attendance.services_hr_edit import RECALCULATED_FROM_TIMES

_COMPARED = ('status', 'first_punch_in', 'last_punch_out', 'total_working_minutes')


def recalculate_correction_days(days: int = 14, *, employee_key: str = '', dry_run: bool = False) -> list[dict]:
    """Recalculate the stale days of the last `days` days (today included). Returns one dict per day that differed (and, unless dry_run, was fixed)."""
    from apps.payroll.models import PayrollCycle

    today = timezone.localdate()
    since = today - datetime.timedelta(days=max(days, 0))
    manual = AttendancePunch.objects.filter(source=AttendancePunch.SOURCE_MANUAL, punched_at__date__gte=since)
    if employee_key:
        manual = manual.filter(employee__employee_id=employee_key) | manual.filter(employee__email__iexact=employee_key)
    keys = sorted(set(manual.values_list('employee_id', 'punched_at__date')), key=lambda pair: (pair[1], str(pair[0])))

    locked = list(PayrollCycle.objects.filter(status__in=['paid', 'closed']).values_list('cycle_start', 'cycle_end'))
    cfg = _get_settings()
    changes: list[dict] = []
    for employee_id, day in keys:
        if any(start <= day <= end for start, end in locked):
            continue
        record = AttendanceRecord.objects.select_related('employee').filter(employee_id=employee_id, date=day, status__in=RECALCULATED_FROM_TIMES).first()
        if record is None:
            continue
        if AttendanceAuditLog.objects.filter(employee_id=employee_id, date=day, event=AttendanceAuditLog.EVENT_MANUALLY_EDITED).exists():
            continue
        punches = list(AttendancePunch.objects.filter(employee_id=employee_id, punched_at__date=day).order_by('punched_at'))
        calculated = AttendanceProcessorService._calculate(punches, day, cfg)
        if all(getattr(record, key) == calculated[key] for key in _COMPARED):
            continue
        changes.append({
            'employee_id': record.employee.employee_id, 'date': day,
            'before': (record.status, record.first_punch_in, record.last_punch_out, record.total_working_minutes),
            'after': (calculated['status'], calculated['first_punch_in'], calculated['last_punch_out'], calculated['total_working_minutes']),
        })
        if not dry_run:
            AttendanceProcessorService.process_day(record.employee, day)
    return changes
