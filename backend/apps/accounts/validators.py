"""Validators shared by every place that takes a person's mobile number, so the same rule applies on every screen."""
from __future__ import annotations

from rest_framework import serializers

from apps.accounts.services_contact_change import ContactChangeError, normalise_mobile


def validate_mobile_number(value: str) -> str:
    """The one mobile rule: a 10-digit Indian number starting 6-9, optional +91/91 prefix, spaces/dashes allowed.

    Returns it normalised (just the 10 digits); blank stays blank (an optional field). Raises a serializer ValidationError whose
    message is already friendly (the field name is added by the caller's envelope, never by this text)."""
    value = (value or '').strip()
    if not value:
        return value
    try:
        return normalise_mobile(value)
    except ContactChangeError as exc:
        raise serializers.ValidationError(exc.message) from None
