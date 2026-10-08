"""
Attendance Celery tasks.

Registered in CELERY_BEAT_SCHEDULE (config/settings.py) for periodic execution.
"""
from __future__ import annotations

import logging

from celery import shared_task
from django.utils import timezone

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def check_missing_clockouts(self):
    """
    Periodic task: find employees who clocked IN today but never clocked OUT
    after shift_end + missing_punch_grace_minutes.

    Runs every 5 minutes (configured in CELERY_BEAT_SCHEDULE), once per
    active company (see apps.tenants.utils.run_for_all_tenants — this task
    has no single tenant of its own, it's scheduled, not dispatched from a
    request).  Safe to run multiple times — idempotent via
    STATUS_INCOMPLETE exclusion and MissingPunchNotification dedup.
    """
    from apps.tenants.models import MODULE_ATTENDANCE
    from apps.tenants.utils import run_for_all_tenants

    def _run_for_one_tenant():
        from apps.attendance.services_unpunch import detect_and_mark_unpunches
        today = timezone.localdate()   # Uses Django TIME_ZONE = 'Asia/Kolkata'
        return detect_and_mark_unpunches(target_date=today)

    try:
        result = run_for_all_tenants(
            _run_for_one_tenant, task_name='check_missing_clockouts', required_module=MODULE_ATTENDANCE,
        )
        logger.info('check_missing_clockouts: %s', result)
        return result
    except Exception as exc:
        logger.error('check_missing_clockouts failed: %s', exc, exc_info=True)
        raise self.retry(exc=exc)


@shared_task(bind=True, max_retries=0, default_retry_delay=0)
def process_attendance_import(self, schema_name: str, import_log_id: str, imported_by_pk: str, csv_content: str):
    """
    Async worker for large CSV imports (> SYNC_THRESHOLD rows).

    Dispatched by import_attendance_csv when the file exceeds the synchronous
    processing threshold.  `schema_name` is the dispatching company's schema
    (captured from the request at dispatch time — the Celery worker
    executing this task runs in a separate process with no tenant of its
    own, see apps.tenants.utils.run_in_tenant). Reads the CSV content passed
    as a task argument, runs the same bulk import engine used by the sync
    path, and writes the final status back to AttendanceImportLog.
    """
    from apps.attendance.models import AttendanceImportLog
    from apps.attendance.services_hr_ops import _run_import_bulk
    from apps.tenants.utils import run_in_tenant
    from django.contrib.auth import get_user_model
    import csv as _csv
    import io as _io

    _User = get_user_model()

    def _do_import():
        import_log   = AttendanceImportLog.objects.get(id=import_log_id)
        imported_by  = _User.objects.get(pk=imported_by_pk)
        rows         = list(_csv.DictReader(_io.StringIO(csv_content)))
        _run_import_bulk(import_log, rows, imported_by)
        logger.info('process_attendance_import finished | import_id=%s', import_log_id)

    try:
        run_in_tenant(schema_name, _do_import)
    except AttendanceImportLog.DoesNotExist:
        logger.error('process_attendance_import: import_log %s not found', import_log_id)
    except _User.DoesNotExist:
        logger.error('process_attendance_import: user %s not found', imported_by_pk)
    except Exception as exc:
        logger.error('process_attendance_import failed: %s', exc, exc_info=True)
        try:
            def _mark_failed():
                log = AttendanceImportLog.objects.get(id=import_log_id)
                if log.status == AttendanceImportLog.STATUS_PROCESSING:
                    log.status = AttendanceImportLog.STATUS_FAILED
                    log.save(update_fields=['status', 'updated_at'])
            run_in_tenant(schema_name, _mark_failed)
        except Exception:
            pass
        raise


@shared_task(bind=True, max_retries=3, default_retry_delay=300)
def check_absence_alerts(self):
    """
    Daily task: fire absence notifications for employees absent N+ consecutive
    working days without approved leave — once per active company (see
    apps.tenants.utils.run_for_all_tenants).

    Threshold and recipients come from AttendanceSettings → AbsenceAlert config.
    Safe to re-run — de-duplicated per employee per calendar day.
    """
    from apps.tenants.models import MODULE_ATTENDANCE
    from apps.tenants.utils import run_for_all_tenants

    def _run_for_one_tenant():
        from apps.attendance.services_absence import detect_absence_alerts
        return detect_absence_alerts()

    try:
        result = run_for_all_tenants(
            _run_for_one_tenant, task_name='check_absence_alerts', required_module=MODULE_ATTENDANCE,
        )
        logger.info('check_absence_alerts: %s', result)
        return result
    except Exception as exc:
        logger.error('check_absence_alerts failed: %s', exc, exc_info=True)
        raise self.retry(exc=exc)


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def reprocess_attendance_task(self, schema_name, target_date_iso, branch, department, performed_by_id, employee_ids):
    """
    On-demand worker for HRAttendanceReprocessView — dispatched so the HTTP
    request can return immediately instead of blocking on however many
    employees are in scope. `schema_name` is the dispatching company's
    schema (see apps.tenants.utils.run_in_tenant).

    Accepts only primitive identifiers (an ISO date string, a branch/
    department string, a performed_by user id, and a list of employee id
    strings or None) rather than model instances, and re-fetches everything
    it needs inside reprocess_date()/AttendanceProcessorService — it does
    NOT reimplement any attendance calculation itself.

    Per-employee failures are already caught and counted individually inside
    reprocess_date() (it never raises for a single employee's failure), so a
    retry here only ever covers a genuinely unexpected failure before that
    per-employee loop even starts (e.g. the initial employee query itself
    failing) — nothing will have been written yet at that point, so retrying
    is safe. Reprocessing is itself idempotent: AttendanceRecord is written
    via update_or_create() keyed on the (employee, date) unique constraint,
    so running this task twice for the same date never creates duplicates.
    """
    import datetime as _dt

    from apps.attendance.services_hr import reprocess_date
    from apps.tenants.utils import run_in_tenant

    def _do_reprocess():
        target_date = _dt.date.fromisoformat(target_date_iso)
        performed_by = None
        if performed_by_id:
            from apps.accounts.models import User
            performed_by = User.objects.filter(pk=performed_by_id).first()

        return reprocess_date(
            target_date=target_date,
            branch=branch,
            department=department,
            performed_by=performed_by,
            employee_ids=employee_ids,
        )

    try:
        result = run_in_tenant(schema_name, _do_reprocess)
        logger.info('reprocess_attendance_task completed: %s', result)
        return result
    except Exception as exc:
        logger.error('reprocess_attendance_task failed: %s', exc, exc_info=True)
        raise self.retry(exc=exc)


@shared_task
def reverse_geocode_punch_task(schema_name: str, punch_id: str) -> None:
    """
    Best-effort background enrichment: resolves AttendancePunch.location_label
    from that punch's own already-stored latitude/longitude via OpenStreetMap
    Nominatim (apps.attendance.services_geocoding.reverse_geocode) — EXCEPT
    for a UK Shift employee's punch made from inside their own branch
    geofence (is_inside_geofence is True, resolved display-only by
    services_geofencing._validate_uk_shift_bypass — it never rejects on
    this), which gets "Office – <Branch Name>" directly with no HTTP call at
    all, per the explicit "don't reverse-geocode office coordinates
    unnecessarily" requirement. A UK Shift punch made from anywhere else, and
    every punch from every non-UK employee (SGT/ICT, the global default —
    regardless of their own is_inside_geofence value), falls through to the
    unconditional reverse-geocode call exactly as before this distinction
    existed — the office shortcut is deliberately scoped to UK Shift only.

    Dispatched fire-and-forget from PunchService.record_punch() via
    transaction.on_commit() — only AFTER the punch is already committed, so
    this never sits on the employee's clock-in/out request. `schema_name` is
    the dispatching company's schema (see apps.tenants.utils.run_in_tenant),
    captured at dispatch time the same way process_attendance_import/
    reprocess_attendance_task above do it.

    No retry: this is a nice-to-have enrichment, not a correctness-critical
    operation — a failure (timeout, rate limit, no result) just leaves
    location_label empty, which the HR UI already handles gracefully
    ("Location name unavailable"), and retrying against a free, rate-limited
    public API would risk making the situation worse, not better.
    """
    from apps.attendance.models import AttendancePunch
    from apps.attendance.services_geocoding import reverse_geocode
    from apps.attendance.services_geofencing import UK_SHIFT_POLICY_CODE
    from apps.tenants.utils import run_in_tenant

    def _do_geocode():
        from core.cache_service import ShiftCacheService

        punch = AttendancePunch.objects.select_related('branch', 'employee').filter(pk=punch_id).first()
        if punch is None or punch.latitude is None or punch.longitude is None:
            return

        if punch.is_inside_geofence is True and punch.branch is not None:
            shift = ShiftCacheService.get_effective(punch.employee, punch.punch_date)
            if shift.policy_code == UK_SHIFT_POLICY_CODE:
                punch.location_label = f'Office – {punch.branch.branch_name}'
                punch.save(update_fields=['location_label'])
                return

        label = reverse_geocode(float(punch.latitude), float(punch.longitude))
        if label:
            punch.location_label = label
            punch.save(update_fields=['location_label'])

    try:
        run_in_tenant(schema_name, _do_geocode)
    except Exception as exc:
        logger.warning('reverse_geocode_punch_task failed (non-blocking, punch_id=%s): %s', punch_id, exc)
