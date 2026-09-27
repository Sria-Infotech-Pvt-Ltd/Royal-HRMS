from __future__ import annotations

import logging
import re
import secrets
import string
from datetime import date, datetime
from email.utils import formataddr

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

def _get_smtp_connection() -> tuple[object, str, object]:
    """Return (connection, from_email, smtp) using the active SMTPSettings row
    — `smtp` is the row itself, returned so callers can record which config
    was actually used (see EmailLog.smtp_settings) without a second query.

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
    from_email = formataddr((smtp.sender_name, smtp.from_email))
    return connection, from_email, smtp


# ─── Email helpers ────────────────────────────────────────────────────────────

def _html_to_text(html: str) -> str:
    
    return re.sub(r'<[^>]+>', '', html).strip()


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

    connection, from_email, _smtp = _get_smtp_connection()
    expiry  = getattr(settings, 'OTP_EXPIRY_MINUTES', 10)
    branding = _get_company_branding()
    company_name = branding[0] or 'Aira HRMS'

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


def send_test_email(recipient_email: str, smtp_config: dict) -> None:
    
    sender_name = smtp_config.get('sender_name', '').strip()
    raw_from    = smtp_config.get('from_email', smtp_config['username'])
    from_email  = formataddr((sender_name, raw_from))

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
    company_name = branding[0] or 'Aira HRMS'
    html_body = (
        f'<p>This is a test email from <strong>{company_name}</strong>.</p>'
        '<p style="color:#16a34a;font-weight:bold;font-size:18px;">'
        '&#10003;&nbsp;Your SMTP configuration is working correctly.</p>'
        f'<p>Regards,<br><strong>{company_name}</strong></p>'
    )
    html_body = _company_email_wrapper(html_body, *branding)

    msg = _build_message(
        subject=f'{company_name} — SMTP Configuration Test',
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
    address      = ', '.join(
        p for p in [company.address, company.city, company.state, company.pin_code] if p
    )
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
    footer_parts = [p for p in [address, website] if p]
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

  </div>
</div>
"""


# Deny-list of context keys whose value must never be persisted to EmailLog —
# these carry a real, working credential in the rendered email body, not just
# a reference to one, so logging them verbatim would let anyone holding
# email_logs.view read a live password/OTP/token indefinitely (CLAUDE.md:
# "never log passwords, tokens"). The actual outgoing email is unaffected —
# only what's written to EmailLog is redacted. See send_template_email below.
_SENSITIVE_CONTEXT_KEYS = {
    'password', 'temp_password', 'otp', 'token', 'secret',
    'api_key', 'access_token', 'refresh_token', 'pin',
}


def _redact_context(context: dict) -> dict:
    return {
        k: ('[REDACTED]' if k.lower() in _SENSITIVE_CONTEXT_KEYS else v)
        for k, v in context.items()
    }


def send_template_email(
    recipient_email: str,
    template_name: str,
    context: dict,
    extra_attachments: list[tuple[str, bytes, str]] | None = None,
    module: str = '',
    triggered_by=None,
) -> None:
    """
    extra_attachments: optional list of (filename, content_bytes, mime_type) —
    for per-send dynamic attachments (e.g. a calendar invite whose date/time
    differs on every send) that can't be a static EmailTemplateAttachment row.

    module: which app/feature triggered this send (e.g. 'hrms', 'recruitment')
    — recorded on the EmailLog row so the system-wide log can be filtered by
    source. triggered_by: the acting User, if any (most Celery/background call
    sites have none — pass None, which is what the field is nullable for).

    Writes one EmailLog row per attempt (success or failure) before returning
    or re-raising — the raise contract is otherwise byte-for-byte unchanged
    from before this row was added: every exception type this function raises
    today is still raised, via a bare `raise`, never re-wrapped. This matters
    because some callers (e.g. recruitment's SendCandidateEmailView) inspect
    the caught exception's type/attributes to shape their own HTTP response.
    """
    from apps.accounts.models import EmailLog, EmailTemplate  # avoid circular import

    log_context = _redact_context(context)
    has_sensitive = log_context != context

    try:
        tpl = EmailTemplate.objects.prefetch_related('attachments').get(
            name=template_name, is_active=True
        )
    except EmailTemplate.DoesNotExist:
        exc = LookupError(f'Email template "{template_name}" not found or inactive.')
        EmailLog.record(
            recipient_email=recipient_email, subject='', body_html='',
            template_name=template_name, context=log_context, module=module,
            status=EmailLog.STATUS_FAILED, error_message=str(exc),
            triggered_by=triggered_by, has_sensitive_context=has_sensitive,
        )
        raise exc

    subject, html_body = tpl.render(context)
    html_body = _company_email_wrapper(html_body, *_get_company_branding())

    # Redacted copy of the same content, for the log row only — never sent.
    log_subject, log_body = tpl.render(log_context)
    log_body = _company_email_wrapper(log_body, *_get_company_branding())

    attachment_names = [att.filename for att in tpl.attachments.all()]
    attachment_names += [a[0] for a in (extra_attachments or [])]

    smtp = None
    try:
        connection, from_email, smtp = _get_smtp_connection()
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
    except Exception as exc:
        EmailLog.record(
            recipient_email=recipient_email, subject=log_subject, body_html=log_body,
            template_name=template_name, context=log_context, module=module,
            status=EmailLog.STATUS_FAILED, error_message=str(exc),
            triggered_by=triggered_by, smtp_settings=smtp,
            had_attachments=bool(attachment_names),
            attachment_filenames=', '.join(attachment_names),
            has_sensitive_context=has_sensitive,
        )
        raise

    EmailLog.record(
        recipient_email=recipient_email, subject=log_subject, body_html=log_body,
        template_name=template_name, context=log_context, module=module,
        status=EmailLog.STATUS_SENT, error_message='',
        triggered_by=triggered_by, smtp_settings=smtp,
        had_attachments=bool(attachment_names),
        attachment_filenames=', '.join(attachment_names),
        has_sensitive_context=has_sensitive,
    )
    logger.info(
        'Template email "%s" sent to %s.', template_name, recipient_email
    )


def resend_logged_email(email_log, triggered_by=None):
    """
    Replay a previously-failed EmailLog's stored subject/body verbatim.
    Never re-touches EmailTemplate — immune to the template being edited or
    deleted since the original send. Writes a NEW EmailLog row (does not
    mutate `email_log`) and raises on failure, mirroring send_template_email's
    contract. Attachments are never replayed (neither static
    EmailTemplateAttachment rows nor dynamic extra_attachments are available
    at this point) — callers should surface email_log.had_attachments as a
    "not reproduced on resend" note.
    """
    from apps.accounts.models import EmailLog

    smtp = None
    try:
        connection, from_email, smtp = _get_smtp_connection()
        msg = _build_message(
            subject=email_log.subject,
            html_body=email_log.body_html,
            from_email=from_email,
            to=[email_log.recipient_email],
            connection=connection,
        )
        msg.send(fail_silently=False)
    except Exception as exc:
        EmailLog.record(
            recipient_email=email_log.recipient_email, subject=email_log.subject,
            body_html=email_log.body_html, template_name=email_log.template_name,
            context=email_log.context, module=email_log.module,
            status=EmailLog.STATUS_FAILED, error_message=str(exc),
            triggered_by=triggered_by, smtp_settings=smtp,
            had_attachments=email_log.had_attachments,
            attachment_filenames=email_log.attachment_filenames,
            has_sensitive_context=email_log.has_sensitive_context,
            is_resend=True, resend_of=email_log,
        )
        raise

    return EmailLog.record(
        recipient_email=email_log.recipient_email, subject=email_log.subject,
        body_html=email_log.body_html, template_name=email_log.template_name,
        context=email_log.context, module=email_log.module,
        status=EmailLog.STATUS_SENT, error_message='',
        triggered_by=triggered_by, smtp_settings=smtp,
        had_attachments=email_log.had_attachments,
        attachment_filenames=email_log.attachment_filenames,
        has_sensitive_context=email_log.has_sensitive_context,
        is_resend=True, resend_of=email_log,
    )
