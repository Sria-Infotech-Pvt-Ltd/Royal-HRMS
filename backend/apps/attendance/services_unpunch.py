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
from decimal import Decimal

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
    un-punch: shift_end + missing_punch_grace_minutes.
    Returns None if settings are not configured (always run detection).
    """
    if not cfg or not hasattr(cfg, 'working_hours'):
        return None
    wh = cfg.working_hours
    grace = getattr(wh, 'missing_punch_grace_minutes', _DEFAULT_GRACE_MINUTES)
    deadline = (
        datetime.combine(date.today(), wh.shift_end) + timedelta(minutes=grace)
    ).time()
    return deadline


def _expected_out_display(cfg) -> str:
    """Shift end as 'HH:MM' for the API response."""
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
      - If current IST time <= deadline, return early (shift not ended yet).
      - Employees on weekly_off / holiday / on_leave are excluded.
      - Already-incomplete records are excluded (idempotent re-runs).
    """
    from apps.attendance.models import AttendanceRecord

    cfg           = _get_settings()
    deadline      = _shift_end_deadline(cfg)
    current_time  = _now_ist()

    if deadline is not None and current_time <= deadline:
        return {
            'marked': 0, 'notified': 0, 'skipped': 0,
            'reason': f'shift_not_ended (deadline={deadline.strftime("%H:%M")})',
        }

    employee_qs = User.objects.filter(is_active=True)
    if branch:
        employee_qs = employee_qs.filter(branch=branch)
    if department:
        from apps.accounts.services_approval import filter_queryset_by_department_name
        employee_qs = filter_queryset_by_department_name(employee_qs, department)

    # All open sessions not yet marked
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

    record_ids    = [r.pk for r in open_records]

    # ── Bulk mark, per the configured missing_punch_action ────────────────────
    # PunchRulesPolicy.missing_punch_action was fully modeled, admin-editable,
    # and validated but never actually read — every un-punch was unconditionally
    # marked STATUS_INCOMPLETE regardless of what was configured. All open
    # records in one sweep get the same treatment (there's one active default
    # policy, not a per-employee one), so this stays a single bulk UPDATE either
    # way — the performance characteristics this function's docstring cares
    # about for 2,000+ employees are unchanged.
    from apps.attendance.models import PunchRulesPolicy
    policy = PunchRulesPolicy.objects.filter(is_default=True, is_active=True).first()
    action = policy.missing_punch_action if policy else PunchRulesPolicy.MISSING_PUNCH_REGULARIZE

    update_fields = {'updated_at': timezone.now()}
    if action == PunchRulesPolicy.MISSING_PUNCH_ABSENT:
        # No verified clock-out to credit any hours against — treat the whole
        # day as not worked, same as a genuine no-show, for LOP purposes.
        update_fields['status'] = AttendanceRecord.STATUS_ABSENT
        update_fields['total_working_minutes'] = 0
        update_fields['note'] = 'Missing clock-out — marked absent per attendance policy.'
    elif action == PunchRulesPolicy.MISSING_PUNCH_HALF_DAY:
        update_fields['status'] = AttendanceRecord.STATUS_HALF_DAY
        update_fields['note'] = 'Missing clock-out — marked half day per attendance policy.'
    elif action == PunchRulesPolicy.MISSING_PUNCH_AUTO:
        # Auto-forgiven: credited as a full present day using the configured
        # minimum full-day hours (AttendancePunchRules.min_hours_full_day) —
        # there's no real clock-out to compute actual worked minutes from.
        # Also synthesizes last_punch_out (shift end) — without it, the
        # record would still match this same sweep's own open-session filter
        # (last_punch_out__isnull=True, status in [present, late]) on the
        # next run, since STATUS_PRESENT is one of the statuses it re-selects.
        cfg = _get_settings()
        min_hours = (
            cfg.punch_rules.min_hours_full_day
            if cfg and hasattr(cfg, 'punch_rules') else Decimal('8.00')
        )
        shift_end = (
            cfg.working_hours.shift_end
            if cfg and hasattr(cfg, 'working_hours') else time(18, 0)
        )
        update_fields['status'] = AttendanceRecord.STATUS_PRESENT
        update_fields['total_working_minutes'] = int(min_hours * 60)
        update_fields['last_punch_out'] = shift_end  # TimeField, not a datetime
        update_fields['note'] = 'Missing clock-out — auto-regularized per attendance policy.'
    else:
        # require_regularization (default) — unchanged from the original
        # behavior: flag it and let the employee submit a correction request.
        update_fields['status'] = AttendanceRecord.STATUS_INCOMPLETE
        update_fields['note'] = 'Missing clock-out — shift ended without a punch-out.'

    with transaction.atomic():
        marked = AttendanceRecord.objects.filter(pk__in=record_ids).update(**update_fields)

    logger.info(
        'Un-punch detection: marked %d records %s (action=%s) on %s',
        marked, update_fields['status'], action, target_date,
    )

    # ── Notifications (one per employee per date per channel) ──────────────────
    notified = _notify_employees(open_records, target_date)

    return {
        'marked':   marked,
        'notified': notified,
        'skipped':  len(open_records) - marked,
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
            module='attendance',
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
