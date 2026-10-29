"""
New-hire onboarding lifecycle: the Onboarding status, its history timeline, and the invite email's send/resend rules.

An employee is "Onboarding" from the moment HR sends the invite (`User.activation_pending`) until they have BOTH set their
password and logged in once; at that point the flag clears by itself and an `activated` event is written. Every step is an
`OnboardingEvent`, so the admin panel can show exactly what happened and when.
"""
from __future__ import annotations

import logging
from datetime import timedelta

from django.conf import settings
from django.db.models import Q
from django.utils import timezone

from apps.accounts.models import OnboardingEvent, PasswordResetToken, User

logger = logging.getLogger(__name__)

# Resends allowed per employee per rolling hour; override with ONBOARDING_RESEND_MAX_PER_HOUR in settings.
DEFAULT_RESEND_MAX_PER_HOUR = 5
_FAILURE_REASON_MAX = 300


class ResendLimitError(Exception):
    """Too many resends in the last hour."""


def resend_limit_per_hour() -> int:
    return int(getattr(settings, 'ONBOARDING_RESEND_MAX_PER_HOUR', DEFAULT_RESEND_MAX_PER_HOUR))


def is_onboarding(user: User) -> bool:
    """The single definition of the Onboarding status for an active record."""
    return user.onboarding_status != User.ONBOARDING_COMPLETE or user.activation_pending


def onboarding_q() -> Q:
    return ~Q(onboarding_status=User.ONBOARDING_COMPLETE) | Q(activation_pending=True)


def fully_onboarded_q() -> Q:
    return Q(onboarding_status=User.ONBOARDING_COMPLETE, activation_pending=False)


def record_event(user: User, event: str, *, actor: User | None = None, detail: str = '') -> OnboardingEvent:
    return OnboardingEvent.objects.create(employee=user, event=event, actor=actor, detail=(detail or '')[:500])


def _has_event(user: User, event: str) -> bool:
    return OnboardingEvent.objects.filter(employee=user, event=event).exists()


def _maybe_activate(user: User) -> bool:
    """Flip to Active once the password has been set and a first login has happened. Safe to call repeatedly."""
    if not user.activation_pending:
        return False
    if not (_has_event(user, OnboardingEvent.PASSWORD_SET) and _has_event(user, OnboardingEvent.FIRST_LOGIN)):
        return False
    User.objects.filter(pk=user.pk).update(activation_pending=False)
    user.activation_pending = False
    record_event(user, OnboardingEvent.ACTIVATED, detail='Password set and first login completed.')
    return True


def on_password_set(user: User) -> None:
    if not user.activation_pending or _has_event(user, OnboardingEvent.PASSWORD_SET):
        return
    record_event(user, OnboardingEvent.PASSWORD_SET)
    _maybe_activate(user)


def on_first_login(user: User) -> None:
    if not user.activation_pending or _has_event(user, OnboardingEvent.FIRST_LOGIN):
        return
    record_event(user, OnboardingEvent.FIRST_LOGIN)
    _maybe_activate(user)


def on_link_opened(user: User) -> None:
    if user.activation_pending and not _has_event(user, OnboardingEvent.LINK_OPENED):
        record_event(user, OnboardingEvent.LINK_OPENED)


def _failure_reason(exc: Exception) -> str:
    text = str(exc).strip() or exc.__class__.__name__
    return text[:_FAILURE_REASON_MAX]


def send_onboarding_email(user: User, *, actor: User | None, is_resend: bool = False, extra_html: str = '') -> bool:
    """Send (or resend) the activation invite and record the outcome. Returns True when the email left the server."""
    from apps.accounts.utils import send_activation_invite

    if is_resend:
        since = timezone.now() - timedelta(hours=1)
        recent = OnboardingEvent.objects.filter(
            employee=user, event=OnboardingEvent.EMAIL_RESENT, created_at__gte=since,
        ).count()
        if recent >= resend_limit_per_hour():
            raise ResendLimitError(
                f'The onboarding email was already resent {recent} times in the last hour. Try again later.'
            )
    try:
        send_activation_invite(user, created_by=actor, extra_html=extra_html)
    except Exception as exc:
        logger.exception('Onboarding email failed for employee %s', user.pk)
        record_event(user, OnboardingEvent.EMAIL_FAILED, actor=actor, detail=_failure_reason(exc))
        return False
    record_event(
        user, OnboardingEvent.EMAIL_RESENT if is_resend else OnboardingEvent.EMAIL_SENT,
        actor=actor, detail=f'Sent to {user.email}.',
    )
    return True


def start_onboarding(user: User, *, actor: User | None, extra_html: str = '') -> bool:
    """Called when HR completes a hire: mark the person Onboarding, log it, and send the invite."""
    User.objects.filter(pk=user.pk).update(activation_pending=True)
    user.activation_pending = True
    record_event(user, OnboardingEvent.INITIATED, actor=actor)
    return send_onboarding_email(user, actor=actor, extra_html=extra_html)


def latest_invite(user: User) -> PasswordResetToken | None:
    return PasswordResetToken.objects.filter(
        user=user, purpose=PasswordResetToken.PURPOSE_INVITE,
    ).order_by('-created_at').first()


def current_state(user: User) -> dict:
    """One plain-language line for the panel header, plus whether a resend makes sense right now."""
    if not user.activation_pending:
        return {'code': 'active', 'message': 'This employee has completed onboarding.', 'can_resend': False}
    last_email = OnboardingEvent.objects.filter(
        employee=user, event__in=[OnboardingEvent.EMAIL_SENT, OnboardingEvent.EMAIL_RESENT, OnboardingEvent.EMAIL_FAILED],
    ).order_by('-created_at').first()
    if last_email is None or last_email.event == OnboardingEvent.EMAIL_FAILED:
        return {'code': 'email_failed', 'message': 'Onboarding email failed. Please resend.', 'can_resend': True}
    invite = latest_invite(user)
    if invite is not None and invite.status == PasswordResetToken.STATUS_EXPIRED:
        return {'code': 'link_expired', 'message': 'Link expired. Please resend the onboarding email.', 'can_resend': True}
    if invite is not None and invite.is_used:
        return {'code': 'awaiting_login', 'message': 'Password is set. Waiting for the first login.', 'can_resend': False}
    if invite is not None and invite.opened_at:
        return {'code': 'link_opened', 'message': 'User opened the link but has not set a password yet.', 'can_resend': True}
    return {'code': 'not_logged_in', 'message': 'User has not logged in yet.', 'can_resend': True}


def timeline(user: User) -> list[dict]:
    return [
        {
            'id': str(item.id), 'event': item.event, 'label': item.get_event_display(), 'at': item.created_at,
            'actor_name': (item.actor.full_name or item.actor.email) if item.actor else None, 'detail': item.detail,
        }
        for item in OnboardingEvent.objects.filter(employee=user).select_related('actor').order_by('created_at')
    ]
