"""
Read-only consistency check of each leave policy: the configured values next to the note employees are shown, with likely
contradictions flagged (a note promising carry-forward while carry-forward is off, "up to 180 days" against 90 configured, ...).

It never changes a value: HR decides which side is right. The checks are plain-language heuristics, so a flag means "look at this",
not "this is wrong".
"""
from __future__ import annotations

import re

_NUMBER = r'(\d+(?:\.\d+)?)'


def policy_values(policy) -> dict:
    """The configuration HR should compare with the note."""
    return {
        'annual_days': float(policy.annual_days or 0),
        'can_carry_forward': bool(policy.can_carry_forward),
        'max_carry_forward_days': float(policy.max_carry_forward_days or 0),
        'maximum_consecutive_days': policy.maximum_consecutive_days or 0,
        'minimum_notice_period': policy.minimum_notice_period or 0,
        'attachment_required': bool(policy.attachment_required),
        'applicable_gender': policy.applicable_gender,
        'allow_probation_leave': bool(policy.allow_probation_leave),
    }


def find_mismatches(policy) -> list[str]:
    """Plain-language reasons the note and the configuration may disagree (empty when nothing looks off)."""
    note = (policy.policy_note or '').lower()
    values = policy_values(policy)
    found: list[str] = []
    if not note:
        return found

    says_no_carry = re.search(r'no carry[- ]?forward|not carry', note)
    if re.search(r'carry[- ]?forward', note) and not says_no_carry and not values['can_carry_forward']:
        found.append('The note mentions carry-forward but carry-forward is switched off.')
    carry_limit = re.search(r'carry[- ]?forward[^.]*?(?:up to|max(?:imum)?)\s*' + _NUMBER + r'\s*days', note)
    if carry_limit and values['can_carry_forward'] and float(carry_limit.group(1)) != values['max_carry_forward_days']:
        found.append(f'The note allows carry-forward up to {carry_limit.group(1)} days; configured maximum is {values["max_carry_forward_days"]:g}.')

    entitlement = re.search(r'up to\s*' + _NUMBER + r'\s*days', note)
    if entitlement and 'carry' not in note[max(0, entitlement.start() - 25):entitlement.start()]:
        if float(entitlement.group(1)) != values['annual_days']:
            found.append(f'The note says up to {entitlement.group(1)} days; the entitlement is configured as {values["annual_days"]:g}.')

    consecutive = re.search(r'max(?:imum)?\s*' + _NUMBER + r'\s*consecutive', note)
    if consecutive and float(consecutive.group(1)) != values['maximum_consecutive_days']:
        found.append(f'The note limits a request to {consecutive.group(1)} consecutive days; configured limit is {values["maximum_consecutive_days"]} (0 = none).')

    asks_notice = re.search(r'days?\s*(?:in advance|advance|notice)|notice', note) and re.search(r'\d', note)
    if asks_notice and values['minimum_notice_period'] == 0:
        found.append('The note asks for advance notice but the minimum notice period is 0.')

    if re.search(r'certificate|attachment|document', note) and not values['attachment_required']:
        found.append('The note mentions a certificate/document but attachment is not required.')
    return found


def build_policy_report(policies) -> list[dict]:
    return [
        {'leave_type': policy.leave_type, 'note': policy.policy_note or '', 'values': policy_values(policy), 'mismatches': find_mismatches(policy)}
        for policy in policies
    ]
