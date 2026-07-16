"""
HR Attendance Audit services — Invalid Punches + Un-punches.

Invalid punches: sequences that don't form clean IN→OUT pairs,
duplicates within the same minute, or punches with a future timestamp.

Un-punches: employees who have an IN punch for the date but no OUT punch yet.
"""
from __future__ import annotations

import datetime
import logging
from collections import defaultdict

from django.contrib.auth import get_user_model
from django.db.models import Q

from apps.attendance.models import AttendancePunch

logger = logging.getLogger(__name__)
User = get_user_model()

# ── Issue type constants ──────────────────────────────────────────────────────

ISSUE_DUPLICATE   = 'duplicate'
ISSUE_FUTURE      = 'future'
ISSUE_NO_MATCH    = 'no-match'


# ── Invalid Punches ───────────────────────────────────────────────────────────

def get_invalid_punch_count(
    target_date: datetime.date,
    branch: str,
    department: str,
) -> int:
    return len(get_invalid_punches(target_date, branch, department))


def get_invalid_punches(
    target_date: datetime.date,
    branch: str,
    department: str,
) -> list[dict]:
    """
    Return rows describing punches that have structural problems for target_date.

    Three issue types:
    - future: punch timestamp is in the future
    - duplicate: two punches of the same type within 60 seconds
    - no-match: punch type causes a broken IN/OUT sequence

    Uses employees who have an AttendanceRecord for target_date to avoid
    UTC vs IST date mismatch on punched_at__date lookups.
    """
    from apps.attendance.models import AttendanceRecord

    employee_qs = User.objects.filter(is_active=True)
    if branch:
        employee_qs = employee_qs.filter(branch=branch)
    if department:
        employee_qs = employee_qs.filter(department=department)

    # Employees who have an AttendanceRecord for this date (date is a plain DateField)
    employee_ids_with_record = AttendanceRecord.objects.filter(
        date=target_date, employee__in=employee_qs,
    ).values_list('employee_id', flat=True)

    punches = (
        AttendancePunch.objects
        .filter(employee_id__in=employee_ids_with_record)
        .filter(punched_at__date=target_date)
        .select_related('employee', 'branch')
        .order_by('employee_id', 'punched_at')
    )

    now = datetime.datetime.now(datetime.timezone.utc)
    invalid: list[dict] = []
    by_employee: dict[str, list] = defaultdict(list)

    for punch in punches:
        by_employee[str(punch.employee_id)].append(punch)

    for _emp_id, emp_punches in by_employee.items():
        # Future punches
        for p in emp_punches:
            ts = p.punched_at
            if ts.tzinfo is None:
                ts = ts.replace(tzinfo=datetime.timezone.utc)
            if ts > now:
                invalid.append(_build_row(p, ISSUE_FUTURE, 'Punch time is in the future'))

        # Duplicates (same type within 60s of each other)
        for i, p in enumerate(emp_punches[1:], 1):
            prev = emp_punches[i - 1]
            delta = abs((p.punched_at - prev.punched_at).total_seconds())
            if p.punch_type == prev.punch_type and delta <= 60:
                invalid.append(
                    _build_row(p, ISSUE_DUPLICATE, f'Duplicate {p.punch_type} within 60 seconds')
                )

        # Sequence issues (consecutive same-type punches without opposite)
        sequence = [p.punch_type for p in emp_punches]
        for i, (current, nxt) in enumerate(zip(sequence, sequence[1:])):
            if current == nxt:
                invalid.append(
                    _build_row(
                        emp_punches[i + 1], ISSUE_NO_MATCH,
                        f'Expected {"OUT" if current == "IN" else "IN"}, got {current}'
                    )
                )

    return invalid


def _build_row(punch: AttendancePunch, issue_type: str, issue: str) -> dict:
    branch_name = punch.branch.name if punch.branch else punch.employee.branch or '—'
    return {
        'id':              str(punch.id),
        'device_id':       punch.device_id or '—',
        'raw_time':        punch.punched_at.strftime('%Y-%m-%d %H:%M:%S'),
        'biometric_id':    punch.device_id or '—',
        'issue':           issue,
        'issue_type':      issue_type,
        'suggested_match': _suggested_match(punch),
        'branch':          branch_name,
    }


def _suggested_match(punch: AttendancePunch) -> str:
    """Suggest the counterpart punch for a no-match issue."""
    if punch.punch_type == AttendancePunch.PUNCH_IN:
        return 'Add OUT punch'
    return 'Add IN punch'


# ── Un-punches ────────────────────────────────────────────────────────────────

def get_unpunch_count(
    target_date: datetime.date,
    branch: str,
    department: str,
) -> int:
    """Count employees whose AttendanceRecord is STATUS_INCOMPLETE for target_date."""
    from apps.attendance.models import AttendanceRecord

    employee_qs = User.objects.filter(is_active=True)
    if branch:
        employee_qs = employee_qs.filter(branch=branch)
    if department:
        employee_qs = employee_qs.filter(department=department)

    return AttendanceRecord.objects.filter(
        date=target_date,
        employee__in=employee_qs,
        status=AttendanceRecord.STATUS_INCOMPLETE,
    ).count()


def get_unpunches(
    target_date: datetime.date,
    branch: str,
    department: str,
) -> list[dict]:
    """
    Return employees marked STATUS_INCOMPLETE for target_date.

    STATUS_INCOMPLETE is set by the Celery task (check_missing_clockouts) only
    after shift_end + missing_punch_grace_minutes has passed.  Employees who are
    still within shift hours appear as 'present' and are NOT shown here.

    Each row includes correction_pending=True when the employee has already
    submitted a regularization request for this date.

    Case 1 (within shift): status=present → not returned.
    Case 3 (past grace):   status=incomplete → returned here.
    Case 4 (clocked out):  processor resets status → removed automatically.
    Case 5 (approved):     processor resets status after approval → removed.
    """
    from apps.attendance.models import AttendanceCorrection, AttendanceRecord
    from apps.attendance.services_unpunch import _expected_out_display, _get_settings

    employee_qs = User.objects.filter(is_active=True)
    if branch:
        employee_qs = employee_qs.filter(branch=branch)
    if department:
        employee_qs = employee_qs.filter(department=department)

    records = (
        AttendanceRecord.objects
        .filter(
            date=target_date,
            employee__in=employee_qs,
            status=AttendanceRecord.STATUS_INCOMPLETE,
        )
        .select_related('employee')
        .order_by('employee__full_name')
    )

    # Employees who already submitted a pending correction for this date
    pending_employee_ids = set(
        AttendanceCorrection.objects
        .filter(
            date=target_date,
            employee__in=employee_qs,
            status=AttendanceCorrection.STATUS_PENDING,
        )
        .values_list('employee_id', flat=True)
    )
    # Correction IDs keyed by employee_id for quick lookup
    pending_correction_ids: dict = dict(
        AttendanceCorrection.objects
        .filter(
            date=target_date,
            employee__in=employee_qs,
            status=AttendanceCorrection.STATUS_PENDING,
        )
        .values_list('employee_id', 'id')
    )

    cfg          = _get_settings()
    expected_out = _expected_out_display(cfg)

    return [
        {
            'employee_id':        r.employee.employee_id or '',
            'name':               r.employee.full_name or '',
            'initials':           _initials(r.employee.full_name or ''),
            'date':               target_date.strftime('%Y-%m-%d'),
            'clock_in':           r.first_punch_in.strftime('%H:%M') if r.first_punch_in else '—',
            'expected_out':       expected_out,
            'branch':             r.employee.branch or '—',
            'correction_pending': r.employee_id in pending_employee_ids,
            'correction_id':      str(pending_correction_ids[r.employee_id])
                                  if r.employee_id in pending_correction_ids else None,
        }
        for r in records
    ]


def _initials(name: str) -> str:
    parts = name.strip().split()
    if len(parts) >= 2:
        return (parts[0][0] + parts[-1][0]).upper()
    return name[:2].upper() if name else '??'
