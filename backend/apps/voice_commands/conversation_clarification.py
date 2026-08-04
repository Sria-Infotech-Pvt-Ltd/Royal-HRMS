from __future__ import annotations

import logging
from typing import Callable, Optional

from apps.voice_commands.approval_extractor import parse_yes_no
from apps.voice_commands.clarification import clear_pending, set_pending
from apps.voice_commands.matcher import DEFAULT_LANG, NO_MATCH_INTENT, get_conversational

logger = logging.getLogger(__name__)

# Split out of conversation.py (which already handles apply_leave and
# approve_leave/reject_leave turn-taking, and is already close to this
# project's 300-line file convention) — mirrors conversation_payroll.py's
# same split, for the same reason. This module owns only the "ask, then
# interpret the yes/no answer" turn-taking for a middle-confidence guess
# (matcher.CLARIFICATION_CONFIDENCE_THRESHOLD <= score <
# matcher.DEFAULT_CONFIDENCE_THRESHOLD — see matcher.match_intent's
# candidate_intent field). The actual per-intent dispatch once confirmed
# (apply_leave's slot-filling start, leave-approval identify step, payroll
# conversational start, or a one-shot execute_intent call) still lives in
# conversation.py's _dispatch_matched_intent — passed into
# continue_clarification() as dispatch_matched_intent rather than imported
# directly, since conversation.py must import start_clarification/
# continue_clarification from here, and importing back the other way would
# create a circular import.

# Distinct from the leave-approval flow's own 'awaiting_name'/
# 'awaiting_confirmation' stage values stored under the same slots['stage']
# key in conversation.py's pending dicts — handle_transcript checks this stage
# first, before pending['intent'] is used to pick a flow, so there's no
# collision even though a clarification's pending 'intent' is the CANDIDATE
# intent (e.g. 'clock_in', 'raise_payslip_query'), not a dedicated marker.
CLARIFICATION_STAGE = 'awaiting_clarification_confirmation'

_REASK_MESSAGE = 'Sorry, was that a yes or a no — did you mean: "{phrase}"?'
_NO_MATCH_MESSAGE = "Sorry, I didn't understand that command."


def start_clarification(
    request, candidate_intent: str, matched_phrase: Optional[str], confidence: float,
    intent_text: str, attendance_mode: Optional[str], lang: str,
) -> dict:
    """
    Instead of the generic no-match message, ask the user to confirm the
    closest registered phrase before acting on it. Reuses clarification.py's
    same pending-state store apply_leave/approve_leave/reject_leave already
    use, and parse_yes_no() for the answer (continue_clarification below) —
    no new mechanism, just a new pending 'stage' value.

    original_text/attendance_mode/lang are stashed so a "yes" answer can
    redispatch using what the user ACTUALLY said the first time (so e.g. a
    slot-filled apply_leave utterance still has its dates recognized on
    confirmation) rather than the literal word "yes". latitude/longitude are
    deliberately NOT threaded through: only clock_in/clock_out ever use them,
    and the browser only ever attaches them to the transcript that triggered
    a geofencing rejection directly, never to an unrelated later "yes"/"no" —
    a clock_in/clock_out landing in this band and then needing geofencing on
    confirmation is a rare, currently-unhandled combination.
    """
    phrase = matched_phrase or candidate_intent
    set_pending(request.user.id, candidate_intent, {
        'stage': CLARIFICATION_STAGE,
        'matched_phrase': phrase,
        'original_text': intent_text,
        'attendance_mode': attendance_mode,
        'lang': lang,
    })
    logger.info(
        'Voice command clarification: user=%s transcript=%r candidate=%s confidence=%s',
        request.user.pk, intent_text, candidate_intent, confidence,
    )
    question = f'Did you mean: "{phrase}"?'
    # conversational=True is an explicit override, not the registry lookup —
    # the candidate might itself be registered conversational: false (e.g.
    # clock_in, check_leave_balance), but THIS turn is a yes/no question
    # regardless, and needs the same mic/typed-answer follow-up UI apply_leave
    # gets. See _payload below.
    return _payload(candidate_intent, confidence, None, question, awaiting_input=True, conversational=True)


def continue_clarification(
    request, pending: dict, answer_text: str,
    dispatch_matched_intent: Callable[..., dict],
) -> dict:
    """
    Second turn of a pending clarification. dispatch_matched_intent is
    conversation.py's _dispatch_matched_intent, injected by the caller rather
    than imported — see this module's docstring above for why.
    """
    candidate_intent = pending['intent']
    slots = pending['slots']
    matched_phrase = slots.get('matched_phrase') or candidate_intent
    decision = parse_yes_no(answer_text)

    if decision is None:
        # Not a recognizable yes/no — re-ask the same question, don't guess.
        # Re-storing extends the clarification's 120s window, same pattern
        # as leave-approval confirmation's own not-yes-no re-ask.
        set_pending(request.user.id, candidate_intent, slots)
        question = _REASK_MESSAGE.format(phrase=matched_phrase)
        return _payload(candidate_intent, None, None, question, awaiting_input=True, conversational=True)

    clear_pending(request.user.id)

    if not decision:
        return _payload(NO_MATCH_INTENT, None, None, _NO_MATCH_MESSAGE, success=False)

    return dispatch_matched_intent(
        request, candidate_intent, slots.get('original_text', ''), None,
        attendance_mode=slots.get('attendance_mode'), lang=slots.get('lang', DEFAULT_LANG),
    )


def _payload(
    intent: str, confidence: Optional[float], result, message: str,
    awaiting_input: bool = False, success: bool = True,
    conversational: Optional[bool] = None,
) -> dict:
    """
    Small, deliberate duplicate of conversation.py's own private _payload —
    same reasoning conversation_payroll.py's docstring gives for its own copy
    (avoiding a circular import back into conversation.py). conversational
    defaults to the registry lookup but both call sites above pass True
    explicitly — see start_clarification's docstring.

    speech_message is always None here (never redacted) — neither the "did
    you mean" question nor the decline/reset message carries figures or a
    third party's personal details (see conversation.py's own _payload for
    where it's actually set); included for shape-consistency with every
    other _payload builder so the frontend can rely on the key always being
    present.
    """
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
