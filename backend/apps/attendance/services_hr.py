"""
HR Attendance Management — Dashboard + List + Detail + Reprocess services.
"""
from __future__ import annotations

import datetime
import hashlib
import logging

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.db.models import Count, OuterRef, Subquery, Q

from apps.attendance.models import AttendanceRecord, AttendancePunch

logger = logging.getLogger(__name__)
User = get_user_model()

_TTL_DASHBOARD_STATS = 60  # seconds — action-queue-ish tab badges, kept near-real-time

# Statuses that mean "not absent" — employee showed up, regardless of clock-out status
_NON_ABSENT = {'present', 'late', 'half_day', 'weekly_off', 'holiday', 'on_leave', 'incomplete'}


# ── Format helpers ────────────────────────────────────────────────────────────

def _fmt_time(t: datetime.time | None) -> str:
    return t.strftime('%H:%M') if t else '—'


def _fmt_minutes(minutes: int) -> str:
    if not minutes:
        return '—'
    h, m = divmod(minutes, 60)
    return f'{h}h {m:02d}m'


def _initials(name: str) -> str:
    parts = name.strip().split()
    if len(parts) >= 2:
        return (parts[0][0] + parts[-1][0]).upper()
    return name[:2].upper() if name else '??'


# ── Dashboard ─────────────────────────────────────────────────────────────────

def _dashboard_stats_cache_key(
    target_date: datetime.date, branch: str, department: str,
    employee_ids: list[str] | None,
) -> str:
    if employee_ids is not None:
        # A manager's team can be a long ID list — hash it to keep the key short.
        scope = 'emp:' + hashlib.md5(
            ','.join(sorted(str(i) for i in employee_ids)).encode()
        ).hexdigest()
    else:
        scope = f'branch:{branch or "all"}:{department or "all"}'
    return f'attendance_dashboard_stats:{target_date.isoformat()}:{scope}'


def get_dashboard_stats(
    target_date: datetime.date, branch: str, department: str,
    employee_ids: list[str] | None = None,
) -> dict:
    """
    Return stat cards + summary chips + tab badge counts for the given date.

    employee_ids: when provided (a manager's direct reports), restricts the
    scope to exactly those employees and branch/department are ignored —
    a manager sees only their own team, never the rest of their branch.

    Cached for a short TTL: the tab badges (invalid punches, un-punches) feed
    directly into an HR action queue, so staleness is capped low enough that
    no one correcting attendance in real time would notice it.
    """
    cache_key = _dashboard_stats_cache_key(target_date, branch, department, employee_ids)
    cached = cache.get(cache_key)
    if cached is not None:
        return cached

    employee_qs = User.objects.filter(is_active=True)
    if employee_ids is not None:
        employee_qs = employee_qs.filter(id__in=employee_ids)
    elif branch:
        employee_qs = employee_qs.filter(branch=branch)
    if department:
        employee_qs = employee_qs.filter(department=department)

    total_employees = employee_qs.count()

    # Single aggregation query — no Python-side counting
    status_counts: dict[str, int] = {
        row['status']: row['cnt']
        for row in (
            AttendanceRecord.objects
            .filter(date=target_date, employee__in=employee_qs)
            .values('status')
            .annotate(cnt=Count('id'))
        )
    }

    # Absent = total − everyone who has a non-absent status
    # This correctly handles employees with no record (implicitly absent)
    # and employees with an explicit absent record.
    non_absent_total = sum(status_counts.get(s, 0) for s in _NON_ABSENT)
    absent = total_employees - non_absent_total

    incomplete    = status_counts.get('incomplete', 0)
    # Employees still working (open session) count as present on the stat card.
    # Employees marked incomplete (past grace, no clock-out) also came in — include them.
    present_today = status_counts.get('present', 0) + status_counts.get('late', 0) + incomplete
    late_arrivals  = status_counts.get('late', 0)
    on_leave       = status_counts.get('on_leave', 0)

    invalid_count = _count_invalid_punches(target_date, branch, department, employee_ids)
    unpunch_count = _count_unpunches(target_date, branch, department, employee_ids)

    result = {
        'stat_cards': {
            'present_today':   present_today,
            'absent':          absent,
            'late_arrivals':   late_arrivals,
            'on_leave':        on_leave,
            'total_employees': total_employees,
        },
        'summary_chips': {
            'present':    status_counts.get('present', 0),
            'late':       status_counts.get('late', 0),
            'absent':     absent,
            'on_leave':   on_leave,
            'half_day':   status_counts.get('half_day', 0),
            'weekly_off': status_counts.get('weekly_off', 0),
            'holiday':    status_counts.get('holiday', 0),
            'incomplete': incomplete,
        },
        'tab_badges': {
            'invalid_punches': invalid_count,
            'un_punches':      unpunch_count,
        },
    }
    cache.set(cache_key, result, _TTL_DASHBOARD_STATS)
    return result


# ── Reprocess ─────────────────────────────────────────────────────────────────

def reprocess_date(
    target_date: datetime.date,
    branch: str,
    department: str,
    performed_by=None,
    employee_ids: list[str] | None = None,
) -> dict:
    """
    Reprocess AttendanceRecord for employees who have punches OR existing records on target_date.

    Covering both sets ensures records are recalculated after settings changes even
    for employees who appear as absent (no punches but a stale record).
    Safe to run multiple times. Returns a summary of what was updated.

    employee_ids: when provided (a manager's direct reports), restricts the
    scope to exactly those employees instead of branch/department.
    """
    from apps.attendance.models import AttendanceAuditLog
    from apps.attendance.services_attendance import AttendanceProcessorService
    from apps.attendance.services_audit_log import write_audit_log

    employee_qs = User.objects.filter(is_active=True)
    if employee_ids is not None:
        employee_qs = employee_qs.filter(id__in=employee_ids)
    elif branch:
        employee_qs = employee_qs.filter(branch=branch)
    if department:
        employee_qs = employee_qs.filter(department=department)

    punched_ids = set(
        AttendancePunch.objects
        .filter(punched_at__date=target_date, employee__in=employee_qs)
        .values_list('employee_id', flat=True)
        .distinct()
    )
    record_ids = set(
        AttendanceRecord.objects
        .filter(date=target_date, employee__in=employee_qs)
        .values_list('employee_id', flat=True)
    )
    all_ids = punched_ids | record_ids

    updated = 0
    errors  = 0

    for employee in employee_qs.filter(pk__in=all_ids).iterator(chunk_size=200):
        try:
            record = AttendanceProcessorService.process_day(employee, target_date)
            write_audit_log(
                employee=employee,
                date=target_date,
                event=AttendanceAuditLog.EVENT_REPROCESSED,
                performed_by=performed_by,
                record=record,
                new_value=record.status if record else '',
                action='Attendance reprocessed by HR',
            )
            updated += 1
        except Exception as exc:
            logger.error('Reprocess failed for %s on %s: %s', employee.pk, target_date, exc)
            errors += 1

    # Reprocessing changes the exact numbers get_dashboard_stats reports for
    # this date/scope — don't make HR wait out the TTL to see their own action.
    cache.delete(_dashboard_stats_cache_key(target_date, branch, department, employee_ids))

    return {
        'date':    target_date.isoformat(),
        'updated': updated,
        'errors':  errors,
    }


# ── Attendance list ───────────────────────────────────────────────────────────

def get_attendance_list(filters: dict) -> list[dict]:
    """
    Return attendance rows for all active employees on `date`.

    Employees without an AttendanceRecord appear with status='absent'.
    Uses Subquery annotations — one DB round-trip, no N+1.
    """
    target_date  = filters['date']
    branch       = filters.get('branch', '')
    department   = filters.get('department', '')
    employee_ids = filters.get('employee_ids')
    status_f     = filters.get('status', '')
    search       = filters.get('search', '').strip()
    sort_by      = filters.get('sort_by', 'name')
    sort_dir     = filters.get('sort_dir', 'asc')

    employee_qs = User.objects.filter(is_active=True)
    if employee_ids is not None:
        employee_qs = employee_qs.filter(id__in=employee_ids)
    elif branch:
        employee_qs = employee_qs.filter(branch=branch)
    if department:
        employee_qs = employee_qs.filter(department=department)
    if search:
        employee_qs = employee_qs.filter(
            Q(full_name__icontains=search) | Q(employee_id__icontains=search)
        )

    rec_qs = AttendanceRecord.objects.filter(date=target_date)

    employee_qs = employee_qs.annotate(
        _rec_id   = Subquery(rec_qs.filter(employee=OuterRef('pk')).values('id')[:1]),
        _status   = Subquery(rec_qs.filter(employee=OuterRef('pk')).values('status')[:1]),
        _clock_in = Subquery(rec_qs.filter(employee=OuterRef('pk')).values('first_punch_in')[:1]),
        _clock_out= Subquery(rec_qs.filter(employee=OuterRef('pk')).values('last_punch_out')[:1]),
        _minutes  = Subquery(rec_qs.filter(employee=OuterRef('pk')).values('total_working_minutes')[:1]),
        _ot_min   = Subquery(rec_qs.filter(employee=OuterRef('pk')).values('overtime_minutes')[:1]),
        _is_late  = Subquery(rec_qs.filter(employee=OuterRef('pk')).values('is_late')[:1]),
    )

    if status_f:
        if status_f == 'absent':
            employee_qs = employee_qs.filter(
                Q(_status='absent') | Q(_status__isnull=True)
            )
        else:
            employee_qs = employee_qs.filter(_status=status_f)

    _sort_map = {
        'name': 'full_name', 'employee_id': 'employee_id',
        'department': 'department', 'branch': 'branch',
        'clock_in': '_clock_in', 'status': '_status',
    }
    order_field = _sort_map.get(sort_by, 'full_name')
    if sort_dir == 'desc':
        order_field = f'-{order_field}'
    employee_qs = employee_qs.order_by(order_field)

    rows = []
    for user in employee_qs:
        status_key = user._status or 'absent'
        rows.append({
            'record_id':   str(user._rec_id) if user._rec_id else None,
            'employee_id': user.employee_id or '',
            'name':        user.full_name or '',
            'initials':    _initials(user.full_name or ''),
            'department':  user.department or '',
            'branch':      user.branch or '',
            'clock_in':    _fmt_time(user._clock_in),
            'clock_out':   _fmt_time(user._clock_out),
            'total_hours': _fmt_minutes(user._minutes or 0),
            'ot':          _fmt_minutes(user._ot_min or 0),
            'status':      AttendanceRecord.STATUS_DISPLAY_MAP.get(status_key, status_key.title()),
            'status_key':  status_key,
            'is_late':     bool(user._is_late),
        })
    return rows


# ── Attendance detail ─────────────────────────────────────────────────────────

def get_attendance_detail(
    record_id: str, target_date: datetime.date, employee_id_str: str,
    employee_ids: list[str] | None = None,
) -> dict | None:
    """
    Return full detail with punch list for one employee on a date.

    employee_ids: when provided (a manager's direct reports), the record's
    employee must be in this set or None is returned (same as not-found) —
    prevents a manager from looking up an arbitrary employee's record by ID.
    """
    try:
        if record_id:
            record = AttendanceRecord.objects.select_related('employee').get(id=record_id)
        else:
            user = User.objects.get(employee_id=employee_id_str)
            record = AttendanceRecord.objects.select_related('employee').get(
                employee=user, date=target_date
            )
    except (AttendanceRecord.DoesNotExist, User.DoesNotExist):
        return None

    if employee_ids is not None and str(record.employee_id) not in {str(i) for i in employee_ids}:
        return None

    punches = (
        AttendancePunch.objects
        .filter(employee=record.employee, punched_at__date=record.date)
        .order_by('punched_at')
    )

    punch_list = [
        {
            'punch_type':  p.punch_type,
            'time':        p.punch_time_display,
            'source':      p.source,
            'mode':        p.attendance_mode,
            'is_geofence': p.is_inside_geofence,
            'distance_m':  float(p.calculated_distance) if p.calculated_distance else None,
        }
        for p in punches
    ]

    user = record.employee
    return {
        'record_id':     str(record.id),
        'employee_id':   user.employee_id or '',
        'name':          user.full_name or '',
        'department':    user.department or '',
        'branch':        user.branch or '',
        'date':          record.date,
        'status':        record.status_display,
        'status_key':    record.status,
        'clock_in':      _fmt_time(record.first_punch_in),
        'clock_out':     _fmt_time(record.last_punch_out),
        'total_hours':   record.total_hours_display,
        'overtime':      _fmt_minutes(record.overtime_minutes),
        'is_late':       record.is_late,
        'is_early_exit': record.is_early_exit,
        'note':          record.note or '',
        'punches':       punch_list,
    }


# ── Private badge count helpers ───────────────────────────────────────────────

def _count_invalid_punches(
    target_date: datetime.date, branch: str, department: str,
    employee_ids: list[str] | None = None,
) -> int:
    from apps.attendance.services_hr_audit import get_invalid_punch_count
    return get_invalid_punch_count(target_date, branch, department, employee_ids)


def _count_unpunches(
    target_date: datetime.date, branch: str, department: str,
    employee_ids: list[str] | None = None,
) -> int:
    from apps.attendance.services_hr_audit import get_unpunch_count
    return get_unpunch_count(target_date, branch, department, employee_ids)
