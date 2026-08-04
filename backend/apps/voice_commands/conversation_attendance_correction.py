from __future__ import annotations

from typing import Optional

from apps.voice_commands.clarification import clear_pending, set_pending
from apps.voice_commands.correction_slot_extractor import (
    extract_correction_slots,
    next_missing_slot,
    parse_slot_answer,
    question_for_slot,
)
from apps.voice_commands.executor import INTENT_REQUEST_ATTENDANCE_CORRECTION, execute_intent
from apps.voice_commands.matcher import get_conversational

# Split out of conversation.py (already close to this project's 300-line
# file convention) the same way conversation_payroll.py was — this module
# owns request_attendance_correction's multi-turn slot-filling, mirroring
# conversation.py's own _start_apply_leave/_continue_apply_leave shape:
# pull whatever slots are in the first utterance, ask for whichever is next
# missing one at a time, submit once complete. The one structural
# difference from apply_leave is that "next missing" isn't a flat list here
# — correction_slot_extractor.next_missing_slot() branches on punch_type's
# value (correct_in_time/correct_out_time are each only required for some
# punch types), matching CorrectionWriteSerializer's own conditional
# requirement instead of asking questions the backend was never going to
# need answered.


def start_request_attendance_correction(request, intent_text: str, confidence: float) -> dict:
    """First turn: pull whatever slots are present in the same utterance
    (e.g. "my clock in on july 22 was wrong, i forgot to punch, it should
    have been 9am" captures date/punch_type/correct_in_time/reason in one
    shot); ask for the rest one at a time."""
    slots = extract_correction_slots(intent_text)
    missing = next_missing_slot(slots)

    if missing is None:
        return _submit(request, slots, confidence)

    set_pending(request.user.id, INTENT_REQUEST_ATTENDANCE_CORRECTION, slots)
    result = {'slots': slots, 'awaiting_slot': missing}
    return _payload(INTENT_REQUEST_ATTENDANCE_CORRECTION, confidence, result, question_for_slot(missing), awaiting_input=True)


def continue_request_attendance_correction(request, pending: dict, answer_text: str) -> dict:
    slots = dict(pending['slots'])
    awaiting = next_missing_slot(slots)

    value, error_message = parse_slot_answer(awaiting, answer_text)
    if error_message:
        # Bad answer: re-ask the SAME slot, don't advance and don't fail
        # silently — same rule apply_leave's slot answers follow.
        set_pending(request.user.id, INTENT_REQUEST_ATTENDANCE_CORRECTION, slots)
        result = {'slots': slots, 'awaiting_slot': awaiting}
        return _payload(INTENT_REQUEST_ATTENDANCE_CORRECTION, None, result, error_message, awaiting_input=True)

    slots[awaiting] = value
    missing = next_missing_slot(slots)

    if missing is None:
        return _submit(request, slots, None)

    set_pending(request.user.id, INTENT_REQUEST_ATTENDANCE_CORRECTION, slots)
    result = {'slots': slots, 'awaiting_slot': missing}
    return _payload(INTENT_REQUEST_ATTENDANCE_CORRECTION, None, result, question_for_slot(missing), awaiting_input=True)


def _submit(request, slots: dict, confidence: Optional[float]) -> dict:
    clear_pending(request.user.id)
    outcome = execute_intent(INTENT_REQUEST_ATTENDANCE_CORRECTION, request, slots=slots)
    return _payload(INTENT_REQUEST_ATTENDANCE_CORRECTION, confidence, outcome.data, outcome.message, success=outcome.success)


def _payload(
    intent: str, confidence: Optional[float], result, message: str,
    awaiting_input: bool = False, success: bool = True,
) -> dict:
    """Small, deliberate duplicate of conversation.py's own private _payload —
    same reasoning conversation_payroll.py's docstring gives for its own copy
    (avoiding a circular import back into conversation.py). speech_message is
    always None here — request_attendance_correction doesn't speak figures or
    a third party's personal details; included for shape-consistency with
    every other _payload builder (see conversation.py's own _payload)."""
    return {
        'intent': intent,
        'confidence': confidence,
        'result': result,
        'message': message,
        'speech_message': None,
        'conversational': get_conversational(intent),
        'awaiting_input': awaiting_input,
        'success': success,
    }
