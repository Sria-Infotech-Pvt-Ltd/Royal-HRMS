"""
The candidate's password-less onboarding link (recruitment path).

When HR sends a selected candidate the onboarding wizard, the candidate gets ONE link. Opening it starts a limited session
that can fill in the onboarding form and upload documents, nothing else (the onboarding gate keeps every employee screen
closed). The link:

  - is single use: opening it consumes it (HR can send a fresh one, which cancels any older one);
  - expires (ONBOARDING_LINK_VALIDITY_HOURS, default 7 days);
  - never carries a password, and it neither creates nor activates an employee account. The employee account is activated
    only by the separate activation link (services_onboarding.start_onboarding), sent after HR approves the submission.
"""
from __future__ import annotations

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from apps.accounts.models import Company, PasswordResetToken, User

DEFAULT_VALIDITY_HOURS = 168


def link_validity_hours() -> float:
    return float(getattr(settings, 'ONBOARDING_LINK_VALIDITY_HOURS', DEFAULT_VALIDITY_HOURS))


def issue_onboarding_link(user: User) -> tuple[PasswordResetToken, str]:
    """A fresh link for `user` (any older unused one stops working). Returns (token, url)."""
    token = PasswordResetToken.create_for_user(user, purpose=PasswordResetToken.PURPOSE_ONBOARDING, validity_hours=link_validity_hours())
    company = Company.objects.first()
    base = ((company.portal_url if company else '') or '').rstrip('/')
    return token, f'{base}/onboarding/start/{token.id}/'


def expiry_label(token: PasswordResetToken) -> str:
    return timezone.localtime(token.expires_at).strftime('%d %b %Y, %I:%M %p')


class LinkRefused(Exception):
    """The link cannot be used; `message` is safe to show the candidate."""

    def __init__(self, message: str, http_status: int = 410):
        super().__init__(message)
        self.message, self.http_status = message, http_status


def consume_onboarding_link(token_id) -> User:
    """Validate and consume a link, returning the candidate it belongs to. Raises LinkRefused otherwise.

    The consume step is one conditional UPDATE, so two simultaneous opens cannot both win.
    """
    try:
        token = PasswordResetToken.objects.select_related('user').filter(id=token_id, purpose=PasswordResetToken.PURPOSE_ONBOARDING).first()
    except (ValidationError, ValueError):   # not even shaped like a link
        token = None
    if token is None:
        raise LinkRefused('This onboarding link is invalid.', 404)
    if not token.is_valid():
        raise LinkRefused('This onboarding link has expired or was already used. Ask HR to send you a new one.')
    user = token.user
    if not user.is_active or not user.requires_self_service_onboarding:
        raise LinkRefused('This onboarding link is no longer valid. Contact HR.')
    if user.onboarding_status == User.ONBOARDING_COMPLETE:
        raise LinkRefused('Your onboarding has already been approved. Use the activation link in your email to set your password.')
    with transaction.atomic():
        won = PasswordResetToken.objects.filter(pk=token.pk, is_used=False, expires_at__gt=timezone.now()).update(
            is_used=True, opened_at=timezone.now(),
        )
        if not won:
            raise LinkRefused('This onboarding link has expired or was already used. Ask HR to send you a new one.')
    return user

