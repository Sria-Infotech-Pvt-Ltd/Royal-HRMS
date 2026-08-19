from __future__ import annotations

import logging
from typing import Callable, Optional

from apps.voice_commands.approval_extractor import parse_yes_no
from apps.voice_commands.audit import log_clarification_outcome, log_stt_confirmation_started
from apps.voice_commands.clarification import clear_pending, set_pending
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

_TRY_AGAIN_MESSAGE = "Okay — could you try that again?"


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
    """
    set_pending(request.user.id, NO_MATCH_INTENT, {
        'stage': STT_CONFIRMATION_STAGE,
        'original_transcript': transcript,
        'lang': lang,
    })
    logger.info(
        'Voice STT confirmation: user=%s transcript=%r — asking for confirmation',
        request.user.pk, transcript,
    )
    log_stt_confirmation_started(request, transcript, language_probability)
    question = f'I think you said "{transcript}" — is that right?'
    return _payload(NO_MATCH_INTENT, None, None, question, awaiting_input=True, conversational=True)


def continue_stt_confirmation(
    request, pending: dict, answer_text: str,
    handle_transcript_fn: Callable[..., dict],
) -> dict:
    """
    Second turn. On "yes", re-runs the NORMAL match/classify flow on the
    now-confirmed original transcript — deliberately NOT passing
    stt_language_probability again (defaults to None), so the gate that
    brought us here doesn't immediately re-trigger on text the user just
    directly confirmed. On "no", stops outright with no dispatch of any
    kind — never falls through to matching/executing anything on text the
    user just said was wrong.
    """
    slots = pending['slots']
    original_transcript = slots['original_transcript']
    lang = slots.get('lang', DEFAULT_LANG)
    decision = parse_yes_no(answer_text)

    if decision is None:
        set_pending(request.user.id, pending['intent'], slots)
        log_clarification_outcome(request, _CLARIFICATION_TYPE, 're_asked')
        question = f'Sorry, was that a yes or a no — did you say "{original_transcript}"?'
        return _payload(NO_MATCH_INTENT, None, None, question, awaiting_input=True, conversational=True)

    clear_pending(request.user.id)

    if not decision:
        logger.info('Voice STT confirmation: user=%s declined transcript=%r', request.user.pk, original_transcript)
        log_clarification_outcome(request, _CLARIFICATION_TYPE, 'declined')
        return _payload(NO_MATCH_INTENT, None, None, _TRY_AGAIN_MESSAGE, success=False)

    logger.info('Voice STT confirmation: user=%s confirmed transcript=%r', request.user.pk, original_transcript)
    log_clarification_outcome(request, _CLARIFICATION_TYPE, 'confirmed')
    return handle_transcript_fn(request, original_transcript, lang=lang)


def _payload(
    intent: str, confidence: Optional[float], result, message: str,
    awaiting_input: bool = False, success: bool = True,
    conversational: Optional[bool] = None,
) -> dict:
    """Small, deliberate duplicate of conversation.py's own private _payload
    — same circular-import reasoning conversation_clarification.py's own
    copy documents."""
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
