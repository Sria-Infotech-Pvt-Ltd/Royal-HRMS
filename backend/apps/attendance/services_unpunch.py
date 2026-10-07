"""
Un-punch detection service.

Called by the Celery periodic task every 5 minutes.  Finds employees who
clocked IN but have not clocked OUT after their shift end + configured grace
period, marks their AttendanceRecord as STATUS_INCOMPLETE, and sends a
missing clock-out notification (one per employee per day, de-duplicated).

Performance notes for 2,000+ employees:
  - ONE query to find open records for today
  - ONE bulk UPDATE to mark them incomplete
  - ONE query to find already-notified employees
  - ONE bulk INSERT for new notifications
  - Per-employee loop only for the notification delivery itself
"""
from __future__ import annotations

import logging
from datetime import date, datetime, time, timedelta

from django.contrib.auth import get_user_model
from django.db import transaction
from django.utils import timezone

logger = logging.getLogger(__name__)
User = get_user_model()

_DEFAULT_GRACE_MINUTES = 10


# ── Config helpers ─────────────────────────────────────────────────────────────

def _get_settings():
    from apps.attendance.services_attendance import _get_settings as _gs
    return _gs()


def _shift_end_deadline(cfg) -> time | None:
    """
    Returns the time (IST, naive) after which a missing clock-out becomes an
    un-punch, using the org-wide default shift: shift_end +
    missing_punch_grace_minutes. Returns None if settings are not configured
    (always run detection).

    This is the GLOBAL default deadline only — used as a display fallback
    (_expected_out_display) and as one input to _earliest_possible_deadline()
    below. The actual per-employee decision of who is overdue is made by
    _resolve_deadlines() against each employee's own effective shift (their
    assignment, or this same global default when they have none).
    """
    if not cfg or not hasattr(cfg, 'working_hours'):
        return None
    wh = cfg.working_hours
    grace = getattr(wh, 'missing_punch_grace_minutes', _DEFAULT_GRACE_MINUTES)
    deadline = (
        datetime.combine(date.today(), wh.shift_end) + timedelta(minutes=grace)
    ).time()
    return deadline


def _earliest_possible_deadline(cfg) -> time | None:
    """
    Lower bound used only to short-circuit the Celery run when NO employee's
    shift could possibly have ended yet — cheap enough to compute every 5
    minutes (one small, rarely-changing table). Must consider every
    WorkingHoursPolicy's end_time, not just the global default, so an
    SGT/ICT employee (16:30 end) is checked as soon as 16:30 + grace passes,
    instead of being delayed until the global default's 18:00 + grace the way
    a single global deadline would. The actual per-employee overdue decision
    still happens later in _resolve_deadlines() / detect_and_mark_unpunches();
    this only decides whether it's worth querying at all.

    Deliberately NOT filtered by is_active: deactivating a policy (soft
    delete) doesn't reassign or clear any EmployeeShiftAssignment still
    pointing at it — PROTECT only blocks a hard delete, not deactivation —
    so an employee can still be resolved against a now-inactive policy by
    _resolve_deadlines()/ShiftCacheService. Excluding inactive policies here
    would let this floor skip past such an employee's real deadline, delaying
    detection until a later run. Including a stale/unused policy's end_time
    only makes this floor more conservative (runs the real check slightly
    more often) — never causes a miss, so there's no reason to filter here.
    """
    global_deadline = _shift_end_deadline(cfg)
    if global_deadline is None:
        return None
    wh = cfg.working_hours
    grace = getattr(wh, 'missing_punch_grace_minutes', _DEFAULT_GRACE_MINUTES)
    end_times = [wh.shift_end]
    try:
        from apps.attendance.models import WorkingHoursPolicy
        end_times += list(
            WorkingHoursPolicy.objects.values_list('end_time', flat=True)
        )
    except Exception:
        logger.warning('WorkingHoursPolicy lookup failed while computing earliest deadline')
    earliest_end = min(end_times)
    return (datetime.combine(date.today(), earliest_end) + timedelta(minutes=grace)).time()


def _resolve_deadlines(employee_ids: list, cfg) -> dict:
    """
    Per-employee missing-clock-out deadline for target_date's open records —
    ONE extra query regardless of len(employee_ids) (via
    ShiftCacheService.get_effective_map), no N+1. The missing-punch grace
    period itself stays the single global
    AttendanceWorkingHours.missing_punch_grace_minutes value for everyone
    (WorkingHoursPolicy has no equivalent field of its own) — only the shift
    end time this grace is added to varies per employee.
    """
    from core.cache_service import ShiftCacheService
    grace = _DEFAULT_GRACE_MINUTES
    if cfg and hasattr(cfg, 'working_hours'):
        grace = getattr(cfg.working_hours, 'missing_punch_grace_minutes', _DEFAULT_GRACE_MINUTES)
    shift_map = ShiftCacheService.get_effective_map(employee_ids, date.today())
    return {
        eid: (datetime.combine(date.today(), shift.end_time) + timedelta(minutes=grace)).time()
        for eid, shift in shift_map.items()
    }


def _expected_out_display(cfg) -> str:
    """Shift end as 'HH:MM' for the API response — global-default fallback.
    See services_hr_audit.get_unpunches() for the per-employee version used
    once a record is actually being displayed."""
    if cfg and hasattr(cfg, 'working_hours'):
        return cfg.working_hours.shift_end.strftime('%H:%M')
    return '18:00'


def _now_ist() -> time:
    """Current time in IST as a naive time object for comparison."""
    from zoneinfo import ZoneInfo
    return datetime.now(ZoneInfo('Asia/Kolkata')).replace(tzinfo=None).time()


# ══════════════════════════════════════════════════════════════════════════════
#  Main detection function
# ══════════════════════════════════════════════════════════════════════════════

def detect_and_mark_unpunches(
    target_date: date,
    branch: str = '',
    department: str = '',
) -> dict:
    """
    Bulk-mark employees as STATUS_INCOMPLETE and send one notification each.

    Returns: {'marked': int, 'notified': int, 'skipped': int, 'reason': str}

    Design:
      - If current IST time is before the earliest deadline ANY shift could
        possibly produce today, return early (nothing could be overdue yet).
      - Each employee is then checked against their OWN effective shift's
        deadline (their assignment, or the global default when unassigned) —
        not a single global cutoff, so a UK-shift employee (12:00-21:00)
        isn't wrongly flagged while still legitimately working, and an
        SGT/ICT employee (07:30-16:30) is caught as soon as their own shift's
        grace period elapses instead of waiting for everyone else's.
      - Employees on weekly_off / holiday / on_leave are excluded.
      - Already-incomplete records are excluded (idempotent re-runs).
    """
    from apps.attendance.models import AttendanceRecord

    cfg              = _get_settings()
    earliest_deadline = _earliest_possible_deadline(cfg)
    current_time      = _now_ist()

    if earliest_deadline is not None and current_time <= earliest_deadline:
        return {
            'marked': 0, 'notified': 0, 'skipped': 0,
            'reason': f'shift_not_ended (earliest_deadline={earliest_deadline.strftime("%H:%M")})',
        }

    employee_qs = User.objects.filter(is_active=True)
    if branch:
        employee_qs = employee_qs.filter(branch=branch)
    if department:
        employee_qs = employee_qs.filter(department=department)

    # All open sessions not yet marked — same single query as before; the
    # per-employee deadline filter below is applied in Python against this
    # already-small result set (open sessions are rare), not pushed into a
    # second query per employee.
    open_records = list(
        AttendanceRecord.objects
        .filter(
            date=target_date,
            employee__in=employee_qs,
            first_punch_in__isnull=False,
            last_punch_out__isnull=True,
            status__in=[
                AttendanceRecord.STATUS_PRESENT,
                AttendanceRecord.STATUS_LATE,
            ],
        )
        .select_related('employee')
        .order_by('employee__full_name')
    )

    if not open_records:
        return {'marked': 0, 'notified': 0, 'skipped': 0, 'reason': 'none_found'}

    # One bulk query resolves every open record's employee-specific deadline
    # (assignment or global default) — no N+1.
    deadlines = _resolve_deadlines([r.employee_id for r in open_records], cfg)
    overdue_records = [
        r for r in open_records
        if current_time > deadlines.get(r.employee_id, earliest_deadline)
    ]

    if not overdue_records:
        return {'marked': 0, 'notified': 0, 'skipped': 0, 'reason': 'none_overdue_yet'}

    record_ids    = [r.pk for r in overdue_records]

    # ── Bulk mark incomplete ───────────────────────────────────────────────────
    with transaction.atomic():
        marked = AttendanceRecord.objects.filter(pk__in=record_ids).update(
            status=AttendanceRecord.STATUS_INCOMPLETE,
            note='Missing clock-out — shift ended without a punch-out.',
            updated_at=timezone.now(),
        )

    logger.info('Un-punch detection: marked %d records incomplete on %s', marked, target_date)

    # ── Notifications (one per employee per date per channel) ──────────────────
    notified = _notify_employees(overdue_records, target_date)

    return {
        'marked':   marked,
        'notified': notified,
        'skipped':  len(overdue_records) - marked,
        'reason':   'ok',
    }


# ── Notification helpers ───────────────────────────────────────────────────────

def _notify_employees(records: list, target_date: date) -> int:
    """
    Send a missing clock-out notification to each employee who hasn't been
    notified today.  Uses bulk_create with ignore_conflicts for deduplication.
    """
    from apps.attendance.models import MissingPunchNotification

    employee_ids = [r.employee_id for r in records]

    # Find employees already notified today via email
    already_notified = set(
        MissingPunchNotification.objects.filter(
            employee_id__in=employee_ids,
            date=target_date,
            channel='email',
        ).values_list('employee_id', flat=True)
    )

    unnotified_records = [r for r in records if r.employee_id not in already_notified]
    if not unnotified_records:
        return 0

    # Bulk-create notification log entries
    notification_objs = [
        MissingPunchNotification(
            employee=r.employee,
            date=target_date,
            channel='email',
        )
        for r in unnotified_records
    ]
    MissingPunchNotification.objects.bulk_create(notification_objs, ignore_conflicts=True)

    # Deliver notifications
    notified = 0
    for record in unnotified_records:
        try:
            _deliver(record.employee, target_date)
            notified += 1
        except Exception as exc:
            logger.error(
                'Notification delivery failed for employee=%s date=%s: %s',
                record.employee_id, target_date, exc,
            )

    return notified


def _deliver(employee, target_date: date) -> None:
    """
    Deliver the missing clock-out notification.

    Current channels: email.
    Future channels: in-app, push, SMS — add a branch here when each is built.
    """
    subject = 'Reminder: You forgot to Clock Out today'
    message = (
        'You forgot to Clock Out today. '
        'Please Clock Out or submit a correction request.'
    )

    # Email — uses the project's shared SMTP utility (see CLAUDE.md)
    try:
        from apps.accounts.models import Company
        from apps.accounts.utils import send_template_email
        company = Company.objects.first()
        send_template_email(
            recipient_email=employee.email,
            template_name='attendance_missing_clockout',
            context={
                'employee_name': getattr(employee, 'full_name', None) or employee.email,
                'date_display':  target_date.strftime('%A, %d %B %Y'),
                'subject':       subject,
                'message':       message,
                'company_name':  company.company_name if company else '',
            },
        )
    except Exception as exc:
        logger.warning(
            'Email send failed for employee=%s: %s — notification logged but not sent',
            employee.pk, exc,
        )

    # TODO: in_app  → call InAppNotificationService.create(employee, message) when module is built
    # TODO: push    → call PushNotificationService.send(employee, message)   when module is built

    logger.info(
        'Missing clock-out notification dispatched: employee=%s date=%s',
        employee.pk, target_date,
    )
