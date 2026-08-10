"""
Face biometric data lifecycle — specifically, what happens to an employee's
stored face data when they separate from the company.

Split out from services_face_matching.py/services_face_antispoofing.py (same
domain, different concern — data retention rather than matching) to stay
under the project's 300-line-per-file convention.

Data-minimization note (see the org-wide Face ID rollout's compliance
review): a face embedding is only retained for as long as the employee it
identifies remains employed. Once separated, the embedding itself serves no
further purpose and must not be kept indefinitely.
"""
from __future__ import annotations

import logging

from apps.attendance.models import FaceRegistrationRequest, FaceVerificationAttempt

logger = logging.getLogger(__name__)


def purge_face_data_for_employee(employee) -> dict:
    """
    Called when an employee is separated (deactivated/deleted) — see
    apps.accounts.views.EmployeeDetailView.patch/.delete, the only two
    places employment status actually changes today (there is no dedicated
    separation/offboarding model yet).

    FaceRegistrationRequest rows are hard-deleted outright: the embedding is
    the entire point of the row, and nothing about this model is designated
    as an audit record (unlike FaceVerificationAttempt below).

    FaceVerificationAttempt rows are NOT deleted — that model's own docstring
    explicitly designates it "Never deleted — kept for HR/security audit",
    the same reasoning as AttendanceAuditLog. Instead, only the biometric
    fingerprint and capture-session identifier are scrubbed; is_match,
    distance, rejection_reason, source and timestamps are left intact so the
    audit trail (who attempted what, when, pass/fail) survives the employee's
    departure without retaining anything that could be used to re-derive or
    replay their biometric data.

    Returns counts for the caller to log/audit — never raises for "nothing to
    delete" (a separated employee who never registered a face ID is the
    common case, not an error).
    """
    deleted_registrations, _ = FaceRegistrationRequest.objects.filter(employee=employee).delete()

    anonymized_attempts = FaceVerificationAttempt.objects.filter(employee=employee).update(
        embedding_fingerprint='',
        capture_session_id='',
    )

    if deleted_registrations or anonymized_attempts:
        logger.info(
            'Purged face data for separated employee %s: %d registration row(s) deleted, '
            '%d verification attempt(s) anonymized.',
            employee.email, deleted_registrations, anonymized_attempts,
        )

    return {
        'registrations_deleted':    deleted_registrations,
        'attempts_anonymized':      anonymized_attempts,
    }
