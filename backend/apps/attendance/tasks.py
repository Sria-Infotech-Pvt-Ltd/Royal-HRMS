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

    Runs every 5 minutes (configured in CELERY_BEAT_SCHEDULE).  Safe to run
    multiple times — idempotent via STATUS_INCOMPLETE exclusion and
    MissingPunchNotification dedup.
    """
    from apps.attendance.services_unpunch import detect_and_mark_unpunches

    try:
        today = timezone.localdate()   # Uses Django TIME_ZONE = 'Asia/Kolkata'
        result = detect_and_mark_unpunches(target_date=today)
        logger.info('check_missing_clockouts: %s', result)
        return result
    except Exception as exc:
        logger.error('check_missing_clockouts failed: %s', exc, exc_info=True)
        raise self.retry(exc=exc)


@shared_task(bind=True, max_retries=0, default_retry_delay=0)
def process_attendance_import(self, import_log_id: str, imported_by_pk: str, csv_content: str):
    """
    Async worker for large CSV imports (> SYNC_THRESHOLD rows).

    Dispatched by import_attendance_csv when the file exceeds the synchronous
    processing threshold. Reads the CSV content passed as a task argument,
    runs the same bulk import engine used by the sync path, and writes the
    final status back to AttendanceImportLog.
    """
    from apps.attendance.models import AttendanceImportLog
    from apps.attendance.services_hr_ops import _run_import_bulk
    from django.contrib.auth import get_user_model
    import csv as _csv
    import io as _io

    _User = get_user_model()

    try:
        import_log   = AttendanceImportLog.objects.get(id=import_log_id)
        imported_by  = _User.objects.get(pk=imported_by_pk)
        rows         = list(_csv.DictReader(_io.StringIO(csv_content)))
        _run_import_bulk(import_log, rows, imported_by)
        logger.info('process_attendance_import finished | import_id=%s', import_log_id)
    except AttendanceImportLog.DoesNotExist:
        logger.error('process_attendance_import: import_log %s not found', import_log_id)
    except _User.DoesNotExist:
        logger.error('process_attendance_import: user %s not found', imported_by_pk)
    except Exception as exc:
        logger.error('process_attendance_import failed: %s', exc, exc_info=True)
        try:
            log = AttendanceImportLog.objects.get(id=import_log_id)
            if log.status == AttendanceImportLog.STATUS_PROCESSING:
                log.status = AttendanceImportLog.STATUS_FAILED
                log.save(update_fields=['status', 'updated_at'])
        except Exception:
            pass
        raise


@shared_task(bind=True, max_retries=3, default_retry_delay=300)
def check_absence_alerts(self):
    """
    Daily task: fire absence notifications for employees absent N+ consecutive
    working days without approved leave.

    Threshold and recipients come from AttendanceSettings → AbsenceAlert config.
    Safe to re-run — de-duplicated per employee per calendar day.
    """
    from apps.attendance.services_absence import detect_absence_alerts

    try:
        result = detect_absence_alerts()
        logger.info('check_absence_alerts: %s', result)
        return result
    except Exception as exc:
        logger.error('check_absence_alerts failed: %s', exc, exc_info=True)
        raise self.retry(exc=exc)


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def reprocess_attendance_task(self, target_date_iso, branch, department, performed_by_id, employee_ids):
    """
    On-demand worker for HRAttendanceReprocessView — dispatched so the HTTP
    request can return immediately instead of blocking on however many
    employees are in scope.

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

    try:
        target_date = _dt.date.fromisoformat(target_date_iso)
        performed_by = None
        if performed_by_id:
            from apps.accounts.models import User
            performed_by = User.objects.filter(pk=performed_by_id).first()

        result = reprocess_date(
            target_date=target_date,
            branch=branch,
            department=department,
            performed_by=performed_by,
            employee_ids=employee_ids,
        )
        logger.info('reprocess_attendance_task completed: %s', result)
        return result
    except Exception as exc:
        logger.error('reprocess_attendance_task failed: %s', exc, exc_info=True)
        raise self.retry(exc=exc)
