from __future__ import annotations

import logging
import re
import secrets
import string
from datetime import date, datetime

from django.conf import settings
from django.core.mail import EmailMultiAlternatives, get_connection

logger = logging.getLogger(__name__)

_OTP_ALPHABET: str = string.digits


# ─── Financial Year helpers ───────────────────────────────────────────────────

def get_fy_start_year(today: date, start_month_name: str) -> int:
    """Return the calendar year in which the current financial year started.

    If today is on or after the configured start month, the FY started this
    calendar year.  Otherwise it started last calendar year.
    """
    start_month = datetime.strptime(start_month_name, '%B').month
    return today.year if today.month >= start_month else today.year - 1


def _fy_label(start_year: int) -> str:
    return f'FY {start_year}-{str(start_year + 1)[2:]}'


def get_financial_years(today: date, start_month_name: str) -> dict:
    """Return previous, current, and next FY display strings."""
    current_start = get_fy_start_year(today, start_month_name)
    return {
        'previous_financial_year': _fy_label(current_start - 1),
        'current_financial_year':  _fy_label(current_start),
        'next_financial_year':     _fy_label(current_start + 1),
    }


def get_company_financial_year_config() -> dict:
    """Return the company FY configuration dict, reading from cache when warm."""
    from core.cache_service import FinancialYearCacheService
    cached = FinancialYearCacheService.get()
    if cached is not None:
        return cached
    from apps.accounts.models import Company
    company = Company.objects.first()
    start_month = company.financial_year_start_month if company else 'April'
    today = date.today()
    data = {
        'financial_year_start_month': start_month,
        **get_financial_years(today, start_month),
    }
    FinancialYearCacheService.set(data)
    return data


# ─── OTP ─────────────────────────────────────────────────────────────────────

def generate_otp(length: int = 6) -> str:
    """Return a cryptographically secure numeric OTP string."""
    return ''.join(secrets.choice(_OTP_ALPHABET) for _ in range(length))


# ─── SMTP connection ──────────────────────────────────────────────────────────

def _get_smtp_connection() -> tuple[object, str]:
    """Return (connection, from_email) using the active SMTPSettings row.

    Raises RuntimeError if no active config exists — callers must handle this
    and return an appropriate error to the user.
    """
    from apps.accounts.models import SMTPSettings  # avoid circular import

    smtp = SMTPSettings.get_active()
    if not smtp:
        raise RuntimeError(
            'No active SMTP configuration found. '
            'Add and activate one in Settings → SMTP.'
        )
    connection = get_connection(
        backend='django.core.mail.backends.smtp.EmailBackend',
        host=smtp.host,
        port=smtp.port,
        username=smtp.username,
        password=smtp.password,
        use_tls=smtp.use_tls,
        fail_silently=False,
    )
    from_email = (
        f'{smtp.sender_name} <{smtp.from_email}>'
        if smtp.sender_name
        else smtp.from_email
    )
    return connection, from_email


# ─── Email helpers ────────────────────────────────────────────────────────────

def _html_to_text(html: str) -> str:
    """
    Plain-text MIME alternative for _build_message(). Block-level tags are
    turned into a newline BEFORE the remaining tags are stripped — without
    this, two elements with no literal whitespace between them in the
    source (e.g. '...{temp_password}<br><strong>Login URL:</strong>...',
    the exact shape of the credential-email bodies below) collapse into one
    fused word once tags are removed with no replacement. That silently
    glued a temporary password directly onto the word "Login" in the
    plain-text part of every credential email — invisible in the HTML
    rendering most clients show, but corrupting the password for anyone
    whose mail client/gateway renders or copies from the plain-text part
    instead (plain-text-preference settings, some corporate gateways,
    screen readers) — producing "Invalid credentials" on an apparently
    correct copy-paste.
    """
    text = re.sub(r'<\s*(br)\s*/?\s*>', '\n', html, flags=re.IGNORECASE)
    text = re.sub(r'<\s*/\s*(p|div|tr|li|h[1-6])\s*>', '\n', text, flags=re.IGNORECASE)
    text = re.sub(r'<[^>]+>', '', text)
    # Collapse the blank-line runs paragraph tags produce, and any trailing
    # per-line whitespace left over from a stripped tag.
    text = re.sub(r'[ \t]+(\n)', r'\1', text)
    text = re.sub(r'\n{3,}', '\n\n', text)
    return text.strip()


def _build_message(
    subject: str,
    html_body: str,
    from_email: str,
    to: list[str],
    connection: object | None = None,
) -> EmailMultiAlternatives:
    
    msg = EmailMultiAlternatives(
        subject=subject,
        body=_html_to_text(html_body),
        from_email=from_email,
        to=to,
        connection=connection,
    )
    msg.attach_alternative(html_body, 'text/html')
    return msg


# ─── Public send functions ────────────────────────────────────────────────────

def send_otp_email(email: str, otp: str, full_name: str) -> None:

    connection, from_email = _get_smtp_connection()
    expiry  = getattr(settings, 'OTP_EXPIRY_MINUTES', 10)
    branding = _get_company_branding()
    company_name = branding[0] or 'Royal HRMS'

    html_body = (
        f'<p>Hi <strong>{full_name}</strong>,</p>'
        f'<p>Your OTP to reset your {company_name} password is:</p>'
        f'<p style="font-size:32px;font-weight:bold;letter-spacing:8px;'
        f'color:#4f46e5;text-align:center;padding:20px 0;'
        f'border:2px dashed #c7d2fe;border-radius:8px;">{otp}</p>'
        f'<p>This OTP is valid for <strong>{expiry} minute(s)</strong>. '
        f'<span style="color:#dc2626;font-weight:bold;">Do not share it with anyone.</span></p>'
        f'<p>If you did not request this reset, please ignore this email or '
        f'contact your system administrator immediately.</p>'
        f'<p style="margin-top:32px;">Regards,<br>'
        f'<strong>HR Team</strong><br>{company_name}</p>'
    )
    html_body = _company_email_wrapper(html_body, *branding)

    msg = _build_message(
        subject=f'Your {company_name} Password Reset OTP',
        html_body=html_body,
        from_email=from_email,
        to=[email],
        connection=connection,
    )
    msg.send(fail_silently=False)


def send_employee_welcome_email(user, temp_password: str) -> bool:
    """
    Sends the "your account is ready" credentials email for a newly created
    employee — the exact HTML/subject/company-branding
    EmployeeListCreateView.post() has always built inline, factored out here
    so EmployeeBulkImportView.post() can send the identical email per row
    instead of a second, drifting implementation.

    Never raises — a failed email must not roll back or block processing of
    an already-created account. Returns True/False so the caller can report
    success per-row exactly as the single-create endpoint already does.

    temp_password is used only to compose this one message — it is never
    persisted, and the exception message logged on failure never includes it
    (only the recipient email and the exception itself).
    """
    from apps.tenants.utils import get_current_company_code

    try:
        company_name, logo_url, website, address = _get_company_branding()
        company_name = company_name or 'Royal HRMS'
        # Same FRONTEND_URL + '/login' convention as the company-provisioning
        # welcome email (see apps.tenants.utils.send_company_provisioned_email).
        company_code = get_current_company_code()
        company_code_line = (
            f'<strong>Company ID:</strong> {company_code}<br>' if company_code else ''
        )
        login_url = f'{settings.FRONTEND_URL}/login'

        body = (
            f'<p>Hi <strong>{user.full_name}</strong>,</p>'
            f'<p>Your {company_name} account has been created.'
            f' Use the credentials below to log in:</p>'
            f'<p>'
            f'{company_code_line}'
            f'<strong>Employee ID:</strong> {user.employee_id}<br>'
            f'<strong>Login Email:</strong> {user.email}<br>'
            f'<strong>Temporary Password:</strong> {temp_password}<br>'
            f'<strong>Login URL:</strong> <a href="{login_url}">{login_url}</a>'
            f'</p>'
            f'<p>You will be asked to change your password on first login.</p>'
            f'<p>— HR Team</p>'
        )
        html_body = _company_email_wrapper(body, company_name, logo_url, website, address)

        connection, from_email = _get_smtp_connection()
        msg = _build_message(
            subject=f'Welcome to {company_name} — Your Login Credentials',
            html_body=html_body,
            from_email=from_email,
            to=[user.email],
            connection=connection,
        )
        msg.send(fail_silently=False)
        logger.info('Welcome email sent to %s', user.email)
        return True
    except Exception as exc:
        logger.error('Welcome email failed for %s: %s', user.email, exc)
        return False


def send_email_change_notifications(user, old_email: str) -> tuple[bool, bool]:
    """
    Sent after a system_admin's login email is changed (see
    EmployeeChangeLoginEmailView) — one confirmation to the NEW address
    (user.email, already updated by the caller) and one security alert to
    the OLD address, so whoever still has that old inbox open finds out.

    Never raises, same "log and return False" contract as
    send_employee_welcome_email. Deliberately never includes a password or
    any credential — this only ever follows an email-field change, never a
    password reset, and the account's existing password is left untouched
    by the caller.

    Returns (new_address_sent, old_address_sent).
    """
    try:
        company_name, logo_url, website, address = _get_company_branding()
        company_name = company_name or 'Royal HRMS'
        login_url = f'{settings.FRONTEND_URL}/login'
        connection, from_email = _get_smtp_connection()
    except Exception as exc:
        logger.error('Email-change notification setup failed for %s: %s', user.email, exc)
        return False, False

    new_sent = False
    try:
        new_body = (
            f'<p>Hi <strong>{user.full_name}</strong>,</p>'
            f'<p>Your {company_name} login email has been changed. You can now log in using:</p>'
            f'<p><strong>New Login Email:</strong> {user.email}<br>'
            f'<strong>Login URL:</strong> <a href="{login_url}">{login_url}</a></p>'
            f'<p>Your password has not changed — use your existing password to log in with this new email.</p>'
            f'<p style="color:#b91c1c;">If you did not request this change, contact your administrator immediately.</p>'
            f'<p>— HR Team</p>'
        )
        new_html = _company_email_wrapper(new_body, company_name, logo_url, website, address)
        msg = _build_message(
            subject=f'Your {company_name} login email has changed',
            html_body=new_html, from_email=from_email, to=[user.email], connection=connection,
        )
        msg.send(fail_silently=False)
        logger.info('Email-change confirmation sent to new address %s', user.email)
        new_sent = True
    except Exception as exc:
        logger.error('Email-change confirmation failed for new address %s: %s', user.email, exc)

    old_sent = False
    try:
        old_body = (
            f'<p>Hi,</p>'
            f'<p>This is a security notification: the login email for your {company_name} account, '
            f'previously <strong>{old_email}</strong>, was just changed to <strong>{user.email}</strong>.</p>'
            f'<p>This address ({old_email}) will no longer be used to log in.</p>'
            f'<p style="color:#b91c1c;">If you did not request this change, contact your administrator immediately.</p>'
            f'<p>— HR Team</p>'
        )
        old_html = _company_email_wrapper(old_body, company_name, logo_url, website, address)
        msg = _build_message(
            subject=f'Security notice: your {company_name} login email was changed',
            html_body=old_html, from_email=from_email, to=[old_email], connection=connection,
        )
        msg.send(fail_silently=False)
        logger.info('Email-change security alert sent to old address %s', old_email)
        old_sent = True
    except Exception as exc:
        logger.error('Email-change security alert failed for old address %s: %s', old_email, exc)

    return new_sent, old_sent


def send_test_email(recipient_email: str, smtp_config: dict) -> None:

    sender_name = smtp_config.get('sender_name', '').strip()
    raw_from    = smtp_config.get('from_email', smtp_config['username'])
    from_email  = f'{sender_name} <{raw_from}>' if sender_name else raw_from

    connection = get_connection(
        backend='django.core.mail.backends.smtp.EmailBackend',
        host=smtp_config['host'],
        port=smtp_config['port'],
        username=smtp_config['username'],
        password=smtp_config['password'],
        use_tls=smtp_config.get('use_tls', True),
        fail_silently=False,
    )

    branding = _get_company_branding()
    company_name = branding[0] or 'Royal HRMS'
    html_body = (
        f'<p>This is a test email from <strong>{company_name}</strong>.</p>'
        '<p style="color:#16a34a;font-weight:bold;font-size:18px;">'
        '&#10003;&nbsp;Your SMTP configuration is working correctly.</p>'
        f'<p>Regards,<br><strong>{company_name}</strong></p>'
    )
    html_body = _company_email_wrapper(html_body, *branding)

    msg = _build_message(
        subject='Royal HRMS — SMTP Configuration Test',
        html_body=html_body,
        from_email=from_email,
        to=[recipient_email],
        connection=connection,
    )
    msg.send(fail_silently=False)


def _get_company_branding() -> tuple[str, str, str, str]:
    """Return (company_name, logo_url, website, address) from the singleton Company row."""
    from apps.accounts.models import Company  # avoid circular import

    company = Company.objects.first()
    if not company:
        return '', '', '', ''

    company_name = company.company_name
    logo_url     = company.logo.url if company.logo else ''
    website      = company.website
    address      = ', '.join(p for p in [company.address, company.city, company.state] if p)
    return company_name, logo_url, website, address


def _company_email_wrapper(body: str, company_name: str, logo_url: str,
                           website: str, address: str) -> str:
    """Wrap an email body HTML with a branded company header and footer."""
    logo_html = (
        f'<img src="{logo_url}" alt="{company_name}" '
        f'style="max-height:70px;max-width:220px;object-fit:contain;" />'
        if logo_url
        else f'<span style="font-size:18px;font-weight:700;color:#1a1a2e;">{company_name}</span>'
    )
    footer_parts = [p for p in [website, address] if p]
    footer_text  = ' &nbsp;|&nbsp; '.join(footer_parts) if footer_parts else company_name

    return f"""
<div style="background:#f4f4f7;padding:32px 0;font-family:Arial,Helvetica,sans-serif;">
  <div style="max-width:600px;margin:0 auto;background:#ffffff;
              border-radius:8px;overflow:hidden;
              box-shadow:0 2px 8px rgba(0,0,0,0.08);">

    <!-- Header -->
    <div style="background:#ffffff;text-align:center;
                padding:28px 40px 20px;
                border-bottom:3px solid #4f46e5;">
      {logo_html}
    </div>

    <!-- Body -->
    <div style="padding:32px 40px;color:#333333;line-height:1.7;font-size:15px;">
      {body}
    </div>

    <!-- Footer -->
    <div style="background:#f8f8fb;text-align:center;
                padding:16px 24px;font-size:12px;color:#888888;
                border-top:1px solid #eeeeee;">
      {footer_text}
    </div>

    <!-- Royal HRMS platform link — the product's own site, distinct from
         the tenant company's own website/address line above. Fixed, not
         tenant-configurable, same category of constant as BRAND_NAME/
         BRAND_LOGO on the frontend login page. -->
    <div style="background:#f8f8fb;text-align:center;
                padding:10px 24px 16px;font-size:11px;color:#aaaaaa;
                border-top:1px solid #eeeeee;">
      Visit Royal HRMS<br/>
      <a href="https://royalhrms.com" style="color:#4f46e5;text-decoration:none;">royalhrms.com</a>
    </div>

  </div>
</div>
"""


def send_template_email(
    recipient_email: str,
    template_name: str,
    context: dict,
    extra_attachments: list[tuple[str, bytes, str]] | None = None,
) -> None:
    """
    extra_attachments: optional list of (filename, content_bytes, mime_type) —
    for per-send dynamic attachments (e.g. a calendar invite whose date/time
    differs on every send) that can't be a static EmailTemplateAttachment row.
    """

    from apps.accounts.models import EmailTemplate  # avoid circular import

    try:
        tpl = EmailTemplate.objects.prefetch_related('attachments').get(
            name=template_name, is_active=True
        )
    except EmailTemplate.DoesNotExist:
        raise LookupError(
            f'Email template "{template_name}" not found or inactive.'
        )

    subject, html_body = tpl.render(context)
    html_body = _company_email_wrapper(html_body, *_get_company_branding())

    connection, from_email = _get_smtp_connection()

    msg = _build_message(
        subject=subject,
        html_body=html_body,
        from_email=from_email,
        to=[recipient_email],
        connection=connection,
    )

    for att in tpl.attachments.all():
        with att.file.open('rb') as f:
            msg.attach(att.filename, f.read(), att.mime_type)

    for filename, content, mime_type in (extra_attachments or []):
        msg.attach(filename, content, mime_type)

    msg.send(fail_silently=False)
    logger.info(
        'Template email "%s" sent to %s.', template_name, recipient_email
    )
