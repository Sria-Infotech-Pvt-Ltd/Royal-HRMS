from __future__ import annotations

from typing import Optional

from apps.voice_commands.approval_extractor import extract_employee_name_query, parse_yes_no
from apps.voice_commands.clarification import clear_pending, set_pending
from apps.voice_commands.executor import INTENT_APPROVE_LEAVE, INTENT_REJECT_LEAVE, execute_intent
from apps.voice_commands.language import get_current_language, text
from apps.voice_commands.matcher import get_conversational

# Split out of conversation.py (already close to this project's 300-line
# file convention) the same way conversation_payroll.py and
# conversation_attendance_correction.py were — this module owns
# approve_leave/reject_leave's multi-turn "identify the request, then
# confirm yes/no" flow.

LEAVE_APPROVAL_INTENTS = (INTENT_APPROVE_LEAVE, INTENT_REJECT_LEAVE)
_LEAVE_APPROVAL_ACTIONS = {INTENT_APPROVE_LEAVE: 'approve', INTENT_REJECT_LEAVE: 'reject'}
# action is always 'approve'/'reject' (see _LEAVE_APPROVAL_ACTIONS above) —
# this local Hindi verb-form lookup mirrors executor_approval._ACTION_LABELS_HI
# (same two values) rather than importing that private name across modules;
# `action` is pre-selected through text() before .format() ever runs, same
# single-shared-placeholder reasoning executor_approval._WHO_TO_ACTION_TEMPLATE
# documents, so English/Hindi templates stay structurally comparable.
_ACTION_LABELS_HI = {'approve': 'स्वीकृत', 'reject': 'अस्वीकृत'}
# Bilingual pairs (Phase 3.1 — Gap 1), selected through text() at every call
# site — same pattern executor_*.py's own messages already use.
_CONFIRM_ACTION_TEMPLATE = {
    'en': 'Sorry, was that a yes or a no — should I {action} this leave request?',
    'hi': 'माफ़ कीजिए, क्या वह हां था या नहीं — क्या मैं इस छुट्टी अनुरोध को {action} करूं?',
}
_NOT_ACTIONED_TEMPLATE = {
    'en': 'Okay, that leave request has not been {verb}.',
    'hi': 'ठीक है, वह छुट्टी अनुरोध {verb} नहीं किया गया है।',
}


def start_leave_approval(request, intent: str, intent_text: str, confidence: float) -> dict:
    """First turn of approve_leave/reject_leave: pull an employee name out of
    the utterance if one is there (e.g. "approve leave for sarah"), then
    resolve it the same way a disambiguation retry does."""
    name_query = extract_employee_name_query(intent_text)
    return _resolve_leave_approval_target(request, intent, name_query, confidence)


def _resolve_leave_approval_target(
    request, intent: str, name_query: Optional[str], confidence: Optional[float],
) -> dict:
    """
    Shared by the first turn and any "be more specific" retry — both need
    the same identify step: look up the team's pending requests and
    fuzzy-match name_query against them (execute_intent()'s leave.approve
    gate runs on every call here, not just the final confirm).
    """
    outcome = execute_intent(intent, request, slots={'stage': 'identify', 'name_query': name_query})
    data = outcome.data or {}
    result_kind = data.get('outcome')

    if result_kind in ('need_name', 'multiple_match'):
        set_pending(request.user.id, intent, {'stage': 'awaiting_name'})
        return _payload(intent, confidence, data, outcome.message, awaiting_input=True)

    if result_kind == 'single_match':
        matched = data['matched']
        set_pending(request.user.id, intent, {'stage': 'awaiting_confirmation', 'request_id': matched['request_id']})
        return _payload(
            intent, confidence, data, outcome.message,
            awaiting_input=True, speech_message=outcome.speech_message,
        )

    # zero_match, permission denied, or a lookup error — nothing to continue.
    return _payload(intent, confidence, data or None, outcome.message, success=outcome.success)


def continue_leave_approval(request, pending: dict, answer_text: str) -> dict:
    intent = pending['intent']
    stage = pending['slots'].get('stage')

    if stage == 'awaiting_confirmation':
        return _continue_leave_approval_confirmation(request, intent, pending, answer_text)

    # awaiting_name: either the very first "who do you mean" ask, or a
    # "be more specific" retry — the whole answer text IS the name this time,
    # not a full sentence to run the phrase-extraction regex against.
    return _resolve_leave_approval_target(request, intent, answer_text.strip(), None)


def _continue_leave_approval_confirmation(request, intent: str, pending: dict, answer_text: str) -> dict:
    action = _LEAVE_APPROVAL_ACTIONS[intent]
    decision = parse_yes_no(answer_text)

    if decision is None:
        set_pending(request.user.id, intent, pending['slots'])
        question = text(_CONFIRM_ACTION_TEMPLATE).format(
            action=text({'en': action, 'hi': _ACTION_LABELS_HI[action]}),
        )
        return _payload(intent, None, None, question, awaiting_input=True)

    request_id = pending['slots'].get('request_id')
    clear_pending(request.user.id)

    if not decision:
        verb_en = 'approved' if action == 'approve' else 'rejected'
        verb_hi = _ACTION_LABELS_HI[action]
        message = text(_NOT_ACTIONED_TEMPLATE).format(verb=text({'en': verb_en, 'hi': verb_hi}))
        return _payload(intent, None, None, message)

    outcome = execute_intent(intent, request, slots={'stage': 'confirm', 'request_id': request_id})
    return _payload(intent, None, outcome.data, outcome.message, success=outcome.success)


def _payload(
    intent: str, confidence: Optional[float], result, message: str,
    awaiting_input: bool = False, success: bool = True,
    speech_message: Optional[str] = None, is_clarification: bool = False,
) -> dict:
    """Small, deliberate duplicate of conversation.py's own private _payload —
    same reasoning conversation_payroll.py's docstring gives for its own copy
    (avoiding a circular import back into conversation.py). speech_message,
    language (Phase 3): see conversation.py's own _payload docstring.

    is_clarification defaults False — every awaiting_input turn in this
    module (asking who's meant, re-asking a yes/no approve/reject
    confirmation) is a normal slot-filling/action-confirmation question that
    already narrowed to a specific request, never a "did you mean intent X?"
    question; kept for payload shape-consistency across every builder."""
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
