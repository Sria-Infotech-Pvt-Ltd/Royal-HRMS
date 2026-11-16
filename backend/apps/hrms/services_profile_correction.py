"""Validation of a profile-correction request message: "Section: <section>. Field to change: <field>. Reason: <reason>"."""
from __future__ import annotations

import logging
import re

from .profile_correction_fields import PROFILE_CORRECTION_FIELDS

logger = logging.getLogger(__name__)

MIN_REASON_LENGTH = 10
_MESSAGE_PATTERN = re.compile(r'^Section: (?P<section>.+?)\. Field to change: (?P<field>.+?)\. Reason: (?P<reason>.*)$', re.DOTALL)

MALFORMED_MESSAGE = 'Please choose a section and a field to change, and describe the reason.'


def parse_profile_correction(message: str) -> tuple[str, str, str]:
    """(section, field, reason) of an already-validated profile-correction message."""
    match = _MESSAGE_PATTERN.match(message.strip())
    if match is None:
        return '', '', ''
    return match.group('section'), match.group('field'), match.group('reason').strip()


def profile_correction_problem(message: str) -> str | None:
    """Why `message` is not an acceptable profile-correction request, or None when it is."""
    match = _MESSAGE_PATTERN.match(message.strip())
    if match is None:
        logger.warning('Profile correction rejected: message does not follow the Section/Field/Reason format.')
        return MALFORMED_MESSAGE
    section, field, reason = match.group('section'), match.group('field'), match.group('reason').strip()
    allowed_fields = PROFILE_CORRECTION_FIELDS.get(section)
    if allowed_fields is None:
        logger.warning('Profile correction rejected: unknown section %r.', section)
        return 'Please choose a valid section.'
    if field not in allowed_fields:
        logger.warning('Profile correction rejected: field %r does not belong to section %r.', field, section)
        return 'Please choose a field that belongs to the selected section.'
    if len(reason) < MIN_REASON_LENGTH:
        return f'Please describe the reason in at least {MIN_REASON_LENGTH} characters.'
    return None
