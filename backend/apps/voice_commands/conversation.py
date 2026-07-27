from __future__ import annotations

import logging
from typing import Optional

from apps.voice_commands.approval_extractor import (
    extract_employee_name_query,
    parse_yes_no,
    strip_employee_name_phrases,
)
from apps.voice_commands.clarification import clear_pending, get_pending, set_pending
from apps.voice_commands.conversation_clarification import (
    CLARIFICATION_STAGE,
    continue_clarification,
    start_clarification,
)
from apps.voice_commands.conversation_payroll import (
    PAYROLL_CONVERSATIONAL_INTENTS,
    continue_payroll_conversation,
    start_payroll_conversation,
)
from apps.voice_commands.executor import (
    INTENT_APPLY_LEAVE,
    INTENT_APPROVE_LEAVE,
    INTENT_REJECT_LEAVE,
    execute_intent,
)
from apps.voice_commands.matcher import DEFAULT_LANG, NO_MATCH_INTENT, get_conversational, match_intent
from apps.voice_commands.mode_extractor import extract_attendance_mode
from apps.voice_commands.normalizer import normalize_transcript
from apps.voice_commands.payslip_extractor import (
    strip_employee_name_phrases as strip_payslip_employee_name_phrases,
    strip_payslip_query_phrases,
)
from apps.voice_commands.slot_extractor import (
    extract_apply_leave_slots,
    extract_date_range,
    extract_leave_type,
    next_missing_slot,
    parse_slot_answer,
    question_for_slot,
    strip_leave_slot_phrases,
)

_LEAVE_APPROVAL_INTENTS = (INTENT_APPROVE_LEAVE, INTENT_REJECT_LEAVE)
_LEAVE_APPROVAL_ACTIONS = {INTENT_APPROVE_LEAVE: 'approve', INTENT_REJECT_LEAVE: 'reject'}

logger = logging.getLogger(__name__)

_NO_MATCH_MESSAGE = "Sorry, I didn't understand that command."
_EXPIRED_CLARIFICATION_MESSAGE = "Your leave application timed out — let's start over."


def handle_transcript(
    request, transcript: str, lang: str = DEFAULT_LANG,
    latitude: Optional[float] = None, longitude: Optional[float] = None,
) -> dict:
    """
    Single entry point VoiceParseView.post() calls for every transcript.

    Every intent except apply_leave goes straight through match_intent ->
    execute_intent, exactly as before this feature existed. apply_leave can
    need several turns to collect leave_type, start_date, end_date, and
    reason, so a per-user "pending clarification" is checked first (Redis-
    backed via apps.voice_commands.clarification, 120s TTL) — if one exists,
    this transcript is treated as the answer to the specific slot still
    missing, not matched as a fresh command.

    Exception: if the transcript matches a *different* intent with high
    enough confidence to be recognized at all, the pending state is dropped
    and the transcript is treated as a new command instead — a user who's
    moved on shouldn't be trapped answering questions for a leave request
    they've abandoned. This also covers a pending "did you mean" clarification
    (see conversation_clarification.start_clarification) — a clear, confident
    new command takes priority over a still-unanswered guess.

    latitude/longitude come from the browser only when the frontend already
    has them — either a manual-parity capture on the original request, or a
    silent resubmit after a geofencing rejection prompted it to fetch them
    (see VoiceCommandButton's retry flow). Only clock_in/clock_out ever do
    anything with them (see execute_intent); every other intent ignores
    them, same as attendance_mode.
    """
    user = request.user
    pending = get_pending(user.id)

    normalized = normalize_transcript(transcript)
    attendance_mode, intent_text = extract_attendance_mode(normalized, lang=lang)

    # Slot/name/reason phrases are stripped before matching only, never
    # before extraction — same reason mode_extractor strips mode phrases
    # first: left in, a slot-filled or name-bearing utterance drags the
    # fuzzy score below match_intent()'s threshold. Each strip_*() no-ops
    # when its own pattern is absent, so chaining is safe either way.
    text = strip_leave_slot_phrases(intent_text)
    text = strip_employee_name_phrases(text)
    text = strip_payslip_query_phrases(text)
    matching_text = strip_payslip_employee_name_phrases(text)
    fresh_match = match_intent(matching_text, lang=lang)

    if pending and fresh_match.intent != NO_MATCH_INTENT and fresh_match.intent != pending['intent']:
        logger.info(
            'Voice: abandoning pending %s clarification for user=%s — matched %s instead',
            pending['intent'], user.pk, fresh_match.intent,
        )
        clear_pending(user.id)
        pending = None

    if pending:
        if pending['slots'].get('stage') == CLARIFICATION_STAGE:
            return continue_clarification(request, pending, normalized, _dispatch_matched_intent)
        if pending['intent'] in _LEAVE_APPROVAL_INTENTS:
            return _continue_leave_approval(request, pending, normalized)
        if pending['intent'] in PAYROLL_CONVERSATIONAL_INTENTS:
            return continue_payroll_conversation(request, pending, normalized)
        return _continue_apply_leave(request, pending, normalized)

    if fresh_match.intent == NO_MATCH_INTENT:
        if _looks_like_expired_slot_answer(intent_text):
            logger.info(
                'Voice command: no pending state but transcript looks like an expired '
                'clarification answer — user=%s transcript=%r', user.pk, transcript,
            )
            return _payload(NO_MATCH_INTENT, fresh_match.confidence, None, _EXPIRED_CLARIFICATION_MESSAGE, success=False)
        if fresh_match.candidate_intent:
            return start_clarification(
                request, fresh_match.candidate_intent, fresh_match.matched_phrase,
                fresh_match.confidence, intent_text, attendance_mode, lang,
            )
        logger.info(
            'Voice command no match: user=%s transcript=%r confidence=%s',
            user.pk, transcript, fresh_match.confidence,
        )
        return _payload(NO_MATCH_INTENT, fresh_match.confidence, None, _NO_MATCH_MESSAGE, success=False)

    return _dispatch_matched_intent(
        request, fresh_match.intent, intent_text, fresh_match.confidence,
        attendance_mode=attendance_mode, lang=lang, latitude=latitude, longitude=longitude,
    )


def _dispatch_matched_intent(
    request, intent: str, intent_text: str, confidence: Optional[float],
    attendance_mode: Optional[str] = None, lang: str = DEFAULT_LANG,
    latitude: Optional[float] = None, longitude: Optional[float] = None,
) -> dict:
    """
    Dispatch an intent already resolved with enough confidence to act on —
    either a fresh match straight out of match_intent(), or a middle-
    confidence candidate the caller just confirmed via the "did you mean"
    clarification flow (see conversation_clarification.continue_clarification,
    which receives this function injected as a callback to avoid a circular
    import). Both need the exact same per-intent-shape routing, so this is
    the one place it lives instead of being duplicated between the two call
    sites.
    """
    if intent == INTENT_APPLY_LEAVE:
        return _start_apply_leave(request, intent_text, confidence)

    if intent in _LEAVE_APPROVAL_INTENTS:
        return _start_leave_approval(request, intent, intent_text, confidence)

    if intent in PAYROLL_CONVERSATIONAL_INTENTS:
        return start_payroll_conversation(request, intent, intent_text, confidence)

    outcome = execute_intent(
        intent, request, attendance_mode=attendance_mode, lang=lang,
        latitude=latitude, longitude=longitude,
    )
    logger.info(
        'Voice command: user=%s intent=%s confidence=%s success=%s',
        request.user.pk, intent, confidence, outcome.success,
    )
    return _payload(intent, confidence, outcome.data, outcome.message, success=outcome.success)


def _looks_like_expired_slot_answer(text: str) -> bool:
    """
    Best-effort guess that a transcript matching no registered command was
    actually a targeted answer to an apply_leave clarification question —
    e.g. "sick leave" or "july 24th" — that arrived after its 120s window
    had already lapsed (get_pending() returned None), rather than a
    genuinely unrecognized command. Reuses the exact signals apply_leave's
    own slot extraction looks for (a leave-type keyword, a parseable date)
    so an unrelated gibberish command isn't mislabeled as a timeout.
    """
    if extract_leave_type(text):
        return True
    start, end = extract_date_range(text)
    return bool(start or end)


def _start_apply_leave(request, intent_text: str, confidence: float) -> dict:
    """First turn: pull whatever slots are present in the same utterance (e.g.
    "apply for sick leave from july 22 to july 24" captures all but reason
    in one shot); ask for the rest one at a time, most-specific-first."""
    slots = extract_apply_leave_slots(intent_text)
    missing = next_missing_slot(slots)

    if missing is None:
        outcome = execute_intent(INTENT_APPLY_LEAVE, request, slots=slots)
        return _payload(INTENT_APPLY_LEAVE, confidence, outcome.data, outcome.message, success=outcome.success)

    set_pending(request.user.id, INTENT_APPLY_LEAVE, slots)
    result = {'slots': slots, 'awaiting_slot': missing}
    return _payload(INTENT_APPLY_LEAVE, confidence, result, question_for_slot(missing), awaiting_input=True)


def _continue_apply_leave(request, pending: dict, answer_text: str) -> dict:
    intent = pending['intent']
    slots = dict(pending['slots'])
    awaiting = next_missing_slot(slots)

    value, error_message = parse_slot_answer(awaiting, answer_text)
    if error_message:
        # Bad answer: re-ask the SAME slot, don't advance and don't fail
        # silently. Re-storing extends the clarification's 120s window.
        set_pending(request.user.id, intent, slots)
        result = {'slots': slots, 'awaiting_slot': awaiting}
        return _payload(intent, None, result, error_message, awaiting_input=True)

    slots[awaiting] = value
    missing = next_missing_slot(slots)

    if missing is None:
        clear_pending(request.user.id)
        outcome = execute_intent(intent, request, slots=slots)
        return _payload(intent, None, outcome.data, outcome.message, success=outcome.success)

    set_pending(request.user.id, intent, slots)
    result = {'slots': slots, 'awaiting_slot': missing}
    return _payload(intent, None, result, question_for_slot(missing), awaiting_input=True)


def _start_leave_approval(request, intent: str, intent_text: str, confidence: float) -> dict:
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
        return _payload(intent, confidence, data, outcome.message, awaiting_input=True)

    # zero_match, permission denied, or a lookup error — nothing to continue.
    return _payload(intent, confidence, data or None, outcome.message, success=outcome.success)


def _continue_leave_approval(request, pending: dict, answer_text: str) -> dict:
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
        question = f'Sorry, was that a yes or a no — should I {action} this leave request?'
        return _payload(intent, None, None, question, awaiting_input=True)

    request_id = pending['slots'].get('request_id')
    clear_pending(request.user.id)

    if not decision:
        verb = 'approved' if action == 'approve' else 'rejected'
        return _payload(intent, None, None, f"Okay, that leave request has not been {verb}.")

    outcome = execute_intent(intent, request, slots={'stage': 'confirm', 'request_id': request_id})
    return _payload(intent, None, outcome.data, outcome.message, success=outcome.success)


def _payload(
    intent: str, confidence: Optional[float], result, message: str,
    awaiting_input: bool = False, success: bool = True,
) -> dict:
    """
    conversational reflects the registry (get_conversational) — a property of
    the intent itself, true for apply_leave on every one of its responses
    (including an immediate single-utterance submission), false for
    everything else, including NO_MATCH_INTENT (never registered).
    conversation_clarification.py's own _payload duplicate is the one place
    that overrides this — see its docstring for why.

    awaiting_input reflects THIS response only: true exactly when pending
    clarification state now exists in Redis and the caller needs to answer a
    follow-up question, false once a conversational flow has actually
    completed (or errored out) and whenever the intent was never
    conversational to begin with — see _start_apply_leave/_continue_apply_leave
    above for the only call sites that pass True.

    success defaults to True — every call site that is mid-dialogue (asking
    for a missing slot, re-asking after a bad answer, awaiting yes/no) is a
    normal continuation, not a failure. Call sites explicitly pass False only
    for a genuinely terminal negative outcome: NO_MATCH_INTENT, or an
    ExecutionResult whose own .success is False (permission denied, a
    geofencing rejection, a validation error from the underlying view, etc.)
    — see VoiceCommandButton's retry flow, which keys off this field to
    decide whether a clock_in/clock_out rejection is worth retrying with
    geolocation.
    """
    return {
        'intent': intent,
        'confidence': confidence,
        'result': result,
        'message': message,
        'conversational': get_conversational(intent),
        'awaiting_input': awaiting_input,
        'success': success,
    }
