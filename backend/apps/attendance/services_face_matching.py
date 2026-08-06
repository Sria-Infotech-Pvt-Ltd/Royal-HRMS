"""
Face verification for the punch flow.

Gated by the org-wide AttendanceFaceVerificationRules.is_mandatory toggle
(Attendance Settings -> Face ID Verification), which is the single source of
truth for the whole feature:

  - OFF — face verification is switched off organisation-wide. No punch is
    ever required to carry a face descriptor, even for an employee who
    registered while it was previously ON.
  - ON  — every employee must have an *approved* FaceRegistrationRequest.
    A punch without one is rejected outright (register first); one with an
    approved registration must submit a live face descriptor that matches it
    before the punch is accepted.

Only 'web' and 'voice' punches are gated (see PunchService.record_punch) —
both originate from a browser tab with camera access (see AttendancePunch's
own docstring for 'voice'). Mobile, biometric, manual and system-sourced
punches never carry a camera and are never required to verify.

Matching stays server-side deliberately (Euclidean distance only — see
_euclidean_distance below) rather than shipping the stored embedding to the
browser for a client-side diff: FaceRegistrationReadSerializer already never
re-exposes a stored embedding over the wire once submitted (an approver
decides from liveness_passed/liveness_score alone), and reversing that for
punch-time matching would hand a malicious client both vectors needed to
fabricate a match offline. The actual heavy compute — face detection and
descriptor extraction via face-api.js's neural nets — has always run
client-side (see frontend/lib/faceApi/); the distance check that remains here
is a handful of subtractions and a sqrt over two float arrays, not a GPU
workload, so keeping it server-side costs nothing in the "no server
GPU/compute" sense this feature was scoped against.

Two independent anti-spoofing defenses (attempt cap + replay detection —
see services_face_antispoofing.py) sit in front of the actual match; this
module orchestrates them but delegates their implementation there to stay
under the project's 300-line-per-file convention.
"""
from __future__ import annotations

import logging
import math
from dataclasses import dataclass
from typing import Optional

from django.conf import settings

from apps.attendance.models import AttendancePunch, FaceRegistrationRequest, FaceVerificationAttempt
from apps.attendance.services_face_antispoofing import FaceAntiSpoofingGuard, fingerprint_embedding

logger = logging.getLogger(__name__)

# face-api.js's own recommended match threshold for its faceRecognitionNet
# descriptors — euclidean distance <= this value is considered the same face.
# Tied to FACE_RECOGNITION_MODEL_VERSION (models.py); revisit if that model changes.
FACE_MATCH_MAX_DISTANCE = 0.6

_EMBEDDING_REQUIRED_MESSAGE = (
    'Face verification is required for clock-in. Please allow camera access and try again.'
)
_EMBEDDING_MISMATCH_MESSAGE = (
    'Face verification failed. Please try again in good lighting, facing the camera directly.'
)
_REGISTRATION_REQUIRED_MESSAGE = (
    'Face ID registration is mandatory and you don’t have one yet. Please contact your '
    'HR representative or manager — they can register your face ID for you from the Face ID '
    'Registrations page.'
)
_ATTEMPT_CAP_MESSAGE = (
    'Too many failed face verification attempts. Please wait a few minutes before trying '
    'again, or contact HR if this keeps happening.'
)
_REPLAY_MESSAGE = (
    'That face capture looks like it was already used. Please capture a fresh photo and try again.'
)
_INSECURE_TRANSPORT_MESSAGE = (
    'Face verification requires a secure connection. Please reload the page and try again.'
)


def is_face_verification_mandatory() -> bool:
    """
    Reads the org-wide toggle (cached — see core.cache_service.AttendanceSettingsCacheService).
    Defaults to False (feature off) if settings haven't been configured yet,
    matching every other AttendanceSettings child's "not configured = off" fallback.
    """
    from core.cache_service import AttendanceSettingsCacheService
    settings_obj = AttendanceSettingsCacheService.get()
    if settings_obj is None or not hasattr(settings_obj, 'face_verification'):
        return False
    return settings_obj.face_verification.is_mandatory


def _euclidean_distance(a: list, b: list) -> float:
    if len(a) != len(b):
        raise ValueError('Face descriptor length mismatch.')
    return math.sqrt(sum((x - y) ** 2 for x, y in zip(a, b)))


@dataclass
class FaceVerificationOutcome:
    required:           bool
    embedding_provided: bool
    is_match:           bool
    distance:           Optional[float]
    rejection_message:  Optional[str]
    # True for a terminal rejection a retry can never fix this cycle (attempt
    # cap or replay) — as opposed to a normal mismatch, which a fresh capture
    # can still resolve. Voice's conversational retry loop (see
    # apps.voice_commands.conversation_clock_in_face) uses this to decide
    # whether "try again" is even worth offering.
    blocked:            bool = False


class FaceVerificationService:
    """Single entry point PunchService.record_punch calls before writing a punch."""

    @classmethod
    def verify_for_punch(
        cls, employee, source: str, submitted_embedding: Optional[list], *,
        capture_session_id: str = '', liveness_passed: Optional[bool] = None,
        liveness_score: Optional[float] = None, is_secure: bool = True,
    ) -> FaceVerificationOutcome:
        if source not in (AttendancePunch.SOURCE_WEB, AttendancePunch.SOURCE_VOICE):
            return cls._not_required(submitted_embedding)
        if not is_face_verification_mandatory():
            # Org-wide toggle is off — the feature is switched off entirely,
            # even for someone who has an approved registration from before.
            return cls._not_required(submitted_embedding)

        registration = cls._resolve_active_registration(employee)
        precondition_failure = cls._check_preconditions(registration, submitted_embedding, is_secure, employee)
        if precondition_failure:
            return precondition_failure

        fingerprint = fingerprint_embedding(submitted_embedding)
        attempt_args = (employee, source, capture_session_id, fingerprint, liveness_passed, liveness_score)

        spoofing_rejection = cls._check_anti_spoofing_gates(*attempt_args)
        if spoofing_rejection:
            return spoofing_rejection

        return cls._match_and_record(registration, submitted_embedding, *attempt_args)

    @staticmethod
    def _check_preconditions(
        registration, submitted_embedding: Optional[list], is_secure: bool, employee,
    ) -> Optional[FaceVerificationOutcome]:
        """Cheap, no-DB-write checks that must pass before a submitted embedding
        is touched any further. Returns the terminal outcome to short-circuit
        with, or None to continue."""
        if not registration:
            return FaceVerificationOutcome(
                required=True, embedding_provided=False, is_match=False,
                distance=None, rejection_message=_REGISTRATION_REQUIRED_MESSAGE,
            )
        if not submitted_embedding:
            return FaceVerificationOutcome(
                required=True, embedding_provided=False, is_match=False,
                distance=None, rejection_message=_EMBEDDING_REQUIRED_MESSAGE,
            )
        # Every leg from here on carries a raw embedding — confirm TLS before
        # touching it further. Checks IS_LOCAL_OR_TEST_ENV, not DEBUG itself
        # — Django's test runner force-overrides settings.DEBUG to False for
        # every test run, which would otherwise make every punch test that
        # submits a face_embedding over the (plain-HTTP-by-default) test
        # client fail this check; see that setting's own comment in
        # config/settings.py. Same "local dev/test must keep working" intent
        # the project's `secure=not settings.DEBUG` cookie convention has.
        if not is_secure and not settings.IS_LOCAL_OR_TEST_ENV:
            logger.warning('Face verification rejected: insecure transport for employee %s', employee.pk)
            return FaceVerificationOutcome(
                required=True, embedding_provided=True, is_match=False,
                distance=None, rejection_message=_INSECURE_TRANSPORT_MESSAGE, blocked=True,
            )
        return None

    @classmethod
    def _check_anti_spoofing_gates(
        cls, employee, source: str, capture_session_id: str, fingerprint: str,
        liveness_passed: Optional[bool], liveness_score: Optional[float],
    ) -> Optional[FaceVerificationOutcome]:
        """Attempt cap, then replay detection (services_face_antispoofing.py) —
        both record their own audit row on rejection. Returns the terminal
        outcome, or None to continue on to the actual distance match."""
        if FaceAntiSpoofingGuard.check_attempt_cap(employee):
            FaceAntiSpoofingGuard.record_attempt(
                employee, source, capture_session_id, fingerprint, liveness_passed, liveness_score,
                is_match=False, distance=None, rejection_reason=FaceVerificationAttempt.REJECTION_CAP,
            )
            return FaceVerificationOutcome(
                required=True, embedding_provided=True, is_match=False,
                distance=None, rejection_message=_ATTEMPT_CAP_MESSAGE, blocked=True,
            )
        if FaceAntiSpoofingGuard.check_replay(employee, fingerprint, capture_session_id):
            FaceAntiSpoofingGuard.record_attempt(
                employee, source, capture_session_id, fingerprint, liveness_passed, liveness_score,
                is_match=False, distance=None, rejection_reason=FaceVerificationAttempt.REJECTION_REPLAY,
            )
            return FaceVerificationOutcome(
                required=True, embedding_provided=True, is_match=False,
                distance=None, rejection_message=_REPLAY_MESSAGE, blocked=True,
            )
        return None

    @classmethod
    def _match_and_record(
        cls, registration, submitted_embedding: list, employee, source: str,
        capture_session_id: str, fingerprint: str,
        liveness_passed: Optional[bool], liveness_score: Optional[float],
    ) -> FaceVerificationOutcome:
        """The actual distance check, always followed by an audit row —
        matched or not (see FaceVerificationAttempt's docstring for why every
        attempt is recorded, not just failures)."""
        try:
            distance = _euclidean_distance(registration.face_embedding, submitted_embedding)
        except ValueError:
            FaceAntiSpoofingGuard.record_attempt(
                employee, source, capture_session_id, fingerprint, liveness_passed, liveness_score,
                is_match=False, distance=None, rejection_reason=FaceVerificationAttempt.REJECTION_MISMATCH,
            )
            return FaceVerificationOutcome(
                required=True, embedding_provided=True, is_match=False,
                distance=None, rejection_message=_EMBEDDING_MISMATCH_MESSAGE,
            )

        is_match = distance <= FACE_MATCH_MAX_DISTANCE
        FaceAntiSpoofingGuard.record_attempt(
            employee, source, capture_session_id, fingerprint, liveness_passed, liveness_score,
            is_match=is_match, distance=distance,
            rejection_reason='' if is_match else FaceVerificationAttempt.REJECTION_MISMATCH,
        )
        return FaceVerificationOutcome(
            required=True, embedding_provided=True, is_match=is_match,
            distance=distance,
            rejection_message=None if is_match else _EMBEDDING_MISMATCH_MESSAGE,
        )

    @staticmethod
    def _not_required(submitted_embedding: Optional[list]) -> FaceVerificationOutcome:
        return FaceVerificationOutcome(
            required=False, embedding_provided=bool(submitted_embedding),
            is_match=False, distance=None, rejection_message=None,
        )

    @staticmethod
    def _resolve_active_registration(employee) -> Optional[FaceRegistrationRequest]:
        return (
            FaceRegistrationRequest.objects
            .filter(employee=employee, status=FaceRegistrationRequest.STATUS_APPROVED)
            .order_by('-approved_at')
            .first()
        )
