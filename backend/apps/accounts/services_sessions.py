"""Ending sessions so people pick up changed access.

Permissions are copied into the login token, so when what a position (or everyone) may do changes, the people
affected must sign in again to get the new set. Blacklisting their outstanding refresh tokens forces that: their
next request is rejected and their next login reads the current permissions.
"""
from __future__ import annotations

from datetime import date

from django.db.models import Q
from rest_framework_simplejwt.token_blacklist.models import BlacklistedToken, OutstandingToken

from apps.accounts.models import Placement, User


def force_relogin(user_ids) -> int:
    """Blacklist every outstanding token of the given users. Returns how many tokens were newly blacklisted."""
    outstanding = OutstandingToken.objects.filter(user_id__in=list(user_ids)).exclude(blacklistedtoken__isnull=False)
    created = BlacklistedToken.objects.bulk_create(
        [BlacklistedToken(token=token) for token in outstanding], ignore_conflicts=True,
    )
    return len(created)


def current_holder_ids(position) -> list:
    """Active users who hold `position` today."""
    today = date.today()
    return list(
        Placement.objects.filter(position=position, effective_from__lte=today, employee__is_active=True)
        .filter(Q(effective_to__isnull=True) | Q(effective_to__gte=today))
        .values_list('employee_id', flat=True)
    )


def active_user_ids() -> list:
    return list(User.objects.filter(is_active=True).values_list('id', flat=True))
