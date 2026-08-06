"""
Voice-initiated clock-in/out with a facial proof step.

Split out of conversation.py (same reasoning conversation_payroll.py and
conversation_leave_approval.py already give for their own splits — keeps
conversation.py under the 300-line convention) to own the turn-taking for
clock_in/clock_out ONLY when AttendanceFaceVerificationRules.is_mandatory is
on. When it's off, start_voice_clock_punch is a same-turn pass-through to the
existing executor_attendance functions — zero behaviour change for any
organisation that hasn't turned this feature on.

Turn shape when face verification IS mandatory:
  1. "clock me in" -> geofence check (reuses GeofencingService.validate
     directly — same rejection message/shape the existing GPS-missing retry
     in useVoiceCommand.ts already handles, so nothing there needs to change)
     -> "Taking facial proof — please look at the camera." (awaiting_input)
  2. Frontend opens FaceVerificationModal, captures a descriptor, resubmits
     the same original transcript with it attached (mirrors how a
     geofence-triggered GPS retry resubmits the same transcript with
     coordinates attached) -> matched via FaceVerificationService.
     verify_for_punch (the SAME check every punch goes through, so its
     attempt-cap/replay defenses apply identically here) -> either the punch
     completes, or after up to MAX_VOICE_FACE_ATTEMPTS mismatches the flow
     gives up and points the employee at the manual Clock In button.
"""
from __future__ import annotations

import logging
from typing import Optional

from apps.attendance.models import FaceRegistrationRequest
from apps.attendance.services_face_matching import FaceVerificationService, is_face_verification_mandatory
from apps.attendance.services_geofencing import GeofencingService

from apps.voice_commands.clarification import clear_pending, set_pending
from apps.voice_commands.executor import INTENT_CLOCK_IN, INTENT_CLOCK_OUT
from apps.voice_commands.executor_attendance import execute_clock_in, execute_clock_out
from apps.voice_commands.matcher import get_conversational

logger = logging.getLogger(__name__)

AWAITING_FACE_PROOF_STAGE = 'awaiting_face_proof'
MAX_VOICE_FACE_ATTEMPTS = 3

# Item 5 — directs the employee to HR/their manager rather than leaving them
# stuck: only FaceRegistrationHRRegisterView (facial_recognition.approve) can
# create an approved registration, so self-service voice can't resolve this.
_NO_REGISTRATION_MESSAGE = (
    "You don't have a registered face ID yet, so I can't verify you by voice. Please contact "
    "your HR representative or manager to get your face ID registered, or use the manual "
    "Clock In button once it's set up."
)
_TAKING_FACIAL_PROOF_MESSAGE = "Taking facial proof — please look at the camera."
_RETRY_MESSAGE = "That didn't match. Please try again, facing the camera directly."
_GIVE_UP_MESSAGE = (
    "We couldn't verify your face after {attempts} attempts. Please use the manual Clock In "
    "button on your dashboard, or contact HR if this keeps happening."
)

def _executor_for(intent: str):
    """
    Looked up by name INSIDE this function (not pre-bound into a module-level
    dict at import time) deliberately — a dict built once at import time
    would freeze references to the ORIGINAL execute_clock_in/execute_clock_out
    objects, so patch('apps.voice_commands.conversation_clock_in_face.
    execute_clock_in') in a test would silently rebind the module's own name
    without ever affecting a copy already frozen into that dict. Referencing
    the bare names here instead means each call re-reads whatever they
    currently resolve to in this module's namespace, same as every other
    execute_*() call site in this test package relies on being mockable.
    """
    return execute_clock_in if intent == INTENT_CLOCK_IN else execute_clock_out


def start_voice_clock_punch(
    request, intent: str, attendance_mode: Optional[str], confidence: Optional[float],
    latitude: Optional[float], longitude: Optional[float],
) -> dict:
    """First turn for clock_in/clock_out — see module docstring for the fast
    path (feature off) vs. the facial-proof path (feature on)."""
    if not is_face_verification_mandatory():
        outcome = _executor_for(intent)(request, attendance_mode, latitude=latitude, longitude=longitude)
        return _payload(intent, confidence, outcome.data, outcome.message, success=outcome.success)

    has_registration = FaceRegistrationRequest.objects.filter(
        employee=request.user, status=FaceRegistrationRequest.STATUS_APPROVED,
    ).exists()
    if not has_registration:
        logger.info('Voice clock punch blocked — no approved face registration for user=%s', request.user.pk)
        return _payload(intent, confidence, None, _NO_REGISTRATION_MESSAGE, success=False)

    geo = GeofencingService.validate(
        employee=request.user, attendance_mode=attendance_mode or 'office',
        employee_lat=latitude, employee_lon=longitude,
    )
    if not geo.is_allowed:
        return _payload(intent, confidence, None, geo.rejection_message, success=False)

    slots = {
        'stage': AWAITING_FACE_PROOF_STAGE, 'attendance_mode': attendance_mode,
        'latitude': latitude, 'longitude': longitude, 'attempt': 0,
    }
    set_pending(request.user.id, intent, slots)
    logger.info('Voice clock punch awaiting facial proof: user=%s intent=%s', request.user.pk, intent)
    return _payload(
        intent, confidence, {'awaiting_face_proof': True}, _TAKING_FACIAL_PROOF_MESSAGE,
        awaiting_input=True, conversational=True,
    )


def continue_voice_clock_punch(
    request, pending: dict, face_embedding: Optional[list], liveness_passed: Optional[bool],
    liveness_score: Optional[float], capture_session_id: str,
) -> dict:
    """Second+ turn — a captured descriptor has come back from
    FaceVerificationModal. See module docstring for the retry-then-give-up shape."""
    intent = pending['intent']
    slots  = dict(pending['slots'])
    attempt = slots.get('attempt', 0) + 1

    if not face_embedding:
        # Frontend never resubmits without a descriptor in the normal flow —
        # a defensive re-ask rather than a hard failure or wasted attempt.
        set_pending(request.user.id, intent, slots)
        return _payload(intent, None, None, _TAKING_FACIAL_PROOF_MESSAGE, awaiting_input=True, conversational=True)

    outcome = FaceVerificationService.verify_for_punch(
        request.user, 'voice', face_embedding,
        capture_session_id=capture_session_id, liveness_passed=liveness_passed,
        liveness_score=liveness_score, is_secure=request.is_secure(),
    )

    # Not required any more (org toggle flipped off mid-conversation) counts
    # as verified — nothing left to check. A required check that couldn't
    # even run (e.g. registration revoked mid-conversation) is a precondition
    # failure, not a retryable mismatch — no amount of recapturing fixes it.
    if not outcome.required:
        return _finish_punch(request, intent, slots, face_embedding, liveness_passed, liveness_score, capture_session_id)
    if not outcome.embedding_provided:
        clear_pending(request.user.id)
        return _payload(intent, None, None, outcome.rejection_message, success=False)
    if outcome.is_match:
        return _finish_punch(request, intent, slots, face_embedding, liveness_passed, liveness_score, capture_session_id)

    if outcome.blocked or attempt >= MAX_VOICE_FACE_ATTEMPTS:
        clear_pending(request.user.id)
        message = outcome.rejection_message if outcome.blocked else _GIVE_UP_MESSAGE.format(attempts=attempt)
        logger.info(
            'Voice clock punch face verification exhausted: user=%s intent=%s attempt=%s blocked=%s',
            request.user.pk, intent, attempt, outcome.blocked,
        )
        return _payload(intent, None, None, message, success=False)

    slots['attempt'] = attempt
    set_pending(request.user.id, intent, slots)
    return _payload(intent, None, None, _RETRY_MESSAGE, awaiting_input=True, conversational=True)


def _finish_punch(
    request, intent: str, slots: dict, face_embedding: list,
    liveness_passed: Optional[bool], liveness_score: Optional[float], capture_session_id: str,
) -> dict:
    """Verified — write the actual punch through the normal executor (which
    calls PunchService.record_punch, the single authoritative writer; this
    module never writes a punch itself)."""
    clear_pending(request.user.id)
    outcome = _executor_for(intent)(
        request, slots.get('attendance_mode'),
        latitude=slots.get('latitude'), longitude=slots.get('longitude'),
        face_embedding=face_embedding, liveness_passed=liveness_passed,
        liveness_score=liveness_score, capture_session_id=capture_session_id,
    )
    return _payload(intent, None, outcome.data, outcome.message, success=outcome.success)


def _payload(
    intent: str, confidence: Optional[float], result, message: str,
    awaiting_input: bool = False, success: bool = True,
    conversational: Optional[bool] = None,
) -> dict:
    """Small, deliberate duplicate of conversation.py's own private _payload —
    same reasoning conversation_clarification.py's own copy gives (avoids a
    circular import back into conversation.py). conversational overrides the
    registry lookup: clock_in/clock_out are registered conversational: false
    (a single-turn command in the common case), true only for the mid-dialogue
    turns this module itself produces."""
    return {
        'intent': intent,
        'confidence': confidence,
        'result': result,
        'message': message,
        'speech_message': None,
        'conversational': get_conversational(intent) if conversational is None else conversational,
        'awaiting_input': awaiting_input,
        'success': success,
    }
