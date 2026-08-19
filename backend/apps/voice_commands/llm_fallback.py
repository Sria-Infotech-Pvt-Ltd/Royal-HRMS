"""
LLM fallback tier for genuinely unmatched voice transcripts — the second half
of the hybrid architecture described in apps/voice_commands/conversation.py's
handle_transcript(). Classification only: this module's only output is one of
the existing intent names (or nothing at all); it never touches a service,
never mutates anything, and never invents a new intent. Whatever it resolves
gets handed to dispatch_matched_intent — the SAME function a confident rule
match uses — so permission gating (execute_intent's required_permission
check) and slot extraction (extract_apply_leave_slots, correction_slot_extractor,
etc., all still running on the original transcript) are exactly as they were
before this feature existed. Nothing downstream of dispatch_matched_intent
knows or cares whether the intent came from matcher.match_intent() or here.

Called from conversation.py's handle_transcript() only when BOTH of the
existing no-match branches have already declined the transcript — no
clarification-band candidate (fresh_match.candidate_intent is None), and it
doesn't look like an expired slot answer. That's "genuine no-match, below
the clarification floor" — the rule engine, unchanged, always gets first
and only shot at everything above that floor.
"""
from __future__ import annotations

import json
import logging
from typing import Callable, Optional

from apps.voice_commands import sarvam_client
from apps.voice_commands.audit import log_llm_fallback_used
from apps.voice_commands.conversation_clarification import start_clarification
from apps.voice_commands.executor import (
    INTENT_ACKNOWLEDGE_PAYSLIP,
    INTENT_APPLY_LEAVE,
    INTENT_APPROVE_LEAVE,
    INTENT_CANCEL_LEAVE,
    INTENT_CHECK_ATTENDANCE_STATS,
    INTENT_CHECK_ATTENDANCE_SUMMARY,
    INTENT_CHECK_EMPLOYEE_PAYSLIP,
    INTENT_CHECK_LEAVE_BALANCE,
    INTENT_CHECK_LEAVE_STATUS,
    INTENT_CHECK_MY_PAYSLIP,
    INTENT_CHECK_TEAM_ATTENDANCE,
    INTENT_CHECK_TEAM_LEAVE_QUEUE,
    INTENT_CLOCK_IN,
    INTENT_CLOCK_OUT,
    INTENT_GREETING,
    INTENT_RAISE_PAYSLIP_QUERY,
    INTENT_REJECT_LEAVE,
    INTENT_REQUEST_ATTENDANCE_CORRECTION,
)
from apps.voice_commands.matcher import DEFAULT_LANG

logger = logging.getLogger(__name__)

# One line per real, executable intent — used only to build the classifier
# prompt below. Deliberately hand-written rather than pulled from the
# registry's `phrases:` lists: the LLM needs a plain description of what each
# intent DOES, not a bag of example phrasings (which would just bias it
# toward parroting registry wording instead of generalizing).
_INTENT_DESCRIPTIONS: dict[str, str] = {
    INTENT_CLOCK_IN: "Clock the caller in for today.",
    INTENT_CLOCK_OUT: "Clock the caller out for today.",
    INTENT_CHECK_LEAVE_BALANCE: "Report the caller's own remaining leave balance.",
    INTENT_CHECK_LEAVE_STATUS: "Report the status of the caller's own leave requests.",
    INTENT_CANCEL_LEAVE: "Cancel one of the caller's own pending leave requests.",
    INTENT_CHECK_ATTENDANCE_STATS: "Report the caller's own attendance percentage/stats for the month.",
    INTENT_CHECK_ATTENDANCE_SUMMARY: "Report the caller's own monthly attendance summary/report.",
    INTENT_APPLY_LEAVE: "Start a new leave application for the caller (type, dates, reason collected over follow-up questions).",
    INTENT_CHECK_TEAM_LEAVE_QUEUE: "List the caller's team's pending leave requests awaiting approval (manager/HR only).",
    INTENT_CHECK_TEAM_ATTENDANCE: "Report today's team attendance dashboard (manager/HR only).",
    INTENT_APPROVE_LEAVE: "Approve a specific pending leave request for someone on the caller's team (manager/HR only).",
    INTENT_REJECT_LEAVE: "Reject or deny a specific pending leave request for someone on the caller's team (manager/HR only).",
    INTENT_CHECK_MY_PAYSLIP: "Report the caller's own most recent payslip figures.",
    INTENT_ACKNOWLEDGE_PAYSLIP: "Mark the caller's own payslip as acknowledged.",
    INTENT_RAISE_PAYSLIP_QUERY: "Raise a question or dispute about the caller's own payslip, or ask for a copy of it.",
    INTENT_CHECK_EMPLOYEE_PAYSLIP: "Look up another named employee's payslip (payroll staff only).",
    INTENT_REQUEST_ATTENDANCE_CORRECTION: "File a correction request for a wrong punch-in/out time on a specific date.",
    INTENT_GREETING: "A bare greeting with no actual request — hello, hi, good morning, etc.",
}

_ALLOWED_INTENTS = frozenset(_INTENT_DESCRIPTIONS)
_NO_MATCH_LABEL = "no_match"  # what the model is told to say when nothing fits — see prompt below.

# Mirrors mode_extractor.py's _MODE_CONSTANTS keys exactly — these are the
# only attendance modes execute_intent/PunchService understand. Used only as
# a fallback for clock_in/clock_out (see try_llm_fallback below) when
# extract_attendance_mode's English-only regex scan over the ORIGINAL
# transcript found nothing — which is guaranteed for typed Hindi/Hinglish
# text ("ghar se kaam karti hoon" contains no English "home"/"wfh" substring
# for the regex to find, even though it plainly means work-from-home).
# Spoken Hindi never hits this gap: Sarvam Saaras' translate-mode STT (see
# sarvam_client.py) already converts it to English text before it reaches
# extract_attendance_mode at all, so the regex scan finds "home" there just
# fine. This is specifically for the one path that skips that translation —
# a user typing Hindi/Hinglish directly, bypassing STT entirely.
_ALLOWED_MODES = frozenset({"office", "wfh", "field", "client_location", "remote_office"})

# NOT YET CALIBRATED — starting point only, pending real data. The prompt
# below has always asked the model for this field; this module simply never
# read it before now — meaning ANY valid, allow-listed intent was dispatched
# immediately regardless of the confidence the model itself reported,
# including a low-confidence guess for an action-taking intent (clock_in,
# apply_leave, approve_leave, ...). That's a real gap against this app's own
# hard constraint: low confidence must always mean "ask," never "guess and
# act." Every real confidence value observed so far this session (2026-08-17)
# was 0.9-1.0 whenever the model committed to a concrete intent at all — we
# have no real example yet of it reporting genuine low confidence, so this
# threshold is a placeholder pending live examples, same discipline as every
# other threshold calibrated this session (rule engine's own 60/80 split was
# empirically derived from real score distributions, not guessed).
_LLM_CLARIFICATION_THRESHOLD = 0.7

_SYSTEM_PROMPT = (
    "You classify a single spoken or typed command from an HR system's voice "
    "assistant into exactly one intent. The transcript may be in English, "
    "in Hindi or Hinglish (romanized Hindi), or already be an English "
    "translation of Hindi speech — understand its meaning regardless of "
    "language or script. Reply with a single JSON object of the exact shape "
    '{"intent": "<name>", "confidence": <0.0-1.0>, "attendance_mode": '
    '<mode-or-null>} and nothing else. '
    f'"intent" must be one of: {", ".join(sorted(_ALLOWED_INTENTS))}, or '
    f'"{_NO_MATCH_LABEL}" if the transcript genuinely does not fit any of '
    "them. Never invent an intent name outside this list.\n\n"
    '"attendance_mode" only matters when intent is clock_in or clock_out: '
    "set it to one of "
    f'{", ".join(sorted(_ALLOWED_MODES))} only if the transcript itself '
    "states where the caller is working from today (e.g. home/office/field/"
    "a client site) — otherwise null. Never guess a mode the transcript "
    "didn't actually state.\n\nIntents:\n"
    + "\n".join(f"- {name}: {desc}" for name, desc in _INTENT_DESCRIPTIONS.items())
)


def try_llm_fallback(
    request,
    transcript: str,
    intent_text: str,
    attendance_mode: Optional[str],
    lang: str,
    dispatch_matched_intent: Callable[..., dict],
    latitude: Optional[float] = None,
    longitude: Optional[float] = None,
) -> Optional[dict]:
    """
    Attempt to classify `transcript` via sarvam-105b. Returns a dispatch-ready
    payload (from dispatch_matched_intent) on a valid, confirmed classification,
    or None on absolutely anything else — no API key configured, a network/
    timeout failure, a malformed response, or a classification outside the
    fixed intent allow-list (including the model's own "no_match"). None
    tells the caller (conversation.py's handle_transcript) to fall through to
    the exact same generic no-match message this app showed before this
    feature existed — this function never makes the no-match case worse.

    dispatch_matched_intent is conversation.py's own _dispatch_matched_intent,
    injected by the caller rather than imported directly — same
    circular-import-avoidance pattern conversation_clarification.py already
    uses for the same function.

    intent_text (not the LLM's own reading of the transcript) is what actually
    reaches dispatch_matched_intent — deliberately. Slot extraction for
    apply_leave/request_attendance_correction/etc. still runs the existing,
    unchanged extractors against this text; this function's only contribution
    to the outcome is which intent name gets dispatched, plus — only when
    the caller-supplied `attendance_mode` came back None from
    extract_attendance_mode's English-only regex scan — the LLM's own read of
    an explicitly-stated attendance mode. That regex scan structurally can't
    read Hindi/Hinglish text ("ghar se kaam karti hoon" contains no English
    "home" substring), so without this, a clock_in resolved from typed Hindi
    always fell back to office mode and failed geofencing even when the
    caller plainly said they were working from home. The LLM-derived mode
    NEVER overrides a real regex extraction — see _ALLOWED_MODES' comment.

    A valid, allow-listed intent below _LLM_CLARIFICATION_THRESHOLD is NOT
    dispatched directly — it goes through start_clarification (the SAME
    "did you mean X?" mechanism the rule engine's own middle confidence band
    uses), so a low-confidence guess still requires an explicit "yes" before
    anything with side effects runs. See _LLM_CLARIFICATION_THRESHOLD's own
    comment for why this gate didn't exist before now.
    """
    if not sarvam_client.is_configured():
        return None

    raw = sarvam_client.chat_completion(
        messages=[
            {"role": "system", "content": _SYSTEM_PROMPT},
            {"role": "user", "content": transcript},
        ],
    )
    if raw is None:
        log_llm_fallback_used(request, transcript, None)
        return None

    intent, llm_mode, confidence = _parse_response(raw)
    if intent is None or intent == _NO_MATCH_LABEL or intent not in _ALLOWED_INTENTS:
        logger.info(
            'Voice LLM fallback: user=%s transcript=%r resolved=%r (rejected/no_match)',
            request.user.pk, transcript, intent,
        )
        log_llm_fallback_used(request, transcript, None, confidence)
        return None

    resolved_mode = attendance_mode if attendance_mode is not None else llm_mode

    # confidence is None (field omitted/wrong type/out of 0-1 range) is
    # treated as low-confidence too — a model that doesn't comply with the
    # requested response shape gets no benefit of the doubt, consistent with
    # never guessing on uncertain ground.
    if confidence is None or confidence < _LLM_CLARIFICATION_THRESHOLD:
        logger.info(
            'Voice LLM fallback: user=%s transcript=%r low-confidence intent=%s confidence=%s — asking',
            request.user.pk, transcript, intent, confidence,
        )
        log_llm_fallback_used(request, transcript, intent, confidence)
        return start_clarification(
            request, intent, intent.replace('_', ' '), confidence or 0.0,
            intent_text, resolved_mode, lang or DEFAULT_LANG, source='llm',
        )

    logger.info(
        'Voice LLM fallback: user=%s transcript=%r resolved intent=%s mode=%s confidence=%s',
        request.user.pk, transcript, intent, resolved_mode, confidence,
    )
    log_llm_fallback_used(request, transcript, intent, confidence)
    return dispatch_matched_intent(
        request, intent, intent_text, None,
        attendance_mode=resolved_mode, lang=lang or DEFAULT_LANG,
        latitude=latitude, longitude=longitude,
    )


def _parse_response(raw: str) -> tuple[Optional[str], Optional[str], Optional[float]]:
    """
    Pull (`intent`, `attendance_mode`, `confidence`) out of the model's JSON
    reply. Anything that isn't the exact shape we asked for — malformed
    JSON, missing/wrong-type `intent` — returns (None, None, None) rather
    than guessing; try_llm_fallback treats a None intent identically to the
    model explicitly saying no_match. An `attendance_mode` outside the fixed
    allow-list (a hallucinated value, or the model omitting the field
    entirely) is silently dropped to None — same "never invent a value
    outside the list" treatment intent itself already gets. `confidence`
    outside [0.0, 1.0] (or the wrong type, or omitted) is dropped to None
    too — try_llm_fallback treats a None confidence as low-confidence, not
    as "no opinion, dispatch anyway."
    """
    try:
        parsed = json.loads(raw)
        intent = parsed.get("intent")
        intent = intent.strip() if isinstance(intent, str) else None
        mode = parsed.get("attendance_mode")
        mode = mode.strip() if isinstance(mode, str) else None
        if mode not in _ALLOWED_MODES:
            mode = None
        confidence = parsed.get("confidence")
        confidence = float(confidence) if isinstance(confidence, (int, float)) else None
        if confidence is not None and not (0.0 <= confidence <= 1.0):
            confidence = None
        return intent, mode, confidence
    except (ValueError, AttributeError) as exc:
        logger.warning('Voice LLM fallback: could not parse model response %r: %s', raw, exc)
        return None, None, None
