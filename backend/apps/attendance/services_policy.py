"""
Company attendance policy rules shared by attendance processing, the
un-punch job and payroll, so every module reaches the same outcome:

- missing_punch_status(): what a Clock In without a Clock Out becomes.
- late_mark_lop_days():   Loss-of-Pay days from a set of late-mark dates.
"""
from __future__ import annotations

from collections import Counter
from datetime import date
from decimal import Decimal
from typing import Iterable

from django.db.models import Q

from apps.attendance.models import AttendanceLateMarkRules, AttendancePunchRules, AttendanceRecord


def missing_clock_out_q() -> Q:
    """Records still missing a Clock Out after the shift ended, whatever status
    the missing-punch setting gave them (the HR Un-punches list)."""
    return Q(status=AttendanceRecord.STATUS_INCOMPLETE) | Q(
        first_punch_in__isnull=False, last_punch_out__isnull=True,
        status__in=[AttendanceRecord.STATUS_HALF_DAY, AttendanceRecord.STATUS_ABSENT],
    )


def missing_punch_status(cfg) -> str:
    """Status for a day with a Clock In but no Clock Out, per Attendance Settings."""
    rules = getattr(cfg, 'punch_rules', None) if cfg else None
    action = getattr(rules, 'missing_punch_action', AttendancePunchRules.MISSING_PUNCH_REGULARIZE)
    return {
        AttendancePunchRules.MISSING_PUNCH_HALF_DAY: AttendanceRecord.STATUS_HALF_DAY,
        AttendancePunchRules.MISSING_PUNCH_ABSENT:   AttendanceRecord.STATUS_ABSENT,
    }.get(action, AttendanceRecord.STATUS_INCOMPLETE)


def wfh_report_status(employee, for_date: date, status: str, cfg, today: date) -> tuple[str, str]:
    """
    Status for an approved WFH day under the WFH work-report rule
    (AttendancePunchRules.wfh_daily_report_required; returns (status, '') unchanged when off).

    The reviewer's decision wins: Half Day → Half Day, Not accepted → Absent,
    Full Day → unchanged. Without a decision, a past day with no report, or a
    report submitted after the day, is Absent. Returns (status, note).
    """
    rules = getattr(cfg, 'punch_rules', None) if cfg else None
    if not getattr(rules, 'wfh_daily_report_required', False):
        return status, ''
    if status not in (AttendanceRecord.STATUS_PRESENT, AttendanceRecord.STATUS_LATE, AttendanceRecord.STATUS_HALF_DAY):
        return status, ''
    from apps.hrms.models import WFHDailyReport
    report = WFHDailyReport.objects.filter(employee=employee, date=for_date).first()
    if report and report.review_status == WFHDailyReport.REVIEW_HALF_DAY:
        return AttendanceRecord.STATUS_HALF_DAY, 'WFH report: half day'
    if report and report.review_status == WFHDailyReport.REVIEW_NOT_ACCEPTED:
        return AttendanceRecord.STATUS_ABSENT, 'WFH report not accepted'
    if report and report.review_status == WFHDailyReport.REVIEW_FULL_DAY:
        return status, ''
    if for_date < today and (report is None or report.submitted_late):
        return AttendanceRecord.STATUS_ABSENT, 'WFH report not submitted on time'
    return status, ''


def late_mark_lop_days(late_dates: Iterable[date], rules) -> Decimal:
    """
    LOP days for the late marks in one payroll cycle.

    every_n:         one LOP unit for every `late_marks_per_lop` late marks in
                     the cycle (unchanged from before late_mark_mode existed).
    after_allowance: per calendar month, the first `late_marks_per_lop` late
                     marks are allowed; each later one is one LOP unit.
    late_marks_per_lop = 0 (or no rules) means tracking only — no LOP.
    """
    n = getattr(rules, 'late_marks_per_lop', 0) if rules else 0
    if not n:
        return Decimal('0')
    unit = Decimal('1') if rules.lop_deduction_unit == AttendanceLateMarkRules.LOP_UNIT_FULL_DAY else Decimal('0.5')
    late_dates = list(late_dates)
    if getattr(rules, 'late_mark_mode', AttendanceLateMarkRules.MODE_EVERY_N) == AttendanceLateMarkRules.MODE_AFTER_ALLOWANCE:
        per_month = Counter((d.year, d.month) for d in late_dates)
        triggers = sum(max(0, count - n) for count in per_month.values())
    else:
        triggers = len(late_dates) // n
    return Decimal(triggers) * unit
