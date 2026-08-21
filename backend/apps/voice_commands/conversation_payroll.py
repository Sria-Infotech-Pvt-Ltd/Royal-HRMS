from __future__ import annotations

from typing import Optional

from apps.voice_commands.clarification import clear_pending, set_pending
from apps.voice_commands.executor import (
    INTENT_CHECK_EMPLOYEE_PAYSLIP,
    INTENT_RAISE_PAYSLIP_QUERY,
    execute_intent,
)
from apps.voice_commands.language import get_current_language, text
from apps.voice_commands.matcher import get_conversational
from apps.voice_commands.payslip_extractor import (
    extract_employee_name_query,
    extract_payslip_query_description,
    looks_like_download_request,
)

# Exported so conversation.py's handle_transcript can route on these without
# importing the two INTENT_* constants directly itself — keeps its own
# import list (and line count; it's a pre-existing file already near this
# project's 300-line convention) from growing with every new payroll intent.
PAYROLL_CONVERSATIONAL_INTENTS = (INTENT_RAISE_PAYSLIP_QUERY, INTENT_CHECK_EMPLOYEE_PAYSLIP)

# Split out of conversation.py (which already handles apply_leave and
# approve_leave/reject_leave turn-taking) rather than added into it directly
# — conversation.py is already close to this project's 300-line file
# convention, and this task's scope is payroll, not restructuring the
# existing leave conversation logic. Mirrors executor.py's own recent split
# into executor_attendance/leave/approval.py: conversation.py keeps only the
# routing (which module owns the pending intent / fresh match), the actual
# turn-taking logic lives here.

_MIN_DESCRIPTION_LENGTH = 10  # voice-only floor — PayslipQuerySerializer has no minimum of its
# own (see executor_payroll.execute_raise_payslip_query), but submitting a one-word reflex
# answer ("no", "nothing") as a real HR query would be a bad outcome. Mirrors the spirit of
# slot_extractor.py's _MIN_REASON_LENGTH, without a serializer validator to mirror here.

# Bilingual pairs (Phase 3.1 — Gap 1), selected through text() at every call
# site — same pattern executor_*.py's own messages already use.
_QUERY_QUESTION = {
    'en': 'What would you like to ask about your payslip?',
    'hi': 'आप अपनी पेस्लिप के बारे में क्या पूछना चाहेंगे?',
}
# looks_like_download_request() is a keyword check on the transcript itself, independent of
# which registered phrase the fuzzy matcher actually landed on — both the direct-query phrases
# and the download-flavored ones resolve to this same intent (registry/intents_en.yaml), so this
# is the only signal available for picking which preamble to open with.
_DOWNLOAD_REDIRECT_PREFIX = {
    'en': "Payslip downloads aren't available yet — I can raise a query with HR on your behalf instead. ",
    'hi': 'पेस्लिप डाउनलोड अभी उपलब्ध नहीं है — इसके बजाय मैं आपकी ओर से एचआर के पास एक प्रश्न दर्ज कर सकता हूं। ',
}
_SHORT_ANSWER_REASK = {
    'en': "Could you say a bit more about what you'd like to ask?",
    'hi': 'क्या आप थोड़ा और बता सकते हैं कि आप क्या पूछना चाहते हैं?',
}


def start_raise_payslip_query(request, intent_text: str, confidence: float) -> dict:
    """First turn: pulls a description out of the same utterance if one is
    there (e.g. 'raise a query about my payslip because the hra looks
    wrong'), otherwise asks for it — same shape as conversation.py's
    _start_apply_leave asking for its first missing slot."""
    description = extract_payslip_query_description(intent_text)
    if description and len(description) >= _MIN_DESCRIPTION_LENGTH:
        return _submit(request, description, confidence)

    question = text(_QUERY_QUESTION)
    if looks_like_download_request(intent_text):
        question = text(_DOWNLOAD_REDIRECT_PREFIX) + text(_QUERY_QUESTION)

    set_pending(request.user.id, INTENT_RAISE_PAYSLIP_QUERY, {})
    return _payload(INTENT_RAISE_PAYSLIP_QUERY, confidence, None, question, awaiting_input=True)


def continue_raise_payslip_query(request, pending: dict, answer_text: str) -> dict:
    answer = (answer_text or '').strip()

    if len(answer) < _MIN_DESCRIPTION_LENGTH:
        # Bad answer: re-ask, don't advance and don't fail silently — same
        # rule apply_leave's slot answers follow (slot_extractor.parse_slot_answer).
        set_pending(request.user.id, INTENT_RAISE_PAYSLIP_QUERY, {})
        return _payload(INTENT_RAISE_PAYSLIP_QUERY, None, None, text(_SHORT_ANSWER_REASK), awaiting_input=True)

    return _submit(request, answer, None)


def _submit(request, description: str, confidence: Optional[float]) -> dict:
    clear_pending(request.user.id)
    outcome = execute_intent(INTENT_RAISE_PAYSLIP_QUERY, request, slots={'description': description})
    return _payload(INTENT_RAISE_PAYSLIP_QUERY, confidence, outcome.data, outcome.message, success=outcome.success)


def start_check_employee_payslip(request, intent_text: str, confidence: float) -> dict:
    """First turn: pulls an employee name out of the utterance if one is
    there (e.g. 'check sarah khan's payslip'), then resolves it the same way
    a disambiguation retry does — mirrors conversation.py's
    _start_leave_approval/_resolve_leave_approval_target, minus the confirm
    stage (viewing isn't a mutating action — see executor_payroll.py's
    execute_identify_employee_payslip docstring)."""
    name_query = extract_employee_name_query(intent_text)
    return _resolve_check_employee_payslip(request, name_query, confidence)


def _resolve_check_employee_payslip(
    request, name_query: Optional[str], confidence: Optional[float],
) -> dict:
    outcome = execute_intent(INTENT_CHECK_EMPLOYEE_PAYSLIP, request, slots={'name_query': name_query})
    data = outcome.data or {}
    result_kind = data.get('outcome')

    if result_kind in ('need_name', 'multiple_match'):
        set_pending(request.user.id, INTENT_CHECK_EMPLOYEE_PAYSLIP, {})
        return _payload(INTENT_CHECK_EMPLOYEE_PAYSLIP, confidence, data, outcome.message, awaiting_input=True)

    # single_match is already the terminal response (payslip summary read
    # back directly — no yes/no confirmation to wait for); zero_match or a
    # permission/lookup error likewise has nothing left to continue.
    return _payload(
        INTENT_CHECK_EMPLOYEE_PAYSLIP, confidence, data or None, outcome.message,
        success=outcome.success, speech_message=outcome.speech_message,
    )


def continue_check_employee_payslip(request, pending: dict, answer_text: str) -> dict:
    # Only ever a "be more specific" retry or the first "who do you mean"
    # answer — the whole answer text IS the name this time, not a full
    # sentence to run the name-extraction regex against (mirrors
    # conversation.py's _continue_leave_approval awaiting_name branch).
    return _resolve_check_employee_payslip(request, answer_text.strip(), None)


def start_payroll_conversation(request, intent: str, intent_text: str, confidence: float) -> dict:
    """conversation.py's single call site for either payroll conversational intent's first turn."""
    if intent == INTENT_RAISE_PAYSLIP_QUERY:
        return start_raise_payslip_query(request, intent_text, confidence)
    return start_check_employee_payslip(request, intent_text, confidence)


def continue_payroll_conversation(request, pending: dict, answer_text: str) -> dict:
    """conversation.py's single call site for either payroll conversational intent's follow-up turns."""
    if pending['intent'] == INTENT_RAISE_PAYSLIP_QUERY:
        return continue_raise_payslip_query(request, pending, answer_text)
    return continue_check_employee_payslip(request, pending, answer_text)


def _payload(
    intent: str, confidence: Optional[float], result, message: str,
    awaiting_input: bool = False, success: bool = True,
    speech_message: Optional[str] = None,
) -> dict:
    """
    Small, deliberate duplicate of conversation.py's own private _payload —
    that function isn't importable here without creating a
    conversation.py <-> conversation_payroll.py circular import (conversation.py
    must import start_raise_payslip_query etc. from this module); same
    reasoning executor_result.py's docstring gives for splitting
    ExecutionResult out of executor.py. speech_message, language (Phase 3):
    see conversation.py's own _payload docstring.
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
    }
