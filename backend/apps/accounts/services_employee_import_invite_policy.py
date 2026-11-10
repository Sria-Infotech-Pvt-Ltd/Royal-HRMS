"""
Policy for the import invitation pipeline: the failure reason codes (and the plain-language text shown for them), how an error is
classified as temporary or permanent, the retry limits and the backoff. No database access here.

Reason codes are stored on the invitation row; the text is only looked up when progress is shown. An exception's own message is
never stored or logged, because it can contain an email address or server details.
"""
from __future__ import annotations

import smtplib
import socket
import ssl
from datetime import timedelta

from django.conf import settings

PROGRESS_ACTION = 'employee_bulk_import_invites'      # the old progress record; still read for batches imported before the invitation table
INVITE_TEMPLATE = 'onboarding_invite'
BACKOFF_SECONDS = (60, 300, 900)
UNQUEUED_GRACE_SECONDS = 120

REASONS = {
    'smtp_auth': 'The mail server rejected the SMTP login. An administrator must fix the SMTP settings, then use Retry.',
    'smtp_not_configured': 'No active SMTP configuration exists. An administrator must set one up, then use Retry.',
    'recipient_refused': 'The mail server refused this recipient address. Check the work email, then use Resend Invite.',
    'smtp_connection': 'The mail server could not be reached. Use Retry when it is available.',
    'smtp_timeout': 'The mail server did not answer in time. Use Retry.',
    'smtp_rejected': 'The mail server rejected the message. Use Retry or Resend Invite.',
    'unexpected': 'The activation email could not be sent. Use Resend Invite on the employee.',
    'max_attempts': 'The email still failed after the maximum number of attempts. Use Retry.',
    'duplicate_open_invite': 'Another invitation for this employee is already waiting or being sent.',
    'already_invited': 'This employee already has a valid, unused activation invitation.',
    'already_activated': 'This employee has already activated their account.',
    'employee_inactive': 'The employee account is no longer active.',
}
FAILURE_REASON = REASONS['unexpected']


class InviteSendingHeld(Exception):
    """Raised by the mail-sending function itself when bulk-import invitations are switched off (see invites_enabled)."""


def invites_enabled() -> bool:
    """The server-side switch for bulk-import invitation emails. OFF unless EMPLOYEE_IMPORT_INVITES_ENABLED is explicitly true, so a
    missing setting, a restarted worker or a Beat sweep can never send mail by accident. While it is off every invitation stays
    exactly as it is (status, attempts, tokens): nothing is queued, claimed, tokenised or emailed."""
    return bool(getattr(settings, 'EMPLOYEE_IMPORT_INVITES_ENABLED', False))


def max_attempts() -> int:
    return int(getattr(settings, 'EMPLOYEE_IMPORT_INVITE_MAX_ATTEMPTS', 4))


def stale_after() -> timedelta:
    return timedelta(seconds=int(getattr(settings, 'EMPLOYEE_IMPORT_INVITE_STALE_SECONDS', 600)))


def classify(exc: Exception) -> tuple[str, bool]:
    """(reason code, is_transient). Only recognised network/SMTP trouble is retried; anything unknown fails at once."""
    if isinstance(exc, smtplib.SMTPAuthenticationError):
        return 'smtp_auth', False
    if isinstance(exc, smtplib.SMTPRecipientsRefused):
        return 'recipient_refused', False
    if isinstance(exc, smtplib.SMTPSenderRefused):
        return 'smtp_rejected', False
    if isinstance(exc, smtplib.SMTPResponseException):
        return 'smtp_rejected', exc.smtp_code < 500                      # 4xx is a temporary refusal, 5xx is permanent
    if isinstance(exc, (socket.timeout, TimeoutError)):
        return 'smtp_timeout', True
    if isinstance(exc, (smtplib.SMTPException, ConnectionError, ssl.SSLError, OSError)):
        return 'smtp_connection', True
    if isinstance(exc, RuntimeError) and 'No active SMTP configuration' in str(exc):
        return 'smtp_not_configured', False
    return 'unexpected', False


def backoff(attempts: int) -> timedelta:
    return timedelta(seconds=BACKOFF_SECONDS[min(max(attempts, 1), len(BACKOFF_SECONDS)) - 1])
