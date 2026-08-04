"""
HR Attendance Management — Dashboard + List + Detail + Reprocess services.
"""
from __future__ import annotations

import datetime
import hashlib
import logging

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.db import transaction
from django.db.models import Count, OuterRef, Subquery, Q

from apps.attendance.models import AttendanceRecord, AttendancePunch, EmployeeWeeklyOffAssignment

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
    audit_entries = []

    for employee in employee_qs.filter(pk__in=all_ids).iterator(chunk_size=200):
        try:
            record = AttendanceProcessorService.process_day(employee, target_date)
            # Collected instead of written per-employee (was one INSERT per
            # employee via write_audit_log) — bulk_create()'d once below.
            audit_entries.append(AttendanceAuditLog(
                record=record,
                employee=employee,
                date=target_date,
                event=AttendanceAuditLog.EVENT_REPROCESSED,
                old_value='',
                new_value=record.status if record else '',
                action='Attendance reprocessed by HR',
                performed_by=performed_by,
                remarks='',
            ))
            updated += 1
        except Exception as exc:
            logger.error('Reprocess failed for %s on %s: %s', employee.pk, target_date, exc)
            errors += 1

    if audit_entries:
        try:
            AttendanceAuditLog.objects.bulk_create(audit_entries, batch_size=500)
        except Exception as exc:
            # Audit log failures must never surface to the caller — matches
            # write_audit_log()'s own swallow-and-log behaviour.
            logger.error('Bulk audit log write failed for reprocess on %s: %s', target_date, exc)

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


# ─── Weekly Off Assignment ─────────────────────────────────────────────────────
#
# Assigns a WeeklyDayPolicy (configured under Settings -> Attendance Rules ->
# Weekly Off Patterns — the existing WeeklyDayPolicy CRUD) to a specific
# employee, effective from a given date. History is preserved, never
# overwritten: assigning a new pattern closes out the employee's previously-
# open row (effective_to) instead of deleting/mutating it, so past attendance/
# leave/payroll calculations keep resolving against whatever pattern was
# actually in effect on that date. Every calculation resolves the effective
# pattern through the single centralized resolver —
# core.cache_service.WeeklyOffCacheService.get_effective()/get_effective_range()
# — not through this module directly.

def _current_weekly_off_subqueries(as_of: datetime.date) -> dict:
    """Subquery annotations for each employee's assignment open as_of a date — one query, no N+1."""
    current_qs = (
        EmployeeWeeklyOffAssignment.objects
        .filter(employee=OuterRef('pk'), effective_from__lte=as_of)
        .filter(Q(effective_to__isnull=True) | Q(effective_to__gte=as_of))
        .order_by('-effective_from')
    )
    return {
        '_woa_id':             Subquery(current_qs.values('id')[:1]),
        '_woa_policy_id':      Subquery(current_qs.values('policy_id')[:1]),
        '_woa_policy_name':    Subquery(current_qs.values('policy__name')[:1]),
        '_woa_effective_from': Subquery(current_qs.values('effective_from')[:1]),
        '_woa_effective_to':   Subquery(current_qs.values('effective_to')[:1]),
    }


def build_weekly_off_assignment_queryset(filters: dict):
    """
    Filtered/annotated/ordered User queryset — one row per active employee,
    with their CURRENT weekly-off assignment (if any) as of today attached via
    Subquery. NOT evaluated here — the caller pages it with core.pagination
    before converting rows to dicts, so only one page of employees is ever
    actually fetched from the database (safe for 2,000+ employees).

    filters: branch, department, pattern (policy id), status
             ('assigned'|'unassigned'|''), search, employee_ids (manager scope)
    """
    branch       = filters.get('branch', '')
    department   = filters.get('department', '')
    pattern_id   = filters.get('pattern', '')
    status_f     = filters.get('status', '')
    search       = filters.get('search', '').strip()
    employee_ids = filters.get('employee_ids')

    today = datetime.date.today()
    qs = User.objects.filter(is_active=True)
    if employee_ids is not None:
        qs = qs.filter(id__in=employee_ids)
    elif branch:
        qs = qs.filter(branch=branch)
    if department:
        qs = qs.filter(department=department)
    if search:
        qs = qs.filter(Q(full_name__icontains=search) | Q(employee_id__icontains=search))

    qs = qs.annotate(**_current_weekly_off_subqueries(today))

    if pattern_id:
        qs = qs.filter(_woa_policy_id=pattern_id)
    if status_f == 'assigned':
        qs = qs.exclude(_woa_id__isnull=True)
    elif status_f == 'unassigned':
        qs = qs.filter(_woa_id__isnull=True)

    return qs.order_by('full_name')


def serialize_weekly_off_assignment_row(user) -> dict:
    """Build one list row from a User instance annotated by build_weekly_off_assignment_queryset()."""
    return {
        'employee_id':    user.employee_id or '',
        'employee_name':  user.full_name or '',
        'department':     user.department or '',
        'branch':         user.branch or '',
        'pattern_id':     str(user._woa_policy_id) if user._woa_policy_id else None,
        'pattern_name':   user._woa_policy_name or None,
        'effective_from': user._woa_effective_from.strftime('%Y-%m-%d') if user._woa_effective_from else None,
        'effective_to':   user._woa_effective_to.strftime('%Y-%m-%d') if user._woa_effective_to else None,
        'status':         'Assigned' if user._woa_policy_id else 'Not Assigned',
    }


def get_weekly_off_assignment_history(employee_id: str) -> list[dict]:
    """Full weekly-off assignment history for one employee, newest first."""
    rows = (
        EmployeeWeeklyOffAssignment.objects
        .filter(employee__employee_id=employee_id)
        .select_related('policy')
        .order_by('-effective_from')
    )
    return [
        {
            'id':             str(r.id),
            'pattern_id':     str(r.policy_id),
            'pattern_name':   r.policy.name,
            'effective_from': r.effective_from.strftime('%Y-%m-%d'),
            'effective_to':   r.effective_to.strftime('%Y-%m-%d') if r.effective_to else None,
            'is_current':     r.effective_to is None,
        }
        for r in rows
    ]


@transaction.atomic
def bulk_assign_weekly_off(employee_codes: list, policy, effective_from: datetime.date, actor=None) -> int:
    """
    Assign `policy` to every employee whose human-readable employee_id is in
    `employee_codes` (matching what the list/history helpers above expose —
    not the internal User UUID pk), effective `effective_from`. Preserves
    history: each employee's currently-open assignment (if it started before
    this new one) is closed out (effective_to = effective_from - 1 day),
    never deleted or overwritten. An open row that starts on/after the new
    effective_from is superseded outright (correcting a future-dated
    assignment before it took effect).

    Four queries total regardless of len(employee_codes) — safe for 2,000+.
    """
    if not employee_codes:
        return 0

    user_ids = list(
        User.objects.filter(employee_id__in=employee_codes, is_active=True).values_list('id', flat=True)
    )
    if not user_ids:
        return 0

    day_before = effective_from - datetime.timedelta(days=1)

    (
        EmployeeWeeklyOffAssignment.objects
        .filter(employee_id__in=user_ids, effective_to__isnull=True, effective_from__lt=effective_from)
        .update(effective_to=day_before, updated_by=actor)
    )
    (
        EmployeeWeeklyOffAssignment.objects
        .filter(employee_id__in=user_ids, effective_to__isnull=True, effective_from__gte=effective_from)
        .delete()
    )
    EmployeeWeeklyOffAssignment.objects.bulk_create([
        EmployeeWeeklyOffAssignment(
            employee_id=uid, policy=policy, effective_from=effective_from,
            created_by=actor, updated_by=actor,
        )
        for uid in user_ids
    ])
    logger.info(
        'Weekly-off pattern "%s" assigned to %d employee(s) effective %s by %s',
        policy.policy_code, len(user_ids), effective_from, getattr(actor, 'email', 'system'),
    )
    return len(user_ids)


def assign_weekly_off(employee_code: str, policy, effective_from: datetime.date, actor=None):
    """Single-employee convenience wrapper around bulk_assign_weekly_off()."""
    count = bulk_assign_weekly_off([employee_code], policy, effective_from, actor)
    if count == 0:
        return None
    return (
        EmployeeWeeklyOffAssignment.objects
        .filter(employee__employee_id=employee_code, effective_to__isnull=True)
        .select_related('policy')
        .first()
    )
