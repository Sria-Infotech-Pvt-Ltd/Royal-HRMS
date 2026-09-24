from __future__ import annotations

from typing import Optional

from apps.voice_commands.approval_extractor import extract_employee_name_query, parse_yes_no
from apps.voice_commands.clarification import clear_pending, set_pending
from apps.voice_commands.executor import (
    INTENT_APPROVE_ATTENDANCE_CORRECTION, INTENT_REJECT_ATTENDANCE_CORRECTION, execute_intent,
)
from apps.voice_commands.language import get_current_language, set_current_language, text
from apps.voice_commands.matcher import get_conversational

# Split out of conversation.py the same way conversation_leave_approval.py
# was — this module owns approve_attendance_correction/
# reject_attendance_correction's multi-turn "identify the request, then
# confirm yes/no" flow, mirroring conversation_leave_approval.py's own shape
# almost exactly. The one structural difference: the confirm-stage pending
# key is slots['correction_id'], not slots['request_id'] — see executor.py's
# own execute_intent docstring for why that's a deliberately distinct name.

ATTENDANCE_CORRECTION_APPROVAL_INTENTS = (
    INTENT_APPROVE_ATTENDANCE_CORRECTION, INTENT_REJECT_ATTENDANCE_CORRECTION,
)
_ATTENDANCE_CORRECTION_APPROVAL_ACTIONS = {
    INTENT_APPROVE_ATTENDANCE_CORRECTION: 'approve', INTENT_REJECT_ATTENDANCE_CORRECTION: 'reject',
}
# action is always 'approve'/'reject' — same local Hindi verb-form lookup
# reasoning conversation_leave_approval.py's own _ACTION_LABELS_HI gives.
_ACTION_LABELS_HI = {'approve': 'स्वीकृत', 'reject': 'अस्वीकृत'}
_CONFIRM_ACTION_TEMPLATE = {
    'en': 'Sorry, was that a yes or a no — should I {action} this attendance correction?',
    'hi': 'माफ़ कीजिए, क्या वह हां था या नहीं — क्या मैं इस उपस्थिति सुधार को {action} करूं?',
}
_NOT_ACTIONED_TEMPLATE = {
    'en': 'Okay, that attendance correction has not been {verb}.',
    'hi': 'ठीक है, वह उपस्थिति सुधार {verb} नहीं किया गया है।',
}


def start_attendance_correction_approval(request, intent: str, intent_text: str, confidence: float) -> dict:
    """First turn of approve_attendance_correction/reject_attendance_correction:
    pull an employee name out of the utterance if one is there (e.g. "approve
    attendance correction for ravindra"), then resolve it the same way a
    disambiguation retry does."""
    name_query = extract_employee_name_query(intent_text)
    return _resolve_attendance_correction_approval_target(request, intent, name_query, confidence, get_current_language())


def _resolve_attendance_correction_approval_target(
    request, intent: str, name_query: Optional[str], confidence: Optional[float], response_language: str,
) -> dict:
    """Shared by the first turn and any "be more specific" retry — see
    conversation_leave_approval.py's own _resolve_leave_approval_target for
    why response_language is threaded through explicitly rather than
    re-read on every call."""
    outcome = execute_intent(intent, request, slots={'stage': 'identify', 'name_query': name_query})
    data = outcome.data or {}
    result_kind = data.get('outcome')

    if result_kind in ('need_name', 'multiple_match'):
        set_pending(request.user.id, intent, {'stage': 'awaiting_name', 'response_language': response_language})
        return _payload(intent, confidence, data, outcome.message, awaiting_input=True)

    if result_kind == 'single_match':
        matched = data['matched']
        set_pending(request.user.id, intent, {
            'stage': 'awaiting_confirmation', 'correction_id': matched['correction_id'],
            'response_language': response_language,
        })
        return _payload(
            intent, confidence, data, outcome.message,
            awaiting_input=True, speech_message=outcome.speech_message,
        )

    # zero_match, permission denied, or a lookup error — nothing to continue.
    return _payload(intent, confidence, data or None, outcome.message, success=outcome.success)


def continue_attendance_correction_approval(request, pending: dict, answer_text: str) -> dict:
    intent = pending['intent']
    stage = pending['slots'].get('stage')

    response_language = pending['slots'].get('response_language')
    if response_language is not None:
        set_current_language(response_language)

    if stage == 'awaiting_confirmation':
        return _continue_attendance_correction_approval_confirmation(request, intent, pending, answer_text)

    # awaiting_name: either the very first "who do you mean" ask, or a
    # "be more specific" retry — the whole answer text IS the name this time.
    return _resolve_attendance_correction_approval_target(
        request, intent, answer_text.strip(), None, response_language or get_current_language(),
    )


def _continue_attendance_correction_approval_confirmation(request, intent: str, pending: dict, answer_text: str) -> dict:
    action = _ATTENDANCE_CORRECTION_APPROVAL_ACTIONS[intent]
    decision = parse_yes_no(answer_text)

    if decision is None:
        set_pending(request.user.id, intent, pending['slots'])
        question = text(_CONFIRM_ACTION_TEMPLATE).format(
            action=text({'en': action, 'hi': _ACTION_LABELS_HI[action]}),
        )
        return _payload(intent, None, None, question, awaiting_input=True)

    correction_id = pending['slots'].get('correction_id')
    clear_pending(request.user.id)

    if not decision:
        verb_en = 'approved' if action == 'approve' else 'rejected'
        verb_hi = _ACTION_LABELS_HI[action]
        message = text(_NOT_ACTIONED_TEMPLATE).format(verb=text({'en': verb_en, 'hi': verb_hi}))
        return _payload(intent, None, None, message)

    outcome = execute_intent(intent, request, slots={'stage': 'confirm', 'correction_id': correction_id})
    return _payload(intent, None, outcome.data, outcome.message, success=outcome.success)


def _payload(
    intent: str, confidence: Optional[float], result, message: str,
    awaiting_input: bool = False, success: bool = True,
    speech_message: Optional[str] = None, is_clarification: bool = False,
) -> dict:
    """Small, deliberate duplicate of conversation.py's own private _payload
    — same reasoning conversation_leave_approval.py's own copy gives
    (avoiding a circular import back into conversation.py)."""
    return {
        'intent': intent,
        'confidence': confidence,
        'result': result,
        'message': message,
        'speech_message': speech_message,
        'conversational': get_conversational(intent),
        'awaiting_input': awaiting_input,
        'success': success,
        'language': get_current_language(),
        'is_clarification': is_clarification,
    }
