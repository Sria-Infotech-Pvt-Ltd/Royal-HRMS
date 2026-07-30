from __future__ import annotations

from django.utils import timezone

from apps.voice_commands.executor_result import ExecutionResult

# Distinct from VoiceConversationPanel's static "Hi, how can I help you?"
# placeholder (frontend/components/VoiceConversationPanel.tsx's
# GREETING_MESSAGE) — that text is shown before any transcript exists and
# never reaches this module. execute_greeting() only runs once a real
# transcript has matched registry/intents_en.yaml's greeting intent through
# /api/voice/parse/ — a real, personalized response, not frontend UI chrome.


def _time_of_day() -> str:
    """
    Same hour bucketing as dashboard/views/manager.py's _greeting() (kept as
    a separate copy rather than importing that module-private helper across
    an app boundary). Computed from the actual server clock — never parsed
    out of the transcript — so "hi", "hey", and "good morning" all produce
    the same, correctly time-appropriate greeting.
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
    message = f'Hi, {display_name}, good {_time_of_day()}! How can I help you today?'
    return ExecutionResult(success=True, message=message)
