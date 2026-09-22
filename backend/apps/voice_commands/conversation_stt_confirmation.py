from __future__ import annotations

import logging
from typing import Callable, Optional

from apps.voice_commands.approval_extractor import parse_yes_no
from apps.voice_commands.audit import log_clarification_outcome, log_stt_confirmation_started
from apps.voice_commands.clarification import clear_pending, set_pending
from apps.voice_commands.language import get_current_language, set_current_language, text
from apps.voice_commands.matcher import DEFAULT_LANG, NO_MATCH_INTENT, get_conversational

logger = logging.getLogger(__name__)

# Split out for the same reason conversation_clarification.py/
# conversation_payroll.py are their own modules: conversation.py needs to
# import start_stt_confirmation/continue_stt_confirmation, and this module
# needs to call BACK into conversation.py's handle_transcript once the
# transcript is confirmed correct — importing that directly here would be
# circular, so it's injected as a callback (handle_transcript_fn) exactly
# like conversation_clarification.py's dispatch_matched_intent parameter.
#
# This is a DIFFERENT kind of uncertainty than conversation_clarification.py's
# "did you mean intent X?" — that asks whether the TEXT matches the right
# COMMAND. This asks whether Sarvam's STT even transcribed the right TEXT in
# the first place, before any intent matching happens at all — see
# handle_transcript's own STT-confidence gate for why intent-match confidence
# being high is meaningless if the input text itself might be wrong. Reuses
# the exact same Redis-backed pending-state store (clarification.py) as
# every other conversational flow, just a new 'stage' value — no new
# infrastructure, per the project's existing multiplexing convention (see
# conversation_clarification.py's own docstring on this).
STT_CONFIRMATION_STAGE = 'awaiting_stt_confirmation'

# clarification_type tag passed to audit.py's log_clarification_outcome —
# distinct from 'rule_engine'/'llm' (conversation_clarification.py's own
# clarification flavors) since this is a different kind of uncertainty (STT
# transcript trust, not intent match) — see this module's own docstring.
_CLARIFICATION_TYPE = 'stt'

# Bilingual pairs (Phase 3.1 — Gap 1), selected through text() at every call
# site — same pattern executor_*.py's own messages already use.
_TRY_AGAIN_MESSAGE = {
    'en': 'Okay — could you try that again?',
    'hi': 'ठीक है — क्या आप इसे फिर से कहेंगे?',
}
_CONFIRM_TRANSCRIPT_TEMPLATE = {
    'en': 'I think you said "{transcript}" — is that right?',
    'hi': 'मुझे लगा आपने कहा "{transcript}" — क्या यह सही है?',
}
_REASK_YES_NO_TEMPLATE = {
    'en': 'Sorry, was that a yes or a no — did you say "{transcript}"?',
    'hi': 'माफ़ कीजिए, क्या वह हां था या नहीं — क्या आपने कहा "{transcript}"?',
}


def start_stt_confirmation(
    request, transcript: str, lang: str, language_probability: Optional[float] = None,
) -> dict:
    """
    Asks the user to confirm the Sarvam-STT transcript itself is what they
    actually said, BEFORE any intent matching/classification runs on it —
    matching/classifying text that might be wrong would just compound the
    uncertainty. Only reached when stt_language_probability was low enough
    to distrust the transcript outright (see handle_transcript) and there is
    no pending state already (a low-confidence ANSWER to this very question
    — e.g. a quiet "haan"/"nahi" — must not re-trigger another round of this
    same gate; see handle_transcript's `pending is None` guard).

    language_probability is logged (not stored in pending state — the second
    turn never needs it) purely so voice_review_report can plot confirmed/
    declined outcomes against the actual probability that triggered this
    flow, the same way STT_CONFIRM_THRESHOLD itself needs real data to
    calibrate.

    response_language (Phase 3.1 fix — a leaked-contextvar bug of the same
    class Phase 3 already had to catch once): handle_transcript() has
    already called set_current_language() for THIS turn before this function
    ever runs, so get_current_language() here is exactly the response
    language this turn resolved to. Read back and stashed in pending state
    (rather than re-derived) so continue_stt_confirmation's "yes" branch can
    replay it into its own re-entrant handle_transcript_fn call as that
    function's response_language parameter — that call runs
    set_current_language() again from scratch (it's the same
    handle_transcript everything else goes through), and without this it
    would default to English regardless of what language the original,
    now-confirmed transcript was actually in. See handle_transcript's own
    response_language docstring for why this is a separate signal from
    stt_used_language_hint rather than a replay of that same parameter.
    """
    set_pending(request.user.id, NO_MATCH_INTENT, {
        'stage': STT_CONFIRMATION_STAGE,
        'original_transcript': transcript,
        'lang': lang,
        'response_language': get_current_language(),
    })
    logger.info(
        'Voice STT confirmation: user=%s transcript=%r — asking for confirmation',
        request.user.pk, transcript,
    )
    log_stt_confirmation_started(request, transcript, language_probability)
    question = text(_CONFIRM_TRANSCRIPT_TEMPLATE).format(transcript=transcript)
    return _payload(NO_MATCH_INTENT, None, None, question, awaiting_input=True, conversational=True)


def continue_stt_confirmation(
    request, pending: dict, answer_text: str,
    handle_transcript_fn: Callable[..., dict],
) -> dict:
    """
    Second turn. On "yes", re-runs the NORMAL match/classify flow on the
    now-confirmed original transcript — deliberately NOT passing
    stt_language_probability/stt_used_language_hint again (both default to
    None/False), so the gate that brought us here doesn't immediately
    re-trigger on text the user just directly confirmed (pending is already
    cleared below, and handle_transcript's gate re-fires on ANY truthy
    stt_used_language_hint whenever pending is None — see handle_transcript's
    own response_language docstring for why this replay uses that separate
    parameter instead). response_language IS replayed, via that parameter —
    handle_transcript_fn is a re-entrant call into handle_transcript, which
    unconditionally re-runs set_current_language() as its first line;
    without replaying this same turn's resolved language, a confirmed
    Hindi-STT transcript's own dispatch (and every executor message built
    from it) would silently render in English. On "no", stops outright with
    no dispatch of any kind — never falls through to matching/executing
    anything on text the user just said was wrong.
    """
    slots = pending['slots']
    original_transcript = slots['original_transcript']
    lang = slots.get('lang', DEFAULT_LANG)
    response_language = slots.get('response_language')
    decision = parse_yes_no(answer_text)

    # Restore the ORIGINAL utterance's response language up front — the
    # re-ask/declined branches below build their own response directly
    # (unlike the confirmed branch, which re-enters handle_transcript via
    # handle_transcript_fn and replays this explicitly through its own
    # response_language parameter — see this function's own docstring;
    # setting it again here too is harmless, since that re-entrant call
    # immediately overrides it the same way regardless). Without this, a
    # quiet "haan"/"nahi" answering a Hindi "was that transcript right?"
    # question would get an English re-ask/decline message — same class of
    # bug as conversation_clarification.py's continue_clarification fix.
    if response_language is not None:
        set_current_language(response_language)

    if decision is None:
        set_pending(request.user.id, pending['intent'], slots)
        log_clarification_outcome(request, _CLARIFICATION_TYPE, 're_asked')
        question = text(_REASK_YES_NO_TEMPLATE).format(transcript=original_transcript)
        return _payload(NO_MATCH_INTENT, None, None, question, awaiting_input=True, conversational=True)

    clear_pending(request.user.id)

    if not decision:
        logger.info('Voice STT confirmation: user=%s declined transcript=%r', request.user.pk, original_transcript)
        log_clarification_outcome(request, _CLARIFICATION_TYPE, 'declined')
        return _payload(NO_MATCH_INTENT, None, None, text(_TRY_AGAIN_MESSAGE), success=False)

    logger.info('Voice STT confirmation: user=%s confirmed transcript=%r', request.user.pk, original_transcript)
    log_clarification_outcome(request, _CLARIFICATION_TYPE, 'confirmed')
    return handle_transcript_fn(
        request, original_transcript, lang=lang, response_language=response_language,
    )


def _payload(
    intent: str, confidence: Optional[float], result, message: str,
    awaiting_input: bool = False, success: bool = True,
    conversational: Optional[bool] = None, is_clarification: bool = False,
) -> dict:
    """Small, deliberate duplicate of conversation.py's own private _payload
    — same circular-import reasoning conversation_clarification.py's own
    copy documents. language (Phase 3): see conversation.py's own _payload
    docstring.

    is_clarification defaults False — this module's "was that transcript
    right?" question is a distinct kind of yes/no turn from the "did you
    mean X?" intent clarification (conversation_clarification.py is the only
    place this is ever explicitly True); kept here for payload
    shape-consistency across every builder."""
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
