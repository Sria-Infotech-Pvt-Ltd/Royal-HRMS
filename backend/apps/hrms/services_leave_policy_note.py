"""
Keeps the numbers written in a leave policy's note in step with the settings the server really uses.

The Leave Types screen shows each policy's free-text note ("Max 3 consecutive days. Apply 1 day in advance."). The real limits live in separate
settings (Leave Policy tab). Before this, changing the setting to 5 left the note saying 3. When a setting changes, the number in the matching
phrase of the note is now rewritten; everything else HR typed is left alone. Only these phrases are recognised, so a note that mentions a
number for another reason ("Within 15 days of child's birth") is never touched:

    "Max N consecutive days"          <- maximum consecutive days
    "Apply N day(s) in advance"       <- minimum notice period
    "Min N days notice"               <- minimum notice period
    "carry-forward up to N days"      <- maximum carry-forward days (only while carry-forward is on)
"""
from __future__ import annotations

import re

_NUMBER = r'(\d+(?:\.\d+)?)'
_CONSECUTIVE = re.compile(r'(max(?:imum)?\s*)' + _NUMBER + r'(\s*consecutive\s*)(days?)', re.IGNORECASE)
_ADVANCE = re.compile(r'(apply\s*)' + _NUMBER + r'(\s*)(days?)(\s*(?:in\s*)?advance)', re.IGNORECASE)
_NOTICE = re.compile(r'(min(?:imum)?\s*)' + _NUMBER + r'(\s*)(days?)(\s*notice)', re.IGNORECASE)
_CARRY = re.compile(r'(carry[- ]?forward[^.]*?(?:up to|max(?:imum)?)\s*)' + _NUMBER + r'(\s*)(days?)', re.IGNORECASE)

# Which setting each phrase follows; used to rewrite only the phrases whose setting just changed.
CONSECUTIVE, NOTICE, CARRY_FORWARD = 'consecutive', 'notice', 'carry_forward'
ALL_SETTINGS = frozenset({CONSECUTIVE, NOTICE, CARRY_FORWARD})


def _format(value) -> str:
    number = float(value)
    return str(int(number)) if number == int(number) else f'{number:g}'


def _replacer(value):
    """A re.sub callback writing `value` as the number, with "day" / "days" to match."""
    def replace(match: re.Match) -> str:
        groups = list(match.groups())
        # group layout: prefix, number, gap, noun[, suffix] — "consecutive" has its own gap before the noun
        noun_index = 3
        groups[1] = _format(value)
        groups[noun_index] = 'day' if float(value) == 1 else 'days'
        return ''.join(groups)
    return replace


def sync_note_numbers(
    note: str, *, maximum_consecutive_days: int, minimum_notice_period: int, can_carry_forward: bool,
    max_carry_forward_days, only=ALL_SETTINGS,
) -> str:
    """`note` with the numbers of the recognised phrases set to the given settings. A setting of 0 / switched off leaves its phrase as written
    (the Leave Policy report flags that disagreement; there is no honest number to write)."""
    if not note:
        return note
    if CONSECUTIVE in only and maximum_consecutive_days and maximum_consecutive_days > 0:
        note = _CONSECUTIVE.sub(_replacer(maximum_consecutive_days), note)
    if NOTICE in only and minimum_notice_period and minimum_notice_period > 0:
        note = _ADVANCE.sub(_replacer(minimum_notice_period), note)
        note = _NOTICE.sub(_replacer(minimum_notice_period), note)
    if CARRY_FORWARD in only and can_carry_forward and max_carry_forward_days and float(max_carry_forward_days) > 0:
        note = _CARRY.sub(_replacer(max_carry_forward_days), note)
    return note


def sync_policy_note(policy, *, only=ALL_SETTINGS) -> bool:
    """Update `policy.policy_note` in memory from the policy's own settings. Returns True when the note changed."""
    updated = sync_note_numbers(
        policy.policy_note or '',
        maximum_consecutive_days=policy.maximum_consecutive_days or 0,
        minimum_notice_period=policy.minimum_notice_period or 0,
        can_carry_forward=bool(policy.can_carry_forward),
        max_carry_forward_days=policy.max_carry_forward_days or 0,
        only=only,
    )
    changed = updated != (policy.policy_note or '')
    if changed:
        policy.policy_note = updated
    return changed
