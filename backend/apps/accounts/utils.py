from __future__ import annotations

import logging
import re
import secrets
import string

from django.conf import settings
from django.core.mail import EmailMultiAlternatives, get_connection

logger = logging.getLogger('accounts')

_OTP_ALPHABET: str = string.digits


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
  
    connection, from_email = _get_smtp_connection()
    expiry = getattr(settings, 'OTP_EXPIRY_MINUTES', 10)

    html_body = (
        f'<p>Hi <strong>{full_name}</strong>,</p>'
        f'<p>Your OTP to reset your Royal Staffing HRMS password is:</p>'
        f'<p style="font-size:32px;font-weight:bold;letter-spacing:8px;'
        f'color:#4f46e5;text-align:center;padding:20px 0;'
        f'border:2px dashed #c7d2fe;border-radius:8px;">{otp}</p>'
        f'<p>This OTP is valid for <strong>{expiry} minute(s)</strong>. '
        f'<span style="color:#dc2626;font-weight:bold;">Do not share it with anyone.</span></p>'
        f'<p>If you did not request this reset, please ignore this email or '
        f'contact your system administrator immediately.</p>'
        f'<p style="margin-top:32px;">Regards,<br>'
        f'<strong>HR Team</strong><br>Royal Staffing Services</p>'
    )

    msg = _build_message(
        subject='Your Royal Staffing HRMS Password Reset OTP',
        html_body=html_body,
        from_email=from_email,
        to=[email],
        connection=connection,
    )
    msg.send(fail_silently=False)


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

    html_body = (
        '<p>This is a test email from <strong>Royal Staffing HRMS</strong>.</p>'
        '<p style="color:#16a34a;font-weight:bold;font-size:18px;">'
        '&#10003;&nbsp;Your SMTP configuration is working correctly.</p>'
        '<p>Regards,<br><strong>Royal Staffing HRMS</strong></p>'
    )

    msg = _build_message(
        subject='Royal HRMS — SMTP Configuration Test',
        html_body=html_body,
        from_email=from_email,
        to=[recipient_email],
        connection=connection,
    )
    msg.send(fail_silently=False)


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

  </div>
</div>
"""


def send_template_email(
    recipient_email: str,
    template_name: str,
    context: dict,
) -> None:

    from apps.accounts.models import Company, EmailTemplate  # avoid circular import

    try:
        tpl = EmailTemplate.objects.prefetch_related('attachments').get(
            name=template_name, is_active=True
        )
    except EmailTemplate.DoesNotExist:
        raise LookupError(
            f'Email template "{template_name}" not found or inactive.'
        )

    subject, html_body = tpl.render(context)

    # Wrap with company branding
    company      = Company.objects.first()
    company_name = company.company_name if company else ''
    logo_url     = company.logo.url     if (company and company.logo) else ''
    website      = company.website      if company else ''
    address_parts = [p for p in [
        getattr(company, 'address', ''),
        getattr(company, 'city', ''),
        getattr(company, 'state', ''),
    ] if p] if company else []
    address = ', '.join(address_parts)

    html_body = _company_email_wrapper(html_body, company_name, logo_url, website, address)

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

    msg.send(fail_silently=False)
    logger.info(
        'Template email "%s" sent to %s.', template_name, recipient_email
    )
