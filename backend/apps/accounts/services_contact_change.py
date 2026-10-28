"""
HR corrections of an employee's mobile number and personal email after hire.

Validation matches the hire wizard (email format, 10-digit Indian mobile starting 6-9) and adds a uniqueness check
against every other employee. In this system the personal email captured at hire IS the login email (User.email), so
changing it changes how the employee signs in: it is only applied when HR confirms that explicitly, and the employee is
told by email at both the old and the new address.
"""
from __future__ import annotations

import logging
import re

from django.core.exceptions import ValidationError as DjangoValidationError
from django.core.validators import validate_email

from apps.accounts.models import Company, EmployeeProfile, User
from apps.accounts.utils import send_template_email

logger = logging.getLogger(__name__)

LOGIN_EMAIL_CHANGED_TEMPLATE = 'login_email_changed'
_FORMAT_CHARS_RE = re.compile(r'[\s\-()./]')
_INDIAN_MOBILE_RE = re.compile(r'^(?:\+?91)?([6-9]\d{9})$')


class ContactChangeError(Exception):
    """A rejected contact edit; `field` is the request key the message belongs next to."""

    def __init__(self, field: str, message: str):
        super().__init__(message)
        self.field = field
        self.message = message


def normalise_mobile(raw: str) -> str:
    """'+91 98765 43210' / '9876543210' -> '9876543210'. Blank is rejected: a hired employee always has a mobile."""
    cleaned = _FORMAT_CHARS_RE.sub('', (raw or '').strip())
    match = _INDIAN_MOBILE_RE.match(cleaned)
    if not match:
        raise ContactChangeError('phone', 'Enter a valid 10-digit Indian mobile number (it must start with 6, 7, 8 or 9).')
    return match.group(1)


def _last_ten_digits(raw: str) -> str:
    return re.sub(r'\D', '', raw or '')[-10:]


def is_mobile_changed(employee: User, raw: str) -> bool:
    """False when the request just echoes the stored number (maybe formatted differently), so an untouched field is never re-validated."""
    return _last_ten_digits(raw) != _last_ten_digits(employee.phone) or not (raw or '').strip()


def is_truthy(raw) -> bool:
    return raw is True or str(raw).strip().lower() in ('true', '1', 'yes')


def check_mobile_unique(employee: User, mobile: str) -> None:
    wanted = _last_ten_digits(mobile)
    others = User.objects.exclude(pk=employee.pk).exclude(phone='').values_list('phone', flat=True)
    if any(_last_ten_digits(phone) == wanted for phone in others):
        raise ContactChangeError('phone', 'This mobile number is already used by another employee.')


def normalise_email(raw: str) -> str:
    email = (raw or '').strip().lower()
    try:
        validate_email(email)
    except DjangoValidationError:
        raise ContactChangeError('email', 'Enter a valid email address.') from None
    return email


def check_email_unique(employee: User, email: str) -> None:
    used_as_login = User.objects.filter(email__iexact=email).exclude(pk=employee.pk).exists()
    used_as_personal = EmployeeProfile.objects.filter(personal_email__iexact=email).exclude(user=employee).exists()
    if used_as_login or used_as_personal:
        raise ContactChangeError('email', 'This email is already used by another employee.')


def require_login_email_confirmation(old_email: str, new_email: str, is_confirmed: bool) -> None:
    if is_confirmed:
        return
    raise ContactChangeError(
        'email',
        f'This email is also the employee\'s login. Changing it from {old_email} to {new_email} changes how they sign in. '
        'Confirm the change to continue; the employee will be notified at both addresses.',
    )


def invalidate_old_email_access(employee: User) -> dict:
    """Ends what the old login address could still do: every signed-in session (all refresh tokens), and any password-reset or
    activation link and one-time code that was sent to it. Expired, not deleted, so the records stay (invite status shows Expired)."""
    from django.utils import timezone

    from apps.accounts.models import OTPVerification, PasswordResetToken
    from apps.accounts.services_sessions import force_relogin

    now = timezone.now()
    sessions = force_relogin([employee.pk])
    links = PasswordResetToken.objects.filter(user=employee, is_used=False, expires_at__gt=now).update(expires_at=now)
    codes = OTPVerification.objects.filter(user=employee, is_used=False, expires_at__gt=now).update(expires_at=now)
    return {'sessions_ended': sessions, 'reset_links_expired': links, 'codes_expired': codes}


def notify_login_email_changed(employee: User, old_email: str, new_email: str, actor: User) -> bool:
    """Tells the employee at the old and the new address. True only when both emails went out."""
    company = Company.objects.first()
    context = {
        'employee_name': employee.full_name or new_email,
        'old_email': old_email,
        'new_email': new_email,
        'company_name': company.company_name if company else '',
    }
    is_all_sent = True
    for recipient in (old_email, new_email):
        try:
            send_template_email(
                recipient_email=recipient, template_name=LOGIN_EMAIL_CHANGED_TEMPLATE, context=context,
                module='accounts', triggered_by=actor,
            )
        except Exception as exc:
            is_all_sent = False
            logger.error('Login-email-change notice for employee %s failed: %s', employee.employee_id, exc)
    return is_all_sent
