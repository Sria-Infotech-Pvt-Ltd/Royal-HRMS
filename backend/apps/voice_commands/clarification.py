from __future__ import annotations

from typing import Optional

from django.core.cache import cache

# Backed by Django's cache framework — django-redis in any environment with
# REDIS_URL set (config/settings.py:114-135), LocMemCache otherwise. Redis
# expires the key on its own; no cleanup job needed.
PENDING_TIMEOUT_SECONDS = 120


def _cache_key(user_id) -> str:
    return f'voice:pending:{user_id}'


def get_pending(user_id) -> Optional[dict]:
    """
    Return {'intent': str, 'slots': dict} for user_id, or None if nothing is
    pending / it expired.

    Sliding window: merely reading an active pending state resets its TTL to
    the full 120s, on top of the reset set_pending() already does on every
    write. Without this, the clock set when the previous turn's response was
    sent keeps running through however long TTS narration and panel
    rendering take client-side before the user even starts speaking again —
    a conversation should stay alive for as long as the user keeps actively
    answering, not get cut short by client-side playback time eating into
    the window.
    """
    key = _cache_key(user_id)
    pending = cache.get(key)
    if pending is not None:
        cache.touch(key, PENDING_TIMEOUT_SECONDS)
    return pending


def set_pending(user_id, intent: str, slots: dict) -> None:
    cache.set(_cache_key(user_id), {'intent': intent, 'slots': slots}, timeout=PENDING_TIMEOUT_SECONDS)


def clear_pending(user_id) -> None:
    cache.delete(_cache_key(user_id))
