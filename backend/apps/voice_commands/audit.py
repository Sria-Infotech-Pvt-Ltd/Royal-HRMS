"""
Wires voice_commands' security-relevant events into the app's real audit
trail (apps.accounts.models.AuditLog — the same table AuditLogListView/
the /dashboard/audit page already read for login, document, and permission-
change events across accounts/announcements/branch/hrms/recruitment) instead
of leaving them only in the standalone logs/voice_commands.log file.

Two event kinds, both called from execute_intent()/handle_transcript() —
the two choke points every voice command already passes through regardless
of which of the ~17 intents it resolves to:
  - permission_denied — execute_intent()'s registry-declared required_permission
    gate rejected the caller (see executor.py).
  - no_match          — match_intent() found nothing confident enough to act
    on, whether or not a "did you mean" candidate was offered (see
    conversation.py's handle_transcript).

No ML/anomaly-detection model for the anomaly check itself — a straightforward
count-based threshold. (Separately, voice_commands/llm_fallback.py now does
call out to an LLM, but only to classify an already-failed transcript into an
existing intent — this anomaly counter has nothing to do with that and stays
a plain threshold.) AuditLog rows (not a cache counter) are the source of
truth for the count, so it survives process restarts and naturally matches
whatever the human reviewing /dashboard/audit would see if they counted the
same rows by hand.
"""
from __future__ import annotations

import logging
from datetime import timedelta
from typing import Optional

from django.utils import timezone

from apps.accounts.models import AuditLog
from core.responses import get_client_ip

logger = logging.getLogger(__name__)

MODULE = 'voice_commands'
ACTION_PERMISSION_DENIED = 'voice_permission_denied'
ACTION_NO_MATCH = 'voice_no_match'
ACTION_UNUSUAL_ACTIVITY = 'voice_unusual_activity'
# Recorded by llm_fallback.py on every attempt at the sarvam-105b classifier —
# both a resolved intent and a rejected/no_match outcome — so actual Sarvam
# usage is visible in /dashboard/audit without waiting on a bill. Distinct
# from ACTION_NO_MATCH: that one fires once per transcript regardless of
# whether the LLM tier is even reachable; this one only fires when it
# actually ran.
ACTION_LLM_FALLBACK_USED = 'voice_llm_fallback_used'
# Fires once per STT-confirmation turn started (see
# conversation_stt_confirmation.py's start_stt_confirmation) — previously
# only reached the module's file logger, invisible to /dashboard/audit and to
# the voice_review_report management command's clarification-outcome stats.
ACTION_STT_CONFIRMATION_STARTED = 'voice_stt_confirmation_started'
# Fires once per clarification turn resolved — confirmed, declined, or
# re-asked (an unrecognized yes/no answer) — for all three clarification
# flavors this app has (rule-engine "did you mean", LLM low-confidence "did
# you mean", and STT-transcript confirmation). clarification_type distin-
# guishes which flavor; a start-with-no-matching-outcome-within-the-report-
# window is how voice_review_report infers "abandoned" — no separate event
# for that, since Redis pending state just expires silently with no eviction
# callback to hook.
ACTION_CLARIFICATION_OUTCOME = 'voice_clarification_outcome'

# Straightforward count-based threshold: this many permission-denial/no-match
# events from the SAME user inside this window is unusual enough to flag for
# a human to look at — e.g. a compromised session being probed for what it
# can do, or a script hammering the endpoint. Numbers chosen generously above
# normal usage (a genuine user fumbling a voice command a few times in a row
# is completely normal) rather than tuned against real traffic, since there's
# no real-world volume to tune against yet.
ANOMALY_THRESHOLD = 5
ANOMALY_WINDOW_MINUTES = 10
_ANOMALY_ACTIONS = (ACTION_PERMISSION_DENIED, ACTION_NO_MATCH)


def log_permission_denied(request, intent: str, required_permission: str) -> None:
    _record(request, ACTION_PERMISSION_DENIED, {
        'intent': intent, 'required_permission': required_permission,
    })


def log_no_match(
    request, transcript: str, confidence: Optional[float], candidate_intent: Optional[str],
) -> None:
    _record(request, ACTION_NO_MATCH, {
        'transcript': transcript, 'confidence': confidence, 'candidate_intent': candidate_intent,
    })


def log_llm_fallback_used(
    request, transcript: str, resolved_intent: Optional[str], confidence: Optional[float] = None,
) -> None:
    """
    Called from llm_fallback.py.try_llm_fallback on every attempt at the
    sarvam-105b classifier. resolved_intent is the intent it settled on, or
    None when the call failed outright (no key configured, network/timeout
    error, malformed response) or the model itself answered no_match/an
    intent outside the allow-list — kept in one action type rather than two
    so /dashboard/audit shows total Sarvam usage in one place; the changes
    payload's resolved_intent field distinguishes a hit from a miss.

    confidence is the model's own reported score (may be None — see
    llm_fallback.py's _parse_response). Without it, a low-confidence guess
    routed to start_clarification and a high-confidence direct dispatch were
    indistinguishable in the audit trail — both logged the same resolved_intent
    with no way to tell which path was taken.
    """
    _record(request, ACTION_LLM_FALLBACK_USED, {
        'transcript': transcript, 'resolved_intent': resolved_intent, 'confidence': confidence,
    })


def log_stt_confirmation_started(
    request, transcript: str, language_probability: Optional[float] = None,
) -> None:
    _record(request, ACTION_STT_CONFIRMATION_STARTED, {
        'transcript': transcript, 'language_probability': language_probability,
    })


def log_clarification_outcome(request, clarification_type: str, outcome: str) -> None:
    """
    clarification_type: 'rule_engine' | 'llm' | 'stt'.
    outcome: 'confirmed' | 'declined' | 're_asked'.
    """
    _record(request, ACTION_CLARIFICATION_OUTCOME, {
        'clarification_type': clarification_type, 'outcome': outcome,
    })


def _record(request, action: str, changes: dict) -> None:
    user = getattr(request, 'user', None)
    if user is None or not getattr(user, 'is_authenticated', False):
        return  # VoiceParseView is IsAuthenticated-only; defensive only.

    # Best-effort: an audit-trail write is a side effect of handling this
    # voice command, never a precondition for it. A DB hiccup (or, in tests,
    # a request double that isn't a real User instance) must not turn an
    # otherwise-normal permission-denied/no-match response into a 500 — the
    # caller still gets their answer either way.
    try:
        AuditLog.objects.create(
            user=user, action=action, module=MODULE, changes=changes,
            ip_address=get_client_ip(request),
        )
        _check_anomaly(request, user)
    except Exception:
        logger.exception(
            'Voice: failed to write audit log for action=%s user=%s', action, getattr(user, 'pk', None),
        )


def _check_anomaly(request, user) -> None:
    window_start = timezone.now() - timedelta(minutes=ANOMALY_WINDOW_MINUTES)
    count = AuditLog.objects.filter(
        user=user, module=MODULE, action__in=_ANOMALY_ACTIONS, created_at__gte=window_start,
    ).count()

    # Flag on the transition past the threshold, then again every full
    # multiple of it beyond that — one alert per burst, not silence for the
    # rest of a sustained one and not a duplicate alert per event either.
    if count < ANOMALY_THRESHOLD or count % ANOMALY_THRESHOLD != 0:
        return

    logger.warning(
        'Voice: unusual volume of permission-denial/no-match events for user=%s — '
        '%d in the last %d minute(s)',
        user.pk, count, ANOMALY_WINDOW_MINUTES,
    )
    AuditLog.objects.create(
        user=user, action=ACTION_UNUSUAL_ACTIVITY, module=MODULE,
        changes={'event_count': count, 'window_minutes': ANOMALY_WINDOW_MINUTES},
        ip_address=get_client_ip(request),
    )
