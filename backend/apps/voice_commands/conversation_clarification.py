from __future__ import annotations

import logging
from typing import Callable, Optional

from apps.attendance.services_geofencing import GPS_REQUIRED_MESSAGE

from apps.voice_commands.approval_extractor import parse_yes_no
from apps.voice_commands.audit import log_clarification_outcome
from apps.voice_commands.clarification import clear_pending, set_pending
from apps.voice_commands.executor import INTENT_CLOCK_IN, INTENT_CLOCK_OUT
from apps.voice_commands.language import get_current_language, set_current_language, text
from apps.voice_commands.matcher import DEFAULT_LANG, get_conversational

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

# Distinct from matcher.NO_MATCH_INTENT on purpose — declining a clarification
# is a normal, expected conversational outcome (the user was asked a direct
# yes/no question and answered it), not an unrecognized command. Giving it its
# own intent name keeps conversation.py's _payload docstring's invariant
# intact ("NO_MATCH_INTENT is always a terminal negative outcome") without
# reusing that marker for a case that is success=True here.
CLARIFICATION_DECLINED_INTENT = 'clarification_declined'

# Bilingual pairs (Phase 3.1 — Gap 1), selected through text() at every call
# site — same pattern executor_*.py's own messages already use.
_DID_YOU_MEAN_TEMPLATE = {
    'en': 'Did you mean: "{phrase}"?',
    'hi': 'क्या आपका मतलब था: "{phrase}"?',
}
_REASK_MESSAGE = {
    'en': 'Sorry, was that a yes or a no — did you mean: "{phrase}"?',
    'hi': 'माफ़ कीजिए, क्या वह हां था या नहीं — क्या आपका मतलब था: "{phrase}"?',
}
# A "no" answer is a deliberate, expected decline — not a failure to
# understand — so it gets its own friendly reset instead of conversation.py's
# generic no-match message (reserved for transcripts that never matched
# anything at all).
_DECLINED_MESSAGE = {
    'en': 'Okay, is there anything else I can help you with?',
    'hi': 'ठीक है, क्या मैं आपकी और किसी चीज़ में मदद कर सकता हूं?',
}


def start_clarification(
    request, candidate_intent: str, matched_phrase: Optional[str], confidence: float,
    intent_text: str, attendance_mode: Optional[str], lang: str,
    source: str = 'rule_engine',
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
    NOT stashed here — the browser only ever attaches them to the specific
    transcript that triggered a geofencing rejection, never to the original,
    location-less command that started the clarification. See
    continue_clarification below for how a clock_in/clock_out confirmation
    that itself gets geofence-rejected still ends up retried with location.

    source distinguishes which tier is asking — the rule engine's own
    middle-confidence band (the default, conversation.py's only caller), or
    llm_fallback.py's low-confidence classification (source='llm') — stashed
    in pending state so continue_clarification below can tag the outcome
    with the right clarification_type for voice_review_report.

    response_language (same leaked-contextvar class of bug Phase 3.1 already
    fixed once for conversation_stt_confirmation.py's start_stt_confirmation
    — see that function's docstring): handle_transcript() has already called
    set_current_language() for THIS turn before this function ever runs, so
    get_current_language() here is exactly the response language the
    original candidate-intent utterance resolved to. Stashed so a confirmed
    "yes" answer (continue_clarification below) can restore it before
    dispatching — otherwise the yes/no answer's own turn (which typically
    carries no STT language signal of its own) re-resolves to English
    regardless of what language the confirmed command was actually in.
    """
    phrase = matched_phrase or candidate_intent
    set_pending(request.user.id, candidate_intent, {
        'stage': CLARIFICATION_STAGE,
        'matched_phrase': phrase,
        'original_text': intent_text,
        'attendance_mode': attendance_mode,
        'lang': lang,
        'source': source,
        'response_language': get_current_language(),
    })
    logger.info(
        'Voice command clarification: user=%s transcript=%r candidate=%s confidence=%s',
        request.user.pk, intent_text, candidate_intent, confidence,
    )
    question = text(_DID_YOU_MEAN_TEMPLATE).format(phrase=phrase)
    # conversational=True is an explicit override, not the registry lookup —
    # the candidate might itself be registered conversational: false (e.g.
    # clock_in, check_leave_balance), but THIS turn is a yes/no question
    # regardless, and needs the same mic/typed-answer follow-up UI apply_leave
    # gets. See _payload below. is_clarification=True: this is the "did you
    # mean X?" question itself — nothing has executed yet, so it's safe for
    # the frontend to silently discard this transcript and retry through
    # Hindi STT rather than treating it as a completed turn.
    return _payload(
        candidate_intent, confidence, None, question,
        awaiting_input=True, conversational=True, is_clarification=True,
    )


def continue_clarification(
    request, pending: dict, answer_text: str,
    dispatch_matched_intent: Callable[..., dict],
    latitude: Optional[float] = None, longitude: Optional[float] = None,
) -> dict:
    """
    Second turn of a pending clarification. dispatch_matched_intent is
    conversation.py's _dispatch_matched_intent, injected by the caller rather
    than imported — see this module's docstring above for why.

    latitude/longitude are whatever the browser attached to THIS turn's
    request — None on the user's original "yes"/"no", populated only on the
    browser's silent geolocation retry (see the re-arming logic below).
    """
    candidate_intent = pending['intent']
    slots = pending['slots']
    matched_phrase = slots.get('matched_phrase') or candidate_intent
    clarification_type = slots.get('source', 'rule_engine')
    decision = parse_yes_no(answer_text)

    # Restore the ORIGINAL utterance's response language up front — before
    # ANY of the three branches below build their response — not just the
    # confirmed/dispatch one. All three (re-ask, declined, confirmed) call
    # text()/_payload() and read the ambient language exactly the same way,
    # and this whole function only ever runs on a SEPARATE turn (the yes/no
    # answer itself) that typically carries no STT language signal of its
    # own — a quiet "haan" answering a Hindi clarification would otherwise
    # get an English re-ask/decline message just as readily as an English
    # dispatch, mid-conversation, in the same language the user has been
    # replying in throughout. Unlike conversation_stt_confirmation.py's
    # equivalent fix, this path never re-enters handle_transcript
    # (dispatch_matched_intent is called directly for confirmed dispatches),
    # so nothing else will set_current_language() for us. See
    # start_clarification's response_language docstring above for where
    # this was stashed.
    response_language = slots.get('response_language')
    if response_language is not None:
        set_current_language(response_language)

    if decision is None:
        # Not a recognizable yes/no — re-ask the same question, don't guess.
        # Re-storing extends the clarification's 120s window, same pattern
        # as leave-approval confirmation's own not-yes-no re-ask.
        set_pending(request.user.id, candidate_intent, slots)
        log_clarification_outcome(request, clarification_type, 're_asked')
        question = text(_REASK_MESSAGE).format(phrase=matched_phrase)
        return _payload(
            candidate_intent, None, None, question,
            awaiting_input=True, conversational=True, is_clarification=True,
        )

    clear_pending(request.user.id)

    if not decision:
        log_clarification_outcome(request, clarification_type, 'declined')
        return _payload(CLARIFICATION_DECLINED_INTENT, None, None, text(_DECLINED_MESSAGE), conversational=True)

    log_clarification_outcome(request, clarification_type, 'confirmed')

    outcome = dispatch_matched_intent(
        request, candidate_intent, slots.get('original_text', ''), None,
        attendance_mode=slots.get('attendance_mode'), lang=slots.get('lang', DEFAULT_LANG),
        latitude=latitude, longitude=longitude,
    )

    # A confirmed clock_in/clock_out that fails specifically for missing GPS
    # is client-retryable: useVoiceCommand.ts's submitTranscript catches this
    # exact rejection, captures the browser's location, and silently
    # resubmits the SAME answer transcript ("yes") with coordinates attached.
    # clear_pending above already fired, so without re-arming it here that
    # resubmit would find no pending state at all and read as a stale/
    # expired answer (see expired_answer_detector.looks_like_expired_slot_answer)
    # instead of finally completing the clock-in with location. Guarded to
    # this one specific rejection with no location yet supplied — any other
    # failure (permission denied, already clocked in, still outside the
    # geofence with GPS already provided, etc.) is terminal and must not
    # re-ask.
    if (
        candidate_intent in (INTENT_CLOCK_IN, INTENT_CLOCK_OUT)
        and not outcome.get('success', True)
        and outcome.get('message') == GPS_REQUIRED_MESSAGE
        and latitude is None and longitude is None
    ):
        set_pending(request.user.id, candidate_intent, slots)

    return outcome


def _payload(
    intent: str, confidence: Optional[float], result, message: str,
    awaiting_input: bool = False, success: bool = True,
    conversational: Optional[bool] = None, is_clarification: bool = False,
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
    present. language (Phase 3): see conversation.py's own _payload docstring.

    is_clarification defaults False; both call sites in this module that ask
    a "did you mean X?" question (start_clarification, and the re-ask branch
    of continue_clarification) pass True explicitly — a clarification
    question hasn't executed anything yet, so the frontend can safely
    discard the mic transcript that produced it and silently retry through
    Hindi STT. Every other outcome this module returns (declined, confirmed
    dispatch) is terminal and keeps the default False.
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
        'language': get_current_language(),
        'is_clarification': is_clarification,
    }
