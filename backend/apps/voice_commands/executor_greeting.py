from __future__ import annotations

from django.utils import timezone

from apps.voice_commands.executor_result import ExecutionResult
from apps.voice_commands.language import text

# Distinct from VoiceConversationPanel's static "Hi, how can I help you?"
# placeholder (frontend/components/VoiceConversationPanel.tsx's
# GREETING_MESSAGE) — that text is shown before any transcript exists and
# never reaches this module. execute_greeting() only runs once a real
# transcript has matched registry/intents_en.yaml's greeting intent through
# /api/voice/parse/ — a real, personalized response, not frontend UI chrome.

# Keyed by _time_of_day()'s own English return value — never shown directly,
# only used to look up the Hindi word before .format() runs (see
# execute_greeting: {time_of_day} is a single, already-localized placeholder
# shared by both templates, same reasoning executor_approval.py's
# _WHO_TO_ACTION_TEMPLATE gives for its own single `{action}` placeholder).
_TIME_OF_DAY_HI = {'morning': 'सुबह', 'afternoon': 'दोपहर', 'evening': 'शाम'}
_GREETING_TEMPLATE = {
    'en': 'Hi, {display_name}, good {time_of_day}! How can I help you today?',
    'hi': 'नमस्ते {display_name}, शुभ {time_of_day}! आज मैं आपकी कैसे मदद कर सकता हूं?',
}


def _time_of_day() -> str:
    """
    Same hour bucketing as dashboard/views/manager.py's _greeting() (kept as
    a separate copy rather than importing that module-private helper across
    an app boundary). Computed from the actual server clock — never parsed
    out of the transcript — so "hi", "hey", and "good morning" all produce
    the same, correctly time-appropriate greeting. Always returns the
    English word — _GREETING_TEMPLATE's Hindi side looks it up in
    _TIME_OF_DAY_HI rather than this function returning a language-specific
    value itself, so this stays a plain, single-purpose hour bucketer.
    """
    hour = timezone.localtime().hour
    if hour < 12:
        return 'morning'
    if hour < 17:
        return 'afternoon'
    return 'evening'


def execute_greeting(request) -> ExecutionResult:
    """
    Single-turn — no slots, no permission beyond IsAuthenticated (already
    enforced by VoiceParseView). display_name reuses the exact same source as
    the dashboard's "Welcome back, {name}" banner: User.full_name (see
    frontend/app/login/page.tsx's user.full_name, populated from
    accounts.models.User.full_name), falling back to email the same way
    dashboard/views/manager.py's manager_name does — never a different field.
    """
    display_name = request.user.full_name or request.user.email
    time_of_day = _time_of_day()
    localized_time_of_day = text({'en': time_of_day, 'hi': _TIME_OF_DAY_HI[time_of_day]})
    message = text(_GREETING_TEMPLATE).format(display_name=display_name, time_of_day=localized_time_of_day)
    return ExecutionResult(success=True, message=message)
