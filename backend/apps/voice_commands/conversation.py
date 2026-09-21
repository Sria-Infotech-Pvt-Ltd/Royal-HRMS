from __future__ import annotations

import logging
from typing import Optional

from apps.voice_commands.approval_extractor import strip_employee_name_phrases
from apps.voice_commands.audit import log_no_match
from apps.voice_commands.clarification import clear_pending, get_pending, set_pending
from apps.voice_commands.conversation_attendance_correction import (
    continue_request_attendance_correction,
    start_request_attendance_correction,
)
from apps.voice_commands.conversation_clarification import (
    CLARIFICATION_STAGE,
    continue_clarification,
    start_clarification,
)
from apps.voice_commands.conversation_clock_in_face import (
    AWAITING_FACE_PROOF_STAGE,
    continue_voice_clock_punch,
    start_voice_clock_punch,
)
from apps.voice_commands.conversation_leave_approval import (
    LEAVE_APPROVAL_INTENTS,
    continue_leave_approval,
    start_leave_approval,
)
from apps.voice_commands.conversation_payroll import (
    PAYROLL_CONVERSATIONAL_INTENTS,
    continue_payroll_conversation,
    start_payroll_conversation,
)
from apps.voice_commands.conversation_stt_confirmation import (
    STT_CONFIRMATION_STAGE,
    continue_stt_confirmation,
    start_stt_confirmation,
)
from apps.voice_commands.correction_slot_extractor import strip_correction_slot_phrases
from apps.voice_commands.executor import (
    INTENT_APPLY_LEAVE,
    INTENT_CLOCK_IN,
    INTENT_CLOCK_OUT,
    INTENT_REQUEST_ATTENDANCE_CORRECTION,
    execute_intent,
)
from apps.voice_commands.expired_answer_detector import looks_like_expired_slot_answer as _looks_like_expired_slot_answer
from apps.voice_commands.language import detect_language, get_current_language, set_current_language, text
from apps.voice_commands.llm_fallback import try_llm_fallback
from apps.voice_commands.matcher import DEFAULT_LANG, NO_MATCH_INTENT, get_conversational, match_intent
from apps.voice_commands.mode_extractor import extract_attendance_mode
from apps.voice_commands.normalizer import normalize_transcript
from apps.voice_commands.payslip_extractor import (
    strip_employee_name_phrases as strip_payslip_employee_name_phrases,
    strip_payslip_query_phrases,
)
from apps.voice_commands.slot_extractor import (
    extract_apply_leave_slots,
    next_missing_slot,
    parse_slot_answer,
    question_for_slot,
    strip_leave_slot_phrases,
)

logger = logging.getLogger(__name__)

# Shown when NOTHING at all was usable — no clarification candidate,
# doesn't look like an expired slot answer, and the LLM tier also declined
# (unavailable, or genuinely no_match with no candidate of its own).
# Deliberately stateless — no new pending state, since there's no candidate
# to confirm against, unlike the clarification branches above/below which DO
# store pending state to interpret the next turn as an answer. Friendlier
# than the flat "didn't understand" wording this constant used to hold —
# same name kept so existing tests asserting against this constant (not a
# hardcoded string) automatically track the improved wording. Bilingual pair
# (Phase 3.1 — Gap 1) rather than a bare string, selected through text() at
# every call site, same pattern executor_*.py's own messages already use.
_NO_MATCH_MESSAGE = {
    'en': "Sorry, I didn't catch that — could you say it differently?",
    'hi': 'माफ़ कीजिए, मैं समझ नहीं पाया — क्या आप इसे दूसरे तरीके से कह सकते हैं?',
}
# Generic on purpose — apply_leave was the only conversational intent when
# this was first written, but request_attendance_correction is conversational
# now too (see _looks_like_expired_slot_answer below), and any future
# multi-turn intent will hit this same branch.
_EXPIRED_CLARIFICATION_MESSAGE = {
    'en': "Your request timed out — let's start over.",
    'hi': 'आपका अनुरोध समय सीमा समाप्त हो गया — कृपया फिर से शुरू करें।',
}

# NOT YET CALIBRATED — starting point only, pending real data. Every genuine
# failure observed this session (2026-08-17, including the same audio bytes
# resubmitted 3x producing 3 different transcripts across 2 different
# detected languages) had language_probability under 0.4; every value above
# that threshold for a GOOD transcription is still unmeasured, since
# sarvam_client.transcribe_audio only started logging this on success in
# this same change. Sized with margin above the observed bad range, not
# proven against the good range yet — same discipline as every other
# threshold calibrated this session.
STT_CONFIRM_THRESHOLD = 0.5


def handle_transcript(
    request, transcript: str, lang: str = DEFAULT_LANG,
    latitude: Optional[float] = None, longitude: Optional[float] = None,
    face_embedding: Optional[list] = None, liveness_passed: Optional[bool] = None,
    liveness_score: Optional[float] = None, capture_session_id: str = '',
    stt_language_probability: Optional[float] = None,
    stt_used_language_hint: bool = False,
    stt_detected_language: Optional[str] = None,
    response_language: Optional[str] = None,
) -> dict:
    """
    Single entry point VoiceParseView.post() calls for every transcript.

    stt_language_probability: only ever set by the frontend on a transcript
    that came back from the Sarvam-STT retry (captureAndTranscribeViaSarvam)
    — None for browser SpeechRecognition output or typed input, which have
    no comparable per-utterance confidence signal at all. Below
    STT_CONFIRM_THRESHOLD, the transcript is confirmed with the user BEFORE
    any matching/classification runs on it at all (see the gate just below)
    — a confident intent match means nothing if the input text itself might
    be wrong, which is a real, confirmed failure mode (see
    conversation_stt_confirmation.py's own docstring). Deliberately checked
    only when `pending` is None: the ANSWER to this very question (e.g. a
    quiet "haan"/"nahi") is itself a Sarvam-STT transcript with its own low
    language_probability sometimes — re-applying this gate to that answer
    would loop the confirmation question on itself.

    stt_used_language_hint: True only when the Sarvam-STT retry succeeded via
    its explicit-Hindi-hint attempt (views_transcribe.py tries hi-IN before
    falling back to auto-detect — see its own docstring). Confirmed against
    real docs.sarvam.ai docs: a hinted call never gets a language_probability
    back at all, so stt_language_probability is always None for these and the
    usual threshold check above has nothing to test. Rather than treat "no
    signal" as "trustworthy by default" — the opposite of this gate's whole
    purpose — a hinted transcript always goes through confirmation. This
    field's meaning and role in the gate above are UNCHANGED by Phase 4 —
    stt_detected_language (below) only changes which signal decides EN vs HI
    text/voice selection, never this gate's own trust logic.

    stt_detected_language (Phase 4 — completes Phase 3.1's Gap 2): 'en' or
    'hi', forwarded by useVoiceCommand.ts from views_transcribe.py's own
    `detected_language` field — the tier (hi-IN vs en-IN hint) that actually
    produced the Sarvam-STT retry's transcript, known deterministically
    server-side with no new API call. Passed straight through to
    language.detect_language(), which prefers it over the
    stt_used_language_hint-derived approximation when present — see that
    function's own docstring. Does not participate in the STT-confirmation
    gate above at all; only stt_used_language_hint/stt_language_probability
    do.

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

    face_embedding/liveness_passed/liveness_score/capture_session_id: same
    silent-resubmit shape, for clock_in/clock_out's "taking facial proof"
    turn (conversation_clock_in_face.py) — every other intent ignores them.

    Sets the ambient response language (apps.voice_commands.language) from
    stt_used_language_hint FIRST, before anything else below runs — this is
    the single entry point every transcript passes through (see this
    docstring's own opening line), so every executor_*.py message built
    anywhere downstream of this call, however many turns deep, reads the
    correct language for THIS request. See language.detect_language's own
    docstring for exactly what this signal does and doesn't tell us.

    response_language (Phase 3.1 — fixes a leaked-contextvar bug of the same
    class Phase 3 already had to catch once): set instead of
    detect_language(stt_used_language_hint) when given. The one caller that
    passes it is conversation_stt_confirmation.continue_stt_confirmation's
    "yes" branch, which re-enters handle_transcript on the now-confirmed
    original transcript — this function unconditionally re-runs
    set_current_language() as its very first line on every call (including
    that re-entrant one), so without a way to replay the language THAT
    original transcript resolved to, a confirmed Hindi-STT command would
    silently dispatch and speak back in English. Deliberately a SEPARATE
    parameter from stt_used_language_hint rather than reusing it for this
    replay — stt_used_language_hint also drives the STT-confirmation gate
    below (pending is None and (... or stt_used_language_hint)), and that
    re-entrant call already has pending=None (clear_pending already ran);
    replaying stt_used_language_hint=True there would re-trigger this exact
    same confirmation question forever instead of finally dispatching.
    """
    if response_language is not None:
        set_current_language(response_language)
    else:
        set_current_language(detect_language(stt_used_language_hint, stt_detected_language))

    user = request.user
    pending = get_pending(user.id)

    if pending is None and (
        (stt_language_probability is not None and stt_language_probability < STT_CONFIRM_THRESHOLD)
        or stt_used_language_hint
    ):
        return start_stt_confirmation(request, transcript, lang, stt_language_probability)

    normalized = normalize_transcript(transcript)
    attendance_mode, intent_text = extract_attendance_mode(normalized, lang=lang)

    # Slot/name/reason phrases are stripped before matching only, never
    # before extraction — same reason mode_extractor strips mode phrases
    # first: left in, a slot-filled or name-bearing utterance drags the
    # fuzzy score below match_intent()'s threshold. Each strip_*() no-ops
    # when its own pattern is absent, so chaining is safe either way.
    stripped_text = strip_leave_slot_phrases(intent_text)
    stripped_text = strip_employee_name_phrases(stripped_text)
    stripped_text = strip_payslip_query_phrases(stripped_text)
    stripped_text = strip_payslip_employee_name_phrases(stripped_text)
    matching_text = strip_correction_slot_phrases(stripped_text)
    fresh_match = match_intent(matching_text, lang=lang)

    if pending and _should_abandon_pending(pending, fresh_match):
        logger.info(
            'Voice: abandoning pending %s clarification for user=%s — matched %s instead',
            pending['intent'], user.pk,
            fresh_match.intent if fresh_match.intent != NO_MATCH_INTENT else fresh_match.candidate_intent,
        )
        clear_pending(user.id)
        pending = None

    if pending:
        return _dispatch_pending(
            request, pending, normalized, latitude, longitude,
            face_embedding, liveness_passed, liveness_score, capture_session_id,
        )

    if fresh_match.intent == NO_MATCH_INTENT:
        # Every path through this branch — a "did you mean" candidate, an
        # expired-slot-answer guess, or a flat no-match — is a no-match/
        # low-confidence event for audit purposes; logged once here rather
        # than in each of the three branches below. See apps/voice_commands/
        # audit.py's own docstring for why this goes to the real AuditLog
        # table, not just this module's file logger.
        log_no_match(request, transcript, fresh_match.confidence, fresh_match.candidate_intent)

        # A real fuzzy-match signal against actual registered phrases beats
        # the expired-slot-answer heuristic below, which is just a crude
        # keyword-in-text guess — checked first so a genuinely correction-
        # or leave-flavored first utterance that merely scores in the
        # clarification band (e.g. mentions "clock in"/"clock out" as part
        # of a longer sentence, which also happens to satisfy the expired-
        # answer heuristic) gets the far more useful "did you mean" question
        # instead of being misread as an expired session that never existed.
        if fresh_match.candidate_intent:
            return start_clarification(
                request, fresh_match.candidate_intent, fresh_match.matched_phrase,
                fresh_match.confidence, intent_text, attendance_mode, lang,
            )
        if _looks_like_expired_slot_answer(intent_text):
            logger.info(
                'Voice command: no pending state but transcript looks like an expired '
                'clarification answer — user=%s transcript=%r', user.pk, transcript,
            )
            return _payload(NO_MATCH_INTENT, fresh_match.confidence, None, text(_EXPIRED_CLARIFICATION_MESSAGE), success=False)

        # Genuine no-match, below the clarification floor — the ONE point
        # where the hybrid architecture's LLM fallback tier gets a shot,
        # after the rule engine (matcher.match_intent, the clarification
        # band, and the expired-slot-answer heuristic above) has already
        # declined the transcript outright. Classification only — see
        # llm_fallback.py's own docstring: its output is dispatched through
        # this exact same _dispatch_matched_intent every rule match uses, so
        # permission gating and slot extraction are untouched either way.
        # Fails soft to the plain message below on absolutely anything
        # (no API key configured, a Sarvam outage, or the model itself
        # answering no_match) — never a worse outcome than before this tier
        # existed.
        llm_outcome = try_llm_fallback(
            request, transcript, intent_text, attendance_mode, lang,
            _dispatch_matched_intent, latitude=latitude, longitude=longitude,
        )
        if llm_outcome is not None:
            return llm_outcome

        logger.info(
            'Voice command no match: user=%s transcript=%r confidence=%s',
            user.pk, transcript, fresh_match.confidence,
        )
        return _payload(NO_MATCH_INTENT, fresh_match.confidence, None, text(_NO_MATCH_MESSAGE), success=False)

    return _dispatch_matched_intent(
        request, fresh_match.intent, intent_text, fresh_match.confidence,
        attendance_mode=attendance_mode, lang=lang, latitude=latitude, longitude=longitude,
    )


def _should_abandon_pending(pending: dict, fresh_match) -> bool:
    """
    True when a fresh utterance should override still-pending state rather
    than being read as its continuation.

    Two distinct cases:
    1. fresh_match resolved CONFIDENTLY to a different intent than pending's
       — the existing rule, covers every pending stage including mid-slot-
       filling (apply_leave's date/type answers, leave-approval's name/
       confirm steps, ...): a clean, confident match to something else means
       the user has moved on.
    2. pending is itself an unanswered "confirm this" turn (did-you-mean /
       was-that-what-you-said — CLARIFICATION_STAGE or STT_CONFIRMATION_STAGE)
       AND fresh_match is at least a middle-confidence candidate for a
       DIFFERENT intent. Both of those stages only ever expect a yes/no
       answer (see continue_clarification/continue_stt_confirmation's own
       parse_yes_no calls) — neither recognizes a brand-new command as
       anything but an unparseable non-answer, so without this, a user who
       ignores the question and says something else entirely (which then
       ALSO happens to land in the clarification band for its own, different
       candidate) gets that new command silently swallowed: parse_yes_no
       returns None and the stale question gets re-asked verbatim, reading
       to the user as "did you mean <the OLD command>?" for something they
       never said. Deliberately NOT extended to slot-filling stages (a slot
       answer's shape — a date, a leave type, free text — makes a stray
       clarification-band coincidence far more likely and far less
       meaningful than it is for a plain yes/no turn).
    """
    if fresh_match.intent != NO_MATCH_INTENT:
        return fresh_match.intent != pending['intent']

    stage = pending['slots'].get('stage')
    if stage not in (CLARIFICATION_STAGE, STT_CONFIRMATION_STAGE):
        return False
    return fresh_match.candidate_intent is not None and fresh_match.candidate_intent != pending['intent']


def _dispatch_pending(
    request, pending: dict, normalized: str, latitude: Optional[float], longitude: Optional[float],
    face_embedding: Optional[list], liveness_passed: Optional[bool],
    liveness_score: Optional[float], capture_session_id: str,
) -> dict:
    """Routes an existing pending conversation to whichever flow owns it —
    extracted out of handle_transcript to keep that function under this
    project's 50-line convention as the number of conversational flows grew."""
    if pending['slots'].get('stage') == CLARIFICATION_STAGE:
        return continue_clarification(
            request, pending, normalized, _dispatch_matched_intent,
            latitude=latitude, longitude=longitude,
        )
    if pending['slots'].get('stage') == STT_CONFIRMATION_STAGE:
        # handle_transcript itself, passed as a callback — see
        # conversation_stt_confirmation.py's own docstring for why (it must
        # be able to re-run the normal match/classify flow on a confirmed
        # transcript without importing this module directly).
        return continue_stt_confirmation(request, pending, normalized, handle_transcript)
    if pending['slots'].get('stage') == AWAITING_FACE_PROOF_STAGE:
        return continue_voice_clock_punch(
            request, pending, face_embedding, liveness_passed, liveness_score, capture_session_id,
        )
    if pending['intent'] in LEAVE_APPROVAL_INTENTS:
        return continue_leave_approval(request, pending, normalized)
    if pending['intent'] in PAYROLL_CONVERSATIONAL_INTENTS:
        return continue_payroll_conversation(request, pending, normalized)
    if pending['intent'] == INTENT_REQUEST_ATTENDANCE_CORRECTION:
        return continue_request_attendance_correction(request, pending, normalized)
    return _continue_apply_leave(request, pending, normalized)


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

    if intent in LEAVE_APPROVAL_INTENTS:
        return start_leave_approval(request, intent, intent_text, confidence)

    if intent in PAYROLL_CONVERSATIONAL_INTENTS:
        return start_payroll_conversation(request, intent, intent_text, confidence)

    if intent == INTENT_REQUEST_ATTENDANCE_CORRECTION:
        return start_request_attendance_correction(request, intent_text, confidence)

    if intent in (INTENT_CLOCK_IN, INTENT_CLOCK_OUT):
        return start_voice_clock_punch(request, intent, attendance_mode, confidence, latitude, longitude)

    # raw_text forwarded as slots['raw_text'] — only check_payroll_cost_summary/
    # check_branch_payroll_breakdown read it today (to extract an optional
    # spoken period via payroll_period_extractor.py; see executor.py's own
    # execute_intent docstring). Every other intent on this generic path
    # ignores an unrecognized slots key, same as it already ignores slots
    # being absent entirely.
    outcome = execute_intent(
        intent, request, attendance_mode=attendance_mode, lang=lang,
        slots={'raw_text': intent_text}, latitude=latitude, longitude=longitude,
    )
    logger.info(
        'Voice command: user=%s intent=%s confidence=%s success=%s',
        request.user.pk, intent, confidence, outcome.success,
    )
    return _payload(
        intent, confidence, outcome.data, outcome.message,
        success=outcome.success, speech_message=outcome.speech_message,
    )


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


def _payload(
    intent: str, confidence: Optional[float], result, message: str,
    awaiting_input: bool = False, success: bool = True,
    speech_message: Optional[str] = None, is_clarification: bool = False,
) -> dict:
    """
    speech_message is the redacted stand-in for `message` that VoiceParseView's
    caller should actually pass to TTS — None (the default, true for almost
    every call site) means "speak `message` unchanged". Only set by intents
    whose ExecutionResult.speech_message was itself set — see that field's
    own docstring for which intents and why. `message` is never redacted; it
    always carries the full detail for the panel/toast.

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

    language (Phase 3) is the ambient value set at the top of
    handle_transcript — "en" or "hi", the detected input language that
    decided which of message/speech_message's string this response actually
    carries (see language.detect_language's own docstring for the exact
    signal and its limits). Present on every response, not just ones with a
    Hindi counterpart to select, so the frontend can rely on the key always
    being there — same reasoning speech_message's own always-present-but-
    often-None shape already follows.

    is_clarification defaults False here — every call site in this module is
    either a terminal outcome or a normal slot-filling question (e.g.
    _continue_apply_leave asking for a missing leave slot), never the
    low/mid-confidence "did you mean X?" question itself (that lives in
    conversation_clarification.py's own _payload, the only place this is
    ever explicitly True). Present on every response for the same
    always-there reasoning as language/speech_message above.
    """
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
