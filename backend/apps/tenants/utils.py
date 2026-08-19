"""
Tenant-context helpers for code that runs OUTSIDE an HTTP request — Celery
tasks, chiefly. apps.tenants.middleware.TenantSchemaMiddleware only scopes
the database connection for the lifetime of one HTTP request; a Celery
worker process (or Celery Beat itself) never goes through that middleware,
so without deliberately activating a tenant, task code sees only the
public schema — no business tables live there at all (see SHARED_APPS /
TENANT_APPS in config/settings.py), so every query fails outright.
"""
import logging
import re

from django.conf import settings

from apps.tenants.models import Client

logger = logging.getLogger(__name__)


def run_for_all_tenants(fn, task_name: str = '', required_module: str | None = None) -> dict:
    """
    Runs fn() once per active company, with that company's schema
    activated. Used by scheduled (Celery Beat) tasks that have no single
    natural tenant — e.g. "check every company for missing clockouts today"
    rather than "check clockouts for company X".

    required_module skips any company that doesn't have that optional
    module enabled (see Client.has_module). Pass this for any task whose
    work only makes sense for a module-enabled company — without it, a
    task keeps running its real logic (sending reminder emails, mutating
    leave balances, pushing notifications) for a company that never turned
    the module on, or turned it off after using it, since this loop is the
    only place outside an HTTP request where enabled_modules can be
    checked at all (apps.tenants.middleware.TenantSchemaMiddleware's module
    gate only ever runs for real HTTP requests). Omit it for platform-level
    tasks with no single company module (e.g. sweep_stale_provisioning).

    One tenant's exception is logged and does NOT stop the others — a bug
    or outage affecting one company's data must never silently skip the
    daily reminder/check for every other company.

    Always skips a company still mid-provisioning (provisioning_status !=
    'active') regardless of required_module — Client.is_active and
    enabled_modules are both set the moment the registry row is created
    (see apps.tenants.services.create_pending_client), well before the
    async provisioning task has actually finished creating the schema and
    running its migrations. Without this, a scheduled task can land on a
    company whose schema exists but is still missing tables the query
    needs, and crash with something like `relation "..." does not exist`
    instead of a clean skip.

    Returns {schema_name: result_or_None} for every eligible tenant that
    was actually run (skipped tenants are simply absent from the result,
    same as if they had no active tenants at all — not represented as
    None, which is reserved for "ran but failed").
    """
    results = {}
    for client in Client.objects.filter(is_active=True, provisioning_status=Client.PROVISIONING_ACTIVE):
        if required_module and not client.has_module(required_module):
            continue
        try:
            with client:
                results[client.schema_name] = fn()
        except Exception:
            logger.error(
                '%s failed for tenant %s', task_name or fn.__name__, client.schema_name,
                exc_info=True,
            )
            results[client.schema_name] = None
    return results


def run_in_tenant(schema_name: str, fn):
    """
    Runs fn() with the given company's schema activated. Used by
    per-object tasks (e.g. "email this announcement") that already know
    exactly which company they belong to — the schema_name the caller
    captured at dispatch time, when a tenant WAS active (mid-request).

    Raises Client.DoesNotExist if the schema is unknown/inactive — callers
    let this propagate so Celery's normal retry/failure handling applies,
    same as any other exception in task body.
    """
    client = Client.objects.get(schema_name=schema_name, is_active=True)
    with client:
        return fn()


def get_current_company_code() -> str:
    """
    The human-facing Company ID (e.g. "DEMOCO") for whichever tenant schema
    is currently active — for anything shown to a user that needs to tell
    them which Company ID to log in with (e.g. the new-employee welcome
    email). Client itself lives in the public schema (see SHARED_APPS), so
    this briefly switches there to look it up and restores the caller's
    schema on the way out. Returns '' if no tenant is active (e.g. running
    against public directly) or the lookup fails, so a caller building an
    email/notification degrades gracefully instead of crashing.
    """
    from django.db import connection
    from django_tenants.utils import get_public_schema_name, schema_context

    current_schema = connection.schema_name
    if not current_schema or current_schema == get_public_schema_name():
        return ''
    try:
        with schema_context(get_public_schema_name()):
            client = Client.objects.filter(schema_name=current_schema).first()
            return client.company_code if client else ''
    except Exception:
        logger.exception('get_current_company_code failed for schema %s', current_schema)
        return ''


def _get_platform_smtp_connection():
    """
    Returns (connection, from_email) built from PlatformSMTPSettings, or
    (None, '') if it isn't configured yet. Shared by every platform-level
    email (provisioning, platform-admin OTP, platform-admin invite) — see
    send_company_provisioned_email's docstring for why these deliberately
    don't go through apps.accounts.utils.send_template_email.
    """
    from django.core.mail import get_connection

    from apps.tenants.models import PlatformSMTPSettings

    smtp = PlatformSMTPSettings.get_solo()
    if not smtp.is_configured():
        return None, ''

    connection = get_connection(
        backend='django.core.mail.backends.smtp.EmailBackend',
        host=smtp.host, port=smtp.port,
        username=smtp.username, password=smtp.password,
        use_tls=smtp.use_tls, fail_silently=False,
    )
    from_email = f'{smtp.sender_name} <{smtp.from_email}>' if smtp.sender_name else smtp.from_email
    return connection, from_email


def send_company_provisioned_email(admin_email: str, company_code: str, company_name: str, password: str) -> None:
    """
    Tells a brand-new company's first admin their login is ready.

    Deliberately does NOT go through apps.accounts.utils.send_template_email
    (the pattern every other email in this codebase uses) — that helper
    requires an active SMTPSettings row in the CURRENT schema, and a
    company that was just created a moment ago has never configured one
    yet (SMTP is itself a per-tenant setting living inside the schema this
    email is announcing the existence of — a chicken-and-egg problem).
    This is a platform-level email, sent via PlatformSMTPSettings (see
    apps/tenants/models.py) — the platform operator's own outbound mail
    account, configured once by a platform admin, not any one tenant's.

    Best-effort: failures (including "not configured yet") are logged and
    swallowed, never raised — a flaky send must not fail company creation
    itself, since by this point the company already exists and is fully
    functional. The platform admin still sees the password once in the
    UI/CLI output regardless, as a fallback if this email never arrives.
    """
    from django.core.mail import EmailMultiAlternatives

    connection, from_email = _get_platform_smtp_connection()
    if not connection:
        logger.warning(
            'Platform SMTP not configured — skipped provisioning email to %s for company %s. '
            'Configure it in the platform-admin settings, or share the password shown above directly.',
            admin_email, company_code,
        )
        return

    login_url = f'{settings.FRONTEND_URL}/login'
    html_body = f"""
        <p>Hi,</p>
        <p>Your company <strong>{company_name}</strong> has been set up on Royal HRMS.
        Use the credentials below to sign in for the first time:</p>
        <table style="border-collapse:collapse;margin:16px 0;">
          <tr>
            <td style="padding:6px 12px;font-weight:600;color:#555;">Login URL</td>
            <td style="padding:6px 12px;"><a href="{login_url}">{login_url}</a></td>
          </tr>
          <tr>
            <td style="padding:6px 12px;font-weight:600;color:#555;">Company ID</td>
            <td style="padding:6px 12px;font-family:monospace;">{company_code}</td>
          </tr>
          <tr>
            <td style="padding:6px 12px;font-weight:600;color:#555;">Login Email</td>
            <td style="padding:6px 12px;">{admin_email}</td>
          </tr>
          <tr>
            <td style="padding:6px 12px;font-weight:600;color:#555;">Temporary Password</td>
            <td style="padding:6px 12px;font-family:monospace;letter-spacing:1px;">{password}</td>
          </tr>
        </table>
        <p>You'll be asked to set a new password the first time you log in.</p>
        <p style="color:#888;font-size:13px;">
            Keep this email private — anyone with these details can sign in as your company's administrator.
            If you weren't expecting this, please ignore it.
        </p>
        <p>Regards,<br><strong>Royal HRMS</strong></p>
    """
    try:
        msg = EmailMultiAlternatives(
            subject=f'Your {company_name} account on Royal HRMS is ready',
            body=re.sub(r'<[^>]+>', '', html_body).strip(),
            from_email=from_email,
            to=[admin_email],
            connection=connection,
        )
        msg.attach_alternative(html_body, 'text/html')
        msg.send(fail_silently=False)
    except Exception:
        logger.exception(
            'Failed to send provisioning email to %s for company %s — '
            'the platform admin still has the password from the create-company response.',
            admin_email, company_code,
        )


def send_platform_admin_otp_email(email: str, otp: str, full_name: str) -> None:
    """
    Platform-admin forgot-password OTP — sent via PlatformSMTPSettings (see
    _get_platform_smtp_connection), never apps.accounts.utils.send_otp_email,
    since that helper reads a per-tenant SMTPSettings row and a platform
    admin has no tenant schema at all. Raises on failure (unlike the
    provisioning email above) — the caller needs to know a genuine send
    failure so it can tell the requester, rather than silently pretending
    an OTP was sent when it wasn't.
    """
    from django.core.mail import EmailMultiAlternatives

    connection, from_email = _get_platform_smtp_connection()
    if not connection:
        raise RuntimeError('Platform SMTP is not configured.')

    expiry = getattr(settings, 'OTP_EXPIRY_MINUTES', 10)
    html_body = f"""
        <p>Hi {full_name},</p>
        <p>Your OTP to reset your Royal HRMS platform-admin password is:</p>
        <p style="font-size:32px;font-weight:bold;letter-spacing:8px;">{otp}</p>
        <p>This code expires in {expiry} minutes. If you didn't request this, you can ignore this email.</p>
        <p>Regards,<br><strong>Royal HRMS</strong></p>
    """
    msg = EmailMultiAlternatives(
        subject='Your Royal HRMS platform-admin password reset OTP',
        body=re.sub(r'<[^>]+>', '', html_body).strip(),
        from_email=from_email,
        to=[email],
        connection=connection,
    )
    msg.attach_alternative(html_body, 'text/html')
    msg.send(fail_silently=False)


def send_platform_admin_invite_email(email: str, full_name: str, password: str) -> None:
    """
    Tells a newly-invited platform admin their login is ready — same
    "temporary password, changed on first login" pattern as
    send_company_provisioned_email, but there is no PlatformAdmin
    equivalent of must_change_password today, so the email itself is the
    only place this is communicated; the invited admin should change it
    via My Account after signing in.
    """
    from django.core.mail import EmailMultiAlternatives

    connection, from_email = _get_platform_smtp_connection()
    if not connection:
        logger.warning(
            'Platform SMTP not configured — skipped invite email to %s. '
            'Share the password shown in the UI directly instead.', email,
        )
        return

    html_body = f"""
        <p>Hi {full_name},</p>
        <p>You've been added as a platform administrator on Royal HRMS. Use the credentials
        below to sign in:</p>
        <table style="border-collapse:collapse;margin:16px 0;">
          <tr>
            <td style="padding:6px 12px;font-weight:600;color:#555;">Login Email</td>
            <td style="padding:6px 12px;">{email}</td>
          </tr>
          <tr>
            <td style="padding:6px 12px;font-weight:600;color:#555;">Temporary Password</td>
            <td style="padding:6px 12px;font-family:monospace;letter-spacing:1px;">{password}</td>
          </tr>
        </table>
        <p>Please change this password from My Account after signing in.</p>
        <p style="color:#888;font-size:13px;">
            Keep this email private — anyone with these details can manage every company on the platform.
        </p>
        <p>Regards,<br><strong>Royal HRMS</strong></p>
    """
    try:
        msg = EmailMultiAlternatives(
            subject='You\'ve been added as a Royal HRMS platform administrator',
            body=re.sub(r'<[^>]+>', '', html_body).strip(),
            from_email=from_email,
            to=[email],
            connection=connection,
        )
        msg.attach_alternative(html_body, 'text/html')
        msg.send(fail_silently=False)
    except Exception:
        logger.exception(
            'Failed to send invite email to %s — the inviting admin still has the '
            'password from the create-admin response.', email,
        )
