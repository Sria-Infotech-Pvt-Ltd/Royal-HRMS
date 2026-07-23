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

    Runs every 5 minutes (configured in CELERY_BEAT_SCHEDULE).
    Safe to run multiple times — idempotent via STATUS_INCOMPLETE exclusion
    and MissingPunchNotification dedup.
    """
    try:
        from apps.attendance.services_unpunch import detect_and_mark_unpunches
        today  = timezone.localdate()   # Uses Django TIME_ZONE = 'Asia/Kolkata'
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
    processing threshold.  Reads the CSV content passed as a task argument,
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
    try:
        from apps.attendance.services_absence import detect_absence_alerts
        result = detect_absence_alerts()
        logger.info('check_absence_alerts: %s', result)
        return result
    except Exception as exc:
        logger.error('check_absence_alerts failed: %s', exc, exc_info=True)
        raise self.retry(exc=exc)
