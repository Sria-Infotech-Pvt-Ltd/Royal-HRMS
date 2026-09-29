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
from django.db import transaction

from apps.attendance.models import AttendancePunch, FaceRegistrationRequest, FaceVerificationAttempt
from apps.attendance.services_face_antispoofing import FaceAntiSpoofingGuard, fingerprint_embedding

logger = logging.getLogger(__name__)

# face-api.js's own recommended match threshold for its faceRecognitionNet
# descriptors — euclidean distance <= this value is considered the same face.
# Tied to FACE_RECOGNITION_MODEL_VERSION (models.py); revisit if that model changes.
# NOT safely lowerable on its own: a 2026-08-13 false-accept incident matched a
# different person at distance 0.578, then 0.556 after frontend multi-frame
# averaging (frontend/components/FaceVerificationModal.tsx) reduced per-capture
# noise — but this employee's own genuine distances already range up to 0.554,
# a 0.002 gap from that impostor attempt. No threshold separates the two;
# frame-averaging alone can't either, since it cancels per-capture noise, not a
# genuine lack of separation between two specific people's embeddings. See
# FACE_MATCH_LOW_CONFIDENCE_MARGIN below for the actual defense against that gap.
FACE_MATCH_MAX_DISTANCE = 0.6

# Width of the hard-reject band right below the threshold — see the
# low-confidence-match log in _match_and_record. An earlier version of this
# check let a match in this band through if a SECOND independent capture also
# landed here ("corroboration"), on the theory that two low-confidence
# coincidences in a row from an unrelated face would be rare. A real retest
# disproved that: the same impostor reproduced a borderline distance on 4 of 5
# captures (0.556-0.588) — a consistent near-threshold result for that specific
# face against this reference, not independent noise, so requiring a second
# draw barely lowered the odds. This band is now a hard reject with no
# escalation path — retrying can never turn it into an accept.
FACE_MATCH_LOW_CONFIDENCE_MARGIN = 0.05

_EMBEDDING_REQUIRED_MESSAGE = (
    'Face verification is required for clock-in. Please allow camera access and try again.'
)
# Deliberately not lighting-flavored (the pre-FR-2 text said "try again in
# good lighting" for a genuine embedding mismatch — misleading, per the FR-1
# audit). Still allows a retry, unlike _LOW_CONFIDENCE_MESSAGE's hard
# reject below — an outright mismatch can be a real different-person
# attempt a registered employee's own next capture would simply pass.
# Framed as "we couldn't match", not "your face didn't match", since the
# cause could equally be a marginal registration reference, not the
# employee's fault.
_EMBEDDING_MISMATCH_MESSAGE = (
    "We couldn't match your face to your registered Face ID. You can try again, or contact "
    "your HR representative if this keeps happening."
)
# Distinct from _EMBEDDING_MISMATCH_MESSAGE on purpose — the low-confidence
# band (see FACE_MATCH_LOW_CONFIDENCE_MARGIN above) is a hard reject with no
# escalation path for this specific employee/reference pair, so telling them
# to retry in better lighting is actively false: the frontend's own capture
# flow already enforces lighting/quality before an embedding is ever
# submitted, and a fresh capture right now cannot change the outcome.
_LOW_CONFIDENCE_MESSAGE = (
    'Face verification failed and trying again right now won’t change the result. '
    'Please contact your HR representative to review or refresh your Face ID registration.'
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
_LIVENESS_FAILED_MESSAGE = (
    'Liveness check did not pass. Please try again in good lighting, facing the camera directly.'
)


@transaction.atomic
def activate_registration(face_request: FaceRegistrationRequest) -> None:
    """
    Marks face_request as the sole active reference for its employee —
    call this the moment a registration becomes approved (self-service
    review approval, or HR's auto-approved direct register in
    face_registration_hr.py). select_for_update stops two concurrent
    approvals for the same employee both landing as active; the
    UniqueConstraint on FaceRegistrationRequest.is_active is the actual
    backstop if that ever raced anyway.
    """
    (
        FaceRegistrationRequest.objects
        .select_for_update()
        .filter(employee_id=face_request.employee_id, is_active=True)
        .exclude(pk=face_request.pk)
        .update(is_active=False)
    )
    face_request.is_active = True
    face_request.save(update_fields=['is_active', 'updated_at'])


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


class FaceVerificationBlockedError(PermissionError):
    """Raised instead of a plain PermissionError when the rejection is a
    terminal block (attempt cap, replay, low-confidence — see
    FaceVerificationOutcome.blocked) rather than an ordinary retryable
    mismatch, so callers that want to surface a countdown/disable-retry UI
    (AttendancePunchView, voice's _execute_punch) can tell the two apart
    without inspecting the message string."""

    def __init__(self, message: str, retry_after_seconds: Optional[int] = None):
        super().__init__(message)
        self.retry_after_seconds = retry_after_seconds


@dataclass
class FaceVerificationOutcome:
    required:           bool
    embedding_provided: bool
    is_match:           bool
    distance:           Optional[float]
    rejection_message:  Optional[str]
    # True for a terminal rejection a retry can never fix this cycle (attempt
    # cap, replay, or a low-confidence match) — as opposed to a normal
    # mismatch, which a fresh capture can still resolve. Voice's conversational
    # retry loop (see apps.voice_commands.conversation_clock_in_face) uses
    # this to decide whether "try again" is even worth offering.
    blocked:            bool = False
    # Only ever set alongside blocked=True from the attempt-cap gate — how
    # many more seconds the cap stays tripped, so a caller can show a
    # countdown / disable retry instead of just repeating the same rejection
    # message on every click (see FaceAntiSpoofingGuard.seconds_until_unblocked).
    retry_after_seconds: Optional[int] = None


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
        """Liveness, then attempt cap, then replay detection
        (services_face_antispoofing.py) — all record their own audit row on
        rejection. Returns the terminal outcome, or None to continue on to
        the actual distance match."""
        if liveness_passed is False:
            # Only gates an explicit False — None means the caller (e.g. an
            # older client build) never reported a liveness result at all,
            # which is not the same claim as "the check ran and failed."
            FaceAntiSpoofingGuard.record_attempt(
                employee, source, capture_session_id, fingerprint, liveness_passed, liveness_score,
                is_match=False, distance=None, rejection_reason=FaceVerificationAttempt.REJECTION_LIVENESS_FAILED,
            )
            return FaceVerificationOutcome(
                required=True, embedding_provided=True, is_match=False,
                distance=None, rejection_message=_LIVENESS_FAILED_MESSAGE,
            )
        if FaceAntiSpoofingGuard.check_attempt_cap(employee):
            FaceAntiSpoofingGuard.record_attempt(
                employee, source, capture_session_id, fingerprint, liveness_passed, liveness_score,
                is_match=False, distance=None, rejection_reason=FaceVerificationAttempt.REJECTION_CAP,
            )
            return FaceVerificationOutcome(
                required=True, embedding_provided=True, is_match=False,
                distance=None, rejection_message=_ATTEMPT_CAP_MESSAGE, blocked=True,
                retry_after_seconds=FaceAntiSpoofingGuard.seconds_until_unblocked(employee),
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
        is_low_confidence = is_match and (FACE_MATCH_MAX_DISTANCE - distance) <= FACE_MATCH_LOW_CONFIDENCE_MARGIN

        if is_low_confidence:
            # A 2026-08-13 false-accept incident originally handled this by
            # accepting once a SECOND independent capture also landed in this
            # band ("corroboration"), on the assumption that two low-
            # confidence coincidences in a row from an unrelated face would be
            # rare. That assumption failed in practice: a real retest against
            # the same impostor reproduced a borderline distance on 4 out of 5
            # captures (0.556-0.588, plus one genuine reject at 0.621) — not
            # independent random noise around a clear non-match, but a
            # consistent near-threshold result for that specific face against
            # this reference. Two draws from a biased coin aren't two draws
            # from a fair one, so requiring a second draw didn't actually
            # lower the odds much. There is no corroboration path anymore —
            # this band is a hard reject, always, same as an outright
            # mismatch; retrying can never turn it into an accept.
            logger.warning(
                'Low-confidence face match rejected: employee=%s source=%s distance=%.4f (threshold=%.2f)',
                employee.pk, source, distance, FACE_MATCH_MAX_DISTANCE,
            )
            FaceAntiSpoofingGuard.record_attempt(
                employee, source, capture_session_id, fingerprint, liveness_passed, liveness_score,
                is_match=False, distance=distance,
                rejection_reason=FaceVerificationAttempt.REJECTION_LOW_CONFIDENCE_PENDING,
            )
            return FaceVerificationOutcome(
                required=True, embedding_provided=True, is_match=False,
                distance=distance, rejection_message=_LOW_CONFIDENCE_MESSAGE, blocked=True,
            )

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
        # is_active + the UniqueConstraint in FaceRegistrationRequest.Meta
        # guarantee at most one row ever matches this filter — no more
        # picking "whichever approved row happens to have the latest
        # approved_at", which had no cap on how many rows could be approved
        # at once. See activate_registration, called at the two places a
        # registration becomes approved.
        return (
            FaceRegistrationRequest.objects
            .filter(employee=employee, status=FaceRegistrationRequest.STATUS_APPROVED, is_active=True)
            .first()
        )
