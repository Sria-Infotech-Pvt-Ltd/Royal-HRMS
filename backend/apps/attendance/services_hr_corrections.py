"""
HR Attendance Correction Management services.

Handles listing pending corrections and approving/rejecting them.
Approval creates the missing AttendancePunch(es) and reprocesses the day,
which changes the AttendanceRecord from STATUS_INCOMPLETE → present/late
and removes the employee from the Un-Punches list automatically.
"""
from __future__ import annotations

import datetime
import logging
from zoneinfo import ZoneInfo

from django.contrib.auth import get_user_model
from django.db import transaction
from django.utils import timezone

from apps.attendance.models import AttendanceCorrection, AttendancePunch

logger = logging.getLogger(__name__)
User = get_user_model()

_IST = ZoneInfo('Asia/Kolkata')


# ── Public API ─────────────────────────────────────────────────────────────────

def list_corrections(
    branch: str = '',
    department: str = '',
    status_filter: str = '',
) -> list[dict]:
    """
    Return correction requests for HR review, newest first.

    status_filter: 'pending' | 'approved' | 'rejected' | '' (all)
    """
    employee_qs = User.objects.filter(is_active=True)
    if branch:
        employee_qs = employee_qs.filter(branch=branch)
    if department:
        employee_qs = employee_qs.filter(department=department)

    qs = (
        AttendanceCorrection.objects
        .filter(employee__in=employee_qs)
        .select_related('employee', 'reviewed_by')
        .order_by('-created_at')
    )
    if status_filter:
        qs = qs.filter(status=status_filter)

    return [_build_row(c) for c in qs]


def approve_correction(correction_id: str, reviewed_by) -> dict:
    """
    Approve a pending correction.

    1. Creates the missing AttendancePunch record(s) with source='manual'.
    2. Calls AttendanceProcessorService.process_day() to recompute the record.
    3. The reprocessed record gets last_punch_out set → status changes from
       incomplete → present or late → employee drops off the Un-Punches list.
    """
    from apps.attendance.services_attendance import AttendanceProcessorService

    with transaction.atomic():
        correction = _get_pending(correction_id)

        if correction.punch_type in (AttendanceCorrection.PUNCH_IN, AttendanceCorrection.PUNCH_BOTH):
            _create_punch(
                correction.employee, correction.date,
                correction.requested_in_time, AttendancePunch.PUNCH_IN,
            )

        if correction.punch_type in (AttendanceCorrection.PUNCH_OUT, AttendanceCorrection.PUNCH_BOTH):
            _create_punch(
                correction.employee, correction.date,
                correction.requested_out_time, AttendancePunch.PUNCH_OUT,
            )

        AttendanceProcessorService.process_day(correction.employee, correction.date)

        correction.status      = AttendanceCorrection.STATUS_APPROVED
        correction.reviewed_by = reviewed_by
        correction.reviewed_at = timezone.now()
        correction.save(update_fields=['status', 'reviewed_by', 'reviewed_at', 'updated_at'])

        logger.info(
            'Correction %s approved by %s (employee=%s date=%s)',
            correction.pk, reviewed_by.pk, correction.employee_id, correction.date,
        )

    return _build_row(correction)


def reject_correction(correction_id: str, reviewed_by) -> dict:
    """Mark a pending correction as rejected. Does not alter any punch records."""
    with transaction.atomic():
        correction = _get_pending(correction_id)
        correction.status      = AttendanceCorrection.STATUS_REJECTED
        correction.reviewed_by = reviewed_by
        correction.reviewed_at = timezone.now()
        correction.save(update_fields=['status', 'reviewed_by', 'reviewed_at', 'updated_at'])

        logger.info(
            'Correction %s rejected by %s (employee=%s date=%s)',
            correction.pk, reviewed_by.pk, correction.employee_id, correction.date,
        )

    return _build_row(correction)


# ── Private helpers ────────────────────────────────────────────────────────────

def _get_pending(correction_id: str) -> AttendanceCorrection:
    try:
        return AttendanceCorrection.objects.select_related('employee').get(
            id=correction_id,
            status=AttendanceCorrection.STATUS_PENDING,
        )
    except AttendanceCorrection.DoesNotExist:
        raise ValueError('Correction not found or already reviewed.')


def _create_punch(
    employee,
    date: datetime.date,
    punch_time: datetime.time,
    punch_type: str,
) -> None:
    """Create a regularization punch. Skips silently if an identical one already exists."""
    punched_at = datetime.datetime.combine(date, punch_time).replace(tzinfo=_IST)
    AttendancePunch.objects.get_or_create(
        employee=employee,
        punched_at=punched_at,
        punch_type=punch_type,
        defaults={
            'source':          AttendancePunch.SOURCE_MANUAL,
            'attendance_mode': AttendancePunch.MODE_OFFICE,
        },
    )


def _build_row(c: AttendanceCorrection) -> dict:
    user = c.employee
    return {
        'id':                 str(c.pk),
        'employee_id':        user.employee_id or '',
        'name':               user.full_name or '',
        'department':         user.department or '',
        'branch':             user.branch or '',
        'date':               c.date.strftime('%Y-%m-%d'),
        'punch_type':         c.punch_type,
        'requested_in_time':  c.requested_in_time.strftime('%H:%M') if c.requested_in_time else None,
        'requested_out_time': c.requested_out_time.strftime('%H:%M') if c.requested_out_time else None,
        'reason':             c.reason,
        'notes':              c.notes or '',
        'status':             c.status,
        'reviewed_by':        c.reviewed_by.full_name if c.reviewed_by else None,
        'reviewed_at':        c.reviewed_at.strftime('%Y-%m-%d %H:%M') if c.reviewed_at else None,
        'created_at':         c.created_at.strftime('%Y-%m-%d %H:%M'),
    }
