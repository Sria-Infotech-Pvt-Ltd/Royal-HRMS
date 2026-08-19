"""
Tenant registry — lives in the shared/public PostgreSQL schema (see
SHARED_APPS in config/settings.py). Every other app in this project
(accounts, payroll, attendance, hrms, ...) is a TENANT_APP: each Client
below gets its own complete copy of those tables in its own schema, so a
company can never see another company's rows — enforced by which schema
the database connection is pointed at, not by an application-level
`.filter(company=...)` that every query would have to remember.

Login flow: the user submits a company code alongside email/password
(apps.accounts login view resolves the Client from that code, activates
its schema, then authenticates against that schema's User table). This is
why TENANT_DOMAIN_MODEL/Domain still exist below — django-tenants requires
a domain model to exist and every Client needs at least one Domain row for
its internal bookkeeping — but real HTTP requests are NOT routed by
hostname here; see apps/tenants/middleware.py.
"""
import uuid
from datetime import timedelta

from django.conf import settings
from django.contrib.auth.hashers import check_password, make_password
from django.db import models, transaction
from django.db.models import F
from django.utils import timezone
from django_tenants.models import DomainMixin, TenantMixin


# The full set of toggleable business modules this project currently
# recognizes. A Client's `enabled_modules` stores a subset of these keys.
# Kept as a plain list (not one boolean column per module) so adding a new
# toggleable module later is a one-line change here, not a migration.
MODULE_ANNOUNCEMENTS      = 'announcements'
MODULE_RECRUITMENT        = 'recruitment'
MODULE_FACE_ATTENDANCE    = 'face_attendance'
MODULE_ATTENDANCE         = 'attendance'
MODULE_LEAVE              = 'leave'
MODULE_PAYROLL            = 'payroll'
MODULE_EXPENSES           = 'expenses'
MODULE_SEPARATION         = 'separation'
MODULE_VOICE_COMMANDS     = 'voice_commands'
MODULE_ASSESSMENTS        = 'assessments'

ALL_MODULES = [
    MODULE_ANNOUNCEMENTS,
    MODULE_RECRUITMENT,
    MODULE_FACE_ATTENDANCE,
    MODULE_ATTENDANCE,
    MODULE_LEAVE,
    MODULE_PAYROLL,
    MODULE_EXPENSES,
    MODULE_SEPARATION,
    MODULE_VOICE_COMMANDS,
    MODULE_ASSESSMENTS,
]

MODULE_LABELS = {
    MODULE_ANNOUNCEMENTS:   'Announcements',
    MODULE_RECRUITMENT:     'Recruitment',
    MODULE_FACE_ATTENDANCE: 'Face ID Attendance',
    MODULE_ATTENDANCE:      'Attendance',
    MODULE_LEAVE:           'Leave Management',
    MODULE_PAYROLL:         'Payroll',
    MODULE_EXPENSES:        'Expenses',
    MODULE_SEPARATION:      'Separation & Offboarding',
    MODULE_VOICE_COMMANDS:  'Voice Commands',
    MODULE_ASSESSMENTS:     'Assessments',
}


class Client(TenantMixin):
    """One row per company. `schema_name` (from TenantMixin) is the
    PostgreSQL schema holding that company's entire copy of every
    TENANT_APP table. Saving a new Client auto-creates and migrates that
    schema (see TenantMixin.save / auto_create_schema)."""

    # django-tenants creates the schema synchronously in .save() by
    # default — fine for the "handful of companies, provisioned by us"
    # scale this is built for (see apps/tenants/management/commands/
    # create_company.py). Revisit if self-serve signup is ever added.
    auto_create_schema = True

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    # Human-facing company code the login form asks for — distinct from
    # schema_name (a Postgres identifier with its own character
    # restrictions) so it can be a friendlier value like "ACME2026".
    company_code = models.CharField(max_length=50, unique=True, db_index=True)
    company_name = models.CharField(max_length=200)

    enabled_modules = models.JSONField(
        default=list, blank=True,
        help_text=f'Subset of: {", ".join(ALL_MODULES)}',
    )

    is_active = models.BooleanField(default=True)

    # Set only by the platform-admin API's async provisioning path (see
    # apps/tenants/views.py CompanyListCreateView.post and
    # apps/tenants/tasks.py finish_provisioning_task) — a Celery task
    # finishes the actual work independently of the web server process, so
    # restarting/crashing/reloading that process (which used to repeatedly
    # kill synchronous in-request provisioning) can no longer corrupt a
    # company mid-creation. manage.py create_company (terminal)
    # never sets this — it still runs synchronously start-to-finish and
    # a Client row it creates is 'active' immediately, matching the
    # default below.
    PROVISIONING_PENDING = 'pending'
    PROVISIONING_ACTIVE  = 'active'
    PROVISIONING_FAILED  = 'failed'
    PROVISIONING_STATUS_CHOICES = [
        (PROVISIONING_PENDING, 'Pending'),
        (PROVISIONING_ACTIVE,  'Active'),
        (PROVISIONING_FAILED,  'Failed'),
    ]
    provisioning_status = models.CharField(
        max_length=10, choices=PROVISIONING_STATUS_CHOICES, default=PROVISIONING_ACTIVE,
    )
    # The generated admin password, held here only until a platform admin
    # views it once through the UI (see CompanyRevealPasswordView), for the
    # async path where it can no longer be returned directly in the
    # HTTP response that kicked off provisioning (that response now
    # returns immediately, before the password even exists yet).
    pending_admin_password = models.CharField(max_length=128, blank=True, default='')

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'tenants_client'

    def __str__(self) -> str:
        return f'{self.company_name} ({self.company_code})'

    def has_module(self, module: str) -> bool:
        return module in (self.enabled_modules or [])


class Domain(DomainMixin):
    """Required by django-tenants' internals even though real request
    routing here is by company_code at login, not by hostname — see
    apps/tenants/middleware.py. One synthetic domain per Client
    (e.g. '<company_code>.internal') is enough to satisfy it."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    class Meta:
        db_table = 'tenants_domain'

    def __str__(self) -> str:
        return self.domain


class PlatformAdmin(models.Model):
    """
    The operator of this SaaS platform — the account that creates and
    manages companies (Client rows) themselves. Deliberately NOT a member
    of, and with no visibility into, any single company: a separate model
    from every tenant's own User (system_admin, hr, ...), living only in
    this shared public schema.

    Its JWT session is kept in its own cookie/claim namespace, entirely
    distinct from tenant-user logins — see apps/tenants/authentication.py
    and apps/tenants/tokens.py — so a platform-admin session can never be
    mistaken for, or grant, access to any company's data, and a company
    admin can never reach this layer.
    """
    id         = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    email      = models.EmailField(unique=True)
    password   = models.CharField(max_length=128)
    full_name  = models.CharField(max_length=150)
    is_active  = models.BooleanField(default=True)
    last_login = models.DateTimeField(null=True, blank=True)

    # Lockout — same fields/thresholds as apps.accounts.models.User, so the
    # platform admin login (the single most powerful account in this
    # system) isn't left with weaker brute-force protection than an
    # ordinary company employee login.
    failed_login_attempts = models.PositiveSmallIntegerField(default=0)
    locked_until           = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    # Not a Django auth user (no AbstractBaseUser) — set directly, the same
    # way AbstractBaseUser itself defines these, so DRF/Django internals
    # that duck-type on request.user (throttling's UserRateThrottle,
    # template context processors, etc.) work without error.
    is_authenticated = True
    is_anonymous     = False

    class Meta:
        db_table = 'tenants_platform_admin'

    def __str__(self) -> str:
        return self.email

    def set_password(self, raw_password: str) -> None:
        self.password = make_password(raw_password)

    def check_password(self, raw_password: str) -> bool:
        return check_password(raw_password, self.password)

    # ── Lockout helpers — mirrors apps.accounts.models.User exactly ──────────

    def is_locked(self) -> bool:
        """Return True if the account is currently locked out."""
        if not self.locked_until:
            return False
        if timezone.now() < self.locked_until:
            return True
        # Lock has expired — clear it atomically (fire-and-forget; failure is harmless)
        PlatformAdmin.objects.filter(pk=self.pk, locked_until=self.locked_until).update(
            locked_until=None,
            failed_login_attempts=0,
        )
        self.locked_until          = None
        self.failed_login_attempts = 0
        return False

    @transaction.atomic
    def increment_failed_login(self) -> None:
        max_attempts    = getattr(settings, 'LOGIN_MAX_ATTEMPTS', 5)
        lockout_minutes = getattr(settings, 'LOGIN_LOCKOUT_MINUTES', 30)

        # Atomic increment — safe under concurrent requests
        PlatformAdmin.objects.filter(pk=self.pk).update(
            failed_login_attempts=F('failed_login_attempts') + 1
        )
        self.refresh_from_db(fields=['failed_login_attempts'])

        if self.failed_login_attempts >= max_attempts:
            lock_until = timezone.now() + timedelta(minutes=lockout_minutes)
            PlatformAdmin.objects.filter(pk=self.pk).update(locked_until=lock_until)
            self.locked_until = lock_until

    def reset_failed_login(self) -> None:
        """Reset lockout state on successful login."""
        PlatformAdmin.objects.filter(pk=self.pk).update(
            failed_login_attempts=0, locked_until=None,
        )
        self.failed_login_attempts = 0
        self.locked_until          = None


class PlatformSMTPSettings(models.Model):
    """
    Singleton (pk=1) — the platform's OWN outbound mail account, used only
    for emails that aren't about any single company (e.g. "your company
    has been provisioned, here's your login" — see
    apps.tenants.utils.send_company_provisioned_email). Deliberately
    separate from apps.accounts.models.SMTPSettings, which is a per-tenant
    setting living inside one company's own schema — a brand-new company
    has no SMTP of its own configured yet at the exact moment this email
    needs to go out, and borrowing one specific tenant's credentials for a
    platform-wide purpose would be its own kind of layering violation.
    Configured by a platform admin; if left blank, provisioning emails are
    skipped (logged, not fatal — see send_company_provisioned_email).
    """
    host        = models.CharField(max_length=255, blank=True)
    port        = models.PositiveIntegerField(default=587)
    username    = models.CharField(max_length=255, blank=True)
    password    = models.CharField(max_length=255, blank=True)
    use_tls     = models.BooleanField(default=True)
    from_email  = models.EmailField(max_length=255, blank=True)
    sender_name = models.CharField(max_length=255, blank=True, default='Royal HRMS')
    updated_at  = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'tenants_platform_smtp_settings'

    def __str__(self) -> str:
        return f'Platform SMTP ({self.host or "not configured"})'

    def is_configured(self) -> bool:
        return bool(self.host and self.username and self.password and self.from_email)

    @classmethod
    def get_solo(cls) -> 'PlatformSMTPSettings':
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj


class PlatformAdminOTP(models.Model):
    """
    Forgot-password OTP for a PlatformAdmin — mirrors apps.accounts.models.
    OTPVerification exactly, but keyed to PlatformAdmin instead of a tenant
    User, since PlatformAdmin has no self-service recovery path today
    (currently only fixable via direct database access).
    """
    admin      = models.ForeignKey(PlatformAdmin, on_delete=models.CASCADE, related_name='otps')
    otp        = models.CharField(max_length=128)   # stores the hash, not the plain OTP
    attempts   = models.PositiveSmallIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField(db_index=True)
    is_used    = models.BooleanField(default=False, db_index=True)

    class Meta:
        db_table = 'tenants_platform_admin_otp'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['admin', 'is_used', 'expires_at']),
        ]

    def __str__(self) -> str:
        return f'OTP for {self.admin.email} (used={self.is_used})'

    def is_valid(self) -> bool:
        max_attempts = getattr(settings, 'OTP_MAX_ATTEMPTS', 5)
        return (
            not self.is_used
            and self.attempts <= max_attempts
            and timezone.now() < self.expires_at
        )

    def check_otp(self, plain_otp: str) -> bool:
        return check_password(plain_otp, self.otp)

    @classmethod
    @transaction.atomic
    def create_for_admin(cls, admin: 'PlatformAdmin') -> tuple['PlatformAdminOTP', str]:
        from apps.accounts.utils import generate_otp  # shared, tenant-agnostic helper

        cls.objects.filter(admin=admin, is_used=False).update(is_used=True)

        expiry_minutes = getattr(settings, 'OTP_EXPIRY_MINUTES', 10)
        plain_otp      = generate_otp()

        otp_obj = cls.objects.create(
            admin      = admin,
            otp        = make_password(plain_otp),
            expires_at = timezone.now() + timedelta(minutes=expiry_minutes),
        )
        return otp_obj, plain_otp


class PlatformAdminPasswordResetToken(models.Model):
    """Mirrors apps.accounts.models.PasswordResetToken, keyed to PlatformAdmin."""
    id         = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    admin      = models.ForeignKey(PlatformAdmin, on_delete=models.CASCADE, related_name='reset_tokens')
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField(db_index=True)
    is_used    = models.BooleanField(default=False, db_index=True)

    class Meta:
        db_table = 'tenants_platform_admin_reset_token'

    def __str__(self) -> str:
        return f'ResetToken({self.admin.email}, used={self.is_used})'

    def is_valid(self) -> bool:
        return not self.is_used and timezone.now() < self.expires_at

    @classmethod
    @transaction.atomic
    def create_for_admin(cls, admin: 'PlatformAdmin') -> 'PlatformAdminPasswordResetToken':
        cls.objects.filter(admin=admin, is_used=False).update(is_used=True)
        return cls.objects.create(admin=admin, expires_at=timezone.now() + timedelta(minutes=60))


class PlatformAdminAuditLog(models.Model):
    """
    Append-only record of platform-admin actions (create/disable a company,
    change its modules, reveal a password, invite another platform admin) —
    previously nonexistent, unlike every tenant-side action which already
    gets an AuditLog row. admin is SET_NULL so history survives an admin
    account being removed later; target_company likewise, since a company
    can in principle be deleted independently of its audit trail.
    """
    id             = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    admin          = models.ForeignKey(
                         PlatformAdmin, on_delete=models.SET_NULL, null=True, blank=True,
                         related_name='audit_logs',
                     )
    action         = models.CharField(max_length=100)
    target_company = models.ForeignKey(
                         Client, on_delete=models.SET_NULL, null=True, blank=True,
                         related_name='platform_audit_logs',
                     )
    changes        = models.JSONField(default=dict, blank=True)
    ip_address     = models.GenericIPAddressField(null=True, blank=True)
    created_at     = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        db_table = 'tenants_platform_admin_audit_log'
        ordering = ['-created_at']

    def __str__(self) -> str:
        return f'{self.action} by {self.admin_id} @ {self.created_at}'
