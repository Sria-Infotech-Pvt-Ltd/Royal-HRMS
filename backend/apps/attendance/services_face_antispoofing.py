"""
Anti-spoofing / replay defenses for face verification at punch time.

Split out of services_face_matching.py to stay under this project's
300-line-per-file convention. FaceVerificationService.verify_for_punch is the
single call site that orchestrates these gates alongside the actual distance
match — see FaceVerificationAttempt's own docstring (attendance/models.py)
for the full reasoning behind both defenses below.

Deliberately scoped to punch-time verification only, not registration
submissions: registration is a single HR-reviewed event, lower frequency and
lower risk than an unattended repeated clock-in attempt.
"""
from __future__ import annotations

import hashlib
from datetime import timedelta
from typing import Optional

from django.utils import timezone

from apps.attendance.models import FaceVerificationAttempt

# How many failed attempts an employee can rack up before further tries are
# blocked outright, and over what rolling window. Independent of any
# conversational retry counter (e.g. voice's own "3 tries then suggest manual
# clock-in" — see apps.voice_commands.conversation_clock_in_face) — that
# counter resets every time a fresh conversation starts, so on its own it
# could never stop someone from just starting over repeatedly.
MAX_FAILED_ATTEMPTS = 5
ATTEMPT_CAP_WINDOW_SECONDS = 900   # 15 minutes

# How long a byte-identical embedding stays "recently seen" for
# duplicate-submission (replay) detection across capture sessions.
REPLAY_WINDOW_SECONDS = 300   # 5 minutes


def fingerprint_embedding(embedding: list) -> str:
    """SHA-256 hex digest of the embedding — used for cap/replay lookups so
    the raw vector is never persisted a second time outside
    FaceRegistrationRequest/AttendancePunch."""
    payload = ','.join(f'{value:.10f}' for value in embedding).encode('utf-8')
    return hashlib.sha256(payload).hexdigest()


class FaceAntiSpoofingGuard:
    """Attempt-cap + replay-detection checks, and the audit trail behind both."""

    @staticmethod
    def check_attempt_cap(employee) -> bool:
        """True when this employee has already hit MAX_FAILED_ATTEMPTS failed
        attempts (any source, web or voice) within the rolling window."""
        window_start = timezone.now() - timedelta(seconds=ATTEMPT_CAP_WINDOW_SECONDS)
        failed_count = (
            FaceVerificationAttempt.objects
            .filter(employee=employee, is_match=False, created_at__gte=window_start)
            .count()
        )
        return failed_count >= MAX_FAILED_ATTEMPTS

    @staticmethod
    def check_replay(employee, fingerprint: str, capture_session_id: str) -> bool:
        """True when this exact embedding was already submitted by this
        employee within the replay window from a DIFFERENT capture session."""
        window_start = timezone.now() - timedelta(seconds=REPLAY_WINDOW_SECONDS)
        query = FaceVerificationAttempt.objects.filter(
            employee=employee, embedding_fingerprint=fingerprint, created_at__gte=window_start,
        )
        if capture_session_id:
            query = query.exclude(capture_session_id=capture_session_id)
        return query.exists()

    @staticmethod
    def record_attempt(
        employee, source: str, capture_session_id: str, fingerprint: str,
        liveness_passed: Optional[bool], liveness_score: Optional[float],
        *, is_match: bool, distance: Optional[float], rejection_reason: str,
    ) -> None:
        FaceVerificationAttempt.objects.create(
            employee=employee,
            source=source,
            capture_session_id=capture_session_id or '',
            embedding_fingerprint=fingerprint,
            liveness_passed=bool(liveness_passed),
            liveness_score=liveness_score,
            is_match=is_match,
            distance=distance,
            rejection_reason=rejection_reason,
        )
