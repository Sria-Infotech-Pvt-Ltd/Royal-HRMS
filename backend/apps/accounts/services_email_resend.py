"""Which logged emails may be replayed from Email Logs, and what to tell the user when one may not.

Email Logs -> Resend re-sends the saved copy of an email word for word. That is wrong for an email whose whole point is a one-time
link: the saved copy holds the ORIGINAL link, which has expired (an invitation lasts INVITE_VALIDITY_HOURS) or was cancelled when a
newer one was issued, so the person receives a mail that says "expired". Those emails must be re-issued by the action that created
them, which makes a fresh link. An invitation is re-issued for the person by the Email Logs Resend button itself (see
EmailLogResendView); a password reset and any other credential email must still be re-issued from where they were made.
"""
from __future__ import annotations

from typing import Optional

INVITE_TEMPLATE = 'onboarding_invite'
ADMIN_RESET_TEMPLATE = 'password_reset_by_admin'

_GENERIC_SENSITIVE = (
    'This email contained a one-time credential and cannot be resent generically for security reasons. Use the dedicated resend '
    'action in its originating module (for example Recruitment, Candidate, Resend Portal Invite), which issues a fresh credential.'
)


def resend_blocked_reason(template_name: str, has_sensitive_context: bool) -> Optional[str]:
    """Why this logged email cannot be replayed from Email Logs, or None when Resend works (a plain replay, or a fresh invitation)."""
    if template_name == INVITE_TEMPLATE:
        return None
    if template_name == ADMIN_RESET_TEMPLATE:
        return (
            'This email contains a one-time password-reset link that expires. Use "Reset password" on the employee again '
            'instead: it sends a fresh link.'
        )
    if has_sensitive_context:
        return _GENERIC_SENSITIVE
    return None
