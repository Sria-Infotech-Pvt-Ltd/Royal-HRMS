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

from core.storage import AuthenticatedRawMediaCloudinaryStorage, subscription_payment_receipt_upload_path


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
# Added with SaaS plans. Companies created before them had these features
# ungated; their URL gates apply only under SUBSCRIPTION_ENFORCEMENT=on
# (apps.tenants.modules.LATE_GATED_MODULES).
MODULE_DOCUMENTS          = 'documents'
MODULE_ASSETS             = 'assets'
MODULE_WFH                = 'wfh'

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
    MODULE_DOCUMENTS,
    MODULE_ASSETS,
    MODULE_WFH,
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
    MODULE_DOCUMENTS:       'Document Management',
    MODULE_ASSETS:          'Asset Management',
    MODULE_WFH:             'Work From Home',
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

    # Captured once at signup, editable afterward via CompanyDetailView.patch —
    # none of this feeds provisioning or login; it's account-management
    # context for the platform admin (who to call, what they signed up for),
    # deliberately kept optional so a quick trial signup isn't blocked on it.
    contact_name            = models.CharField(max_length=150, blank=True)
    contact_phone           = models.CharField(max_length=20, blank=True)
    address                 = models.TextField(blank=True)
    gstin                   = models.CharField(max_length=15, blank=True)
    expected_employee_count = models.PositiveIntegerField(null=True, blank=True)
    contract_start_date     = models.DateField(null=True, blank=True)

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
    # A company added with a manual subscription whose payment isn't
    # confirmed yet: only the registry row exists, nothing is queued. Kept
    # separate from 'pending' so sweep_stale_provisioning (pending -> failed
    # after 15 min) and cleanup_failed_tenants never touch it.
    PROVISIONING_AWAITING_PAYMENT = 'awaiting'
    PROVISIONING_STATUS_CHOICES = [
        (PROVISIONING_PENDING, 'Pending'),
        (PROVISIONING_ACTIVE,  'Active'),
        (PROVISIONING_FAILED,  'Failed'),
        (PROVISIONING_AWAITING_PAYMENT, 'Awaiting payment'),
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


# ─── SaaS subscriptions (public schema, like Client) ─────────────────────────

class SubscriptionPlan(models.Model):
    """A sellable plan. `features` are keys from apps.tenants.modules.FEATURES
    (module + display kinds); the module keys among them become the
    company's Client.enabled_modules via apps.tenants.subscriptions.
    Editing a plan never changes existing subscriptions — each subscription
    keeps a snapshot of the plan as assigned."""

    STATUS_DRAFT = 'draft'
    STATUS_ACTIVE = 'active'
    STATUS_INACTIVE = 'inactive'
    STATUS_CHOICES = [(STATUS_DRAFT, 'Draft'), (STATUS_ACTIVE, 'Active'), (STATUS_INACTIVE, 'Inactive')]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    code = models.SlugField(max_length=40, unique=True)
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    price_per_employee = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    currency = models.CharField(max_length=3, default='INR')
    # Billing periods offered, e.g. ["monthly", "yearly"] — informational
    # until billing is approved.
    billing_periods = models.JSONField(default=list, blank=True)
    # GST kept configurable (rate + whether the price includes it).
    gst_rate = models.DecimalField(max_digits=5, decimal_places=2, default=18)
    gst_inclusive = models.BooleanField(default=False)
    min_employees = models.PositiveIntegerField(null=True, blank=True)
    max_employees = models.PositiveIntegerField(null=True, blank=True)
    features = models.JSONField(default=list, blank=True)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default=STATUS_DRAFT)
    is_public = models.BooleanField(default=False)
    display_order = models.PositiveSmallIntegerField(default=0)
    # The internal plan existing companies are moved onto (never public).
    is_legacy = models.BooleanField(default=False)
    updated_by = models.ForeignKey(PlatformAdmin, on_delete=models.SET_NULL, null=True, blank=True,
                                   related_name='+')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'tenants_subscription_plan'
        ordering = ['display_order', 'name']

    def __str__(self) -> str:
        return f'{self.name} ({self.code})'


class CompanySubscription(models.Model):
    """A company's current subscription (one per Client). Plan price and
    features are snapshotted at assignment. Every change is recorded in
    SubscriptionHistory."""

    SOURCE_MANUAL = 'manual'
    SOURCE_WEBSITE = 'website'
    SOURCE_LEGACY = 'legacy'
    SOURCE_CHOICES = [(SOURCE_MANUAL, 'Manual'), (SOURCE_WEBSITE, 'Website'), (SOURCE_LEGACY, 'Legacy')]

    STATUS_ACTIVE = 'active'
    STATUS_INACTIVE = 'inactive'
    STATUS_CHOICES = [(STATUS_ACTIVE, 'Active'), (STATUS_INACTIVE, 'Inactive')]

    # Payment, subscription status and provisioning are independent fields.
    PAYMENT_PENDING = 'pending'
    PAYMENT_PAID = 'paid'
    PAYMENT_PARTIAL = 'partially_paid'
    PAYMENT_FAILED = 'failed'
    PAYMENT_WAIVED = 'waived'
    PAYMENT_CHOICES = [(PAYMENT_PENDING, 'Pending'), (PAYMENT_PAID, 'Paid'), (PAYMENT_PARTIAL, 'Partially paid'),
                       (PAYMENT_FAILED, 'Failed'), (PAYMENT_WAIVED, 'Waived')]

    # Whether the subscription's modules / limits have been applied to the company.
    PROVISION_AWAITING_PAYMENT = 'awaiting_payment'
    PROVISION_PENDING = 'pending'
    PROVISION_SUCCESS = 'success'
    PROVISION_FAILED = 'failed'
    PROVISION_CHOICES = [(PROVISION_AWAITING_PAYMENT, 'Awaiting payment'), (PROVISION_PENDING, 'In progress'),
                         (PROVISION_SUCCESS, 'Success'), (PROVISION_FAILED, 'Failed')]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    client = models.OneToOneField(Client, on_delete=models.CASCADE, related_name='subscription')
    plan = models.ForeignKey(SubscriptionPlan, on_delete=models.PROTECT, related_name='subscriptions')
    source = models.CharField(max_length=10, choices=SOURCE_CHOICES, default=SOURCE_MANUAL)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default=STATUS_ACTIVE)
    starts_on = models.DateField()
    ends_on = models.DateField(null=True, blank=True, help_text='Blank = no end date')
    employee_count = models.PositiveIntegerField(null=True, blank=True)
    billing_period = models.CharField(max_length=10, blank=True, default='')
    # Snapshot of the plan when assigned / last changed.
    plan_name = models.CharField(max_length=100)
    price_per_employee = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    currency = models.CharField(max_length=3, default='INR')
    gst_rate = models.DecimalField(max_digits=5, decimal_places=2, default=18)
    gst_inclusive = models.BooleanField(default=False)
    max_employees = models.PositiveIntegerField(null=True, blank=True)
    plan_features = models.JSONField(default=list, blank=True)
    # Customer-specific overrides (module keys). Not offered in the UI until
    # approved (settings.SUBSCRIPTION_ALLOW_OVERRIDES); legacy subscriptions
    # use extra_modules to keep a company's exact pre-subscription modules.
    extra_modules = models.JSONField(default=list, blank=True)
    removed_modules = models.JSONField(default=list, blank=True)
    notes = models.TextField(blank=True)
    # Payment (recorded manually; see SubscriptionPayment). payment_status is
    # derived from confirmed payments vs amount_due, except 'waived'.
    payment_status = models.CharField(max_length=16, choices=PAYMENT_CHOICES, default=PAYMENT_PENDING)
    amount_due = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    payment_waiver_reason = models.TextField(blank=True)
    provisioning_status = models.CharField(max_length=20, choices=PROVISION_CHOICES, default=PROVISION_PENDING)
    provisioning_error = models.CharField(max_length=255, blank=True)
    provisioned_at = models.DateTimeField(null=True, blank=True)
    # New company awaiting payment: its first admin's login email, used when
    # provisioning starts. Cleared once provisioned.
    pending_admin_email = models.EmailField(blank=True)
    updated_by = models.ForeignKey(PlatformAdmin, on_delete=models.SET_NULL, null=True, blank=True,
                                   related_name='+')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'tenants_company_subscription'

    def __str__(self) -> str:
        return f'{self.client.company_code} — {self.plan_name}'


class SubscriptionHistory(models.Model):
    """Append-only record of subscription changes."""

    EVENT_ASSIGNED = 'assigned'
    EVENT_PLAN_CHANGED = 'plan_changed'
    EVENT_EXTENDED = 'extended'
    EVENT_ACTIVATED = 'activated'
    EVENT_DEACTIVATED = 'deactivated'
    EVENT_PROVISIONING_RETRIED = 'provisioning_retried'
    EVENT_PAYMENT_RECORDED = 'payment_recorded'
    EVENT_PAYMENT_VERIFIED = 'payment_verified'
    EVENT_PAYMENT_REJECTED = 'payment_rejected'
    EVENT_PAYMENT_WAIVED = 'payment_waived'
    EVENT_PAYMENT_WAIVER_REMOVED = 'payment_waiver_removed'
    EVENT_AMOUNT_DUE_CHANGED = 'amount_due_changed'
    EVENT_PROVISIONED = 'provisioned'
    EVENT_PROVISIONING_FAILED = 'provisioning_failed'

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    subscription = models.ForeignKey(CompanySubscription, on_delete=models.CASCADE, related_name='history')
    event = models.CharField(max_length=30)
    before = models.JSONField(default=dict, blank=True)
    after = models.JSONField(default=dict, blank=True)
    note = models.TextField(blank=True)
    admin = models.ForeignKey(PlatformAdmin, on_delete=models.SET_NULL, null=True, blank=True, related_name='+')
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        db_table = 'tenants_subscription_history'
        ordering = ['-created_at']


class SubscriptionPayment(models.Model):
    """A payment received outside the app (UPI, bank transfer, cheque, ...)
    and recorded by a Platform Admin. Counts toward the subscription only
    once confirmed ('verified'). Rows are never edited or deleted — a wrong
    entry is rejected and re-recorded, so the trail stays complete."""

    METHOD_CHOICES = [('upi', 'UPI'), ('bank_transfer', 'Bank transfer'), ('neft', 'NEFT'), ('rtgs', 'RTGS'),
                      ('cash', 'Cash'), ('cheque', 'Cheque'), ('other', 'Other')]

    STATUS_RECORDED = 'recorded'
    STATUS_VERIFIED = 'verified'
    STATUS_REJECTED = 'rejected'
    STATUS_CHOICES = [(STATUS_RECORDED, 'Awaiting confirmation'), (STATUS_VERIFIED, 'Confirmed'),
                      (STATUS_REJECTED, 'Rejected')]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    subscription = models.ForeignKey(CompanySubscription, on_delete=models.PROTECT, related_name='payments')
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    currency = models.CharField(max_length=3, default='INR')
    method = models.CharField(max_length=20, choices=METHOD_CHOICES)
    paid_on = models.DateField()
    reference = models.CharField(max_length=100, blank=True)
    notes = models.TextField(blank=True)
    receipt = models.FileField(upload_to=subscription_payment_receipt_upload_path,
                               storage=AuthenticatedRawMediaCloudinaryStorage(), max_length=255, null=True, blank=True)
    receipt_name = models.CharField(max_length=255, blank=True)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default=STATUS_RECORDED)
    rejection_reason = models.TextField(blank=True)
    recorded_by = models.ForeignKey(PlatformAdmin, on_delete=models.SET_NULL, null=True, blank=True, related_name='+')
    reviewed_by = models.ForeignKey(PlatformAdmin, on_delete=models.SET_NULL, null=True, blank=True, related_name='+')
    reviewed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        db_table = 'tenants_subscription_payment'
        ordering = ['-paid_on', '-created_at']

    def __str__(self) -> str:
        return f'{self.subscription.client.company_code} — {self.amount} {self.currency} ({self.status})'


# ─── Website registrations (public schema) ───────────────────────────────────

class CompanyRegistration(models.Model):
    """A company signing up on the website. Nothing is provisioned until the
    payment is VERIFIED (by the payment gateway integration, never by the
    browser) AND a Platform Admin approves — then the normal provisioning +
    subscription assignment runs (apps.tenants.registrations.approve)."""

    PAYMENT_PENDING = 'pending'
    PAYMENT_PAID = 'paid'
    PAYMENT_FAILED = 'failed'
    PAYMENT_REFUNDED = 'refunded'
    PAYMENT_CHOICES = [(PAYMENT_PENDING, 'Pending'), (PAYMENT_PAID, 'Paid'), (PAYMENT_FAILED, 'Failed'),
                       (PAYMENT_REFUNDED, 'Refunded')]

    APPROVAL_PENDING = 'pending'
    APPROVAL_APPROVED = 'approved'
    APPROVAL_REJECTED = 'rejected'
    APPROVAL_CHOICES = [(APPROVAL_PENDING, 'Pending'), (APPROVAL_APPROVED, 'Approved'),
                        (APPROVAL_REJECTED, 'Rejected')]

    REFUND_NONE = ''
    REFUND_PENDING = 'pending'          # rejected after payment; refund per approved policy
    REFUND_DONE = 'refunded'

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    reference = models.CharField(max_length=20, unique=True)
    company_name = models.CharField(max_length=200)
    company_code = models.CharField(max_length=20, db_index=True)
    contact_name = models.CharField(max_length=150)
    admin_email = models.EmailField()
    contact_phone = models.CharField(max_length=20)
    address = models.TextField(blank=True)
    gstin = models.CharField(max_length=15, blank=True)
    employee_count = models.PositiveIntegerField()
    plan = models.ForeignKey(SubscriptionPlan, on_delete=models.PROTECT, related_name='registrations')
    billing_period = models.CharField(max_length=10, default='monthly')
    # Amount worked out on the server from the plan when registering.
    plan_name = models.CharField(max_length=100)
    # The plan's features when the customer registered — what they pay for,
    # even if the plan is edited before approval.
    plan_features = models.JSONField(default=list, blank=True)
    price_per_employee = models.DecimalField(max_digits=10, decimal_places=2)
    months = models.PositiveSmallIntegerField(default=1)
    subtotal = models.DecimalField(max_digits=12, decimal_places=2)
    gst_rate = models.DecimalField(max_digits=5, decimal_places=2)
    gst_inclusive = models.BooleanField(default=False)
    gst_amount = models.DecimalField(max_digits=12, decimal_places=2)
    total = models.DecimalField(max_digits=12, decimal_places=2)
    currency = models.CharField(max_length=3, default='INR')
    payment_status = models.CharField(max_length=10, choices=PAYMENT_CHOICES, default=PAYMENT_PENDING)
    paid_at = models.DateTimeField(null=True, blank=True)
    approval_status = models.CharField(max_length=10, choices=APPROVAL_CHOICES, default=APPROVAL_PENDING)
    rejection_reason = models.TextField(blank=True)
    refund_status = models.CharField(max_length=10, blank=True, default='')
    reviewed_by = models.ForeignKey(PlatformAdmin, on_delete=models.SET_NULL, null=True, blank=True, related_name='+')
    reviewed_at = models.DateTimeField(null=True, blank=True)
    client = models.OneToOneField(Client, on_delete=models.SET_NULL, null=True, blank=True,
                                  related_name='registration')
    terms_accepted_at = models.DateTimeField()
    signup_ip = models.GenericIPAddressField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'tenants_company_registration'
        ordering = ['-created_at']

    def __str__(self) -> str:
        return f'{self.reference} {self.company_code}'


class PaymentTransaction(models.Model):
    """A payment attempt for a registration, as reported by the payment
    gateway integration (apps.tenants.payments). Never written from browser
    input. payment_id is unique so a payment can be recorded only once."""

    STATUS_CREATED = 'created'
    STATUS_PAID = 'paid'
    STATUS_FAILED = 'failed'
    STATUS_REFUNDED = 'refunded'

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    registration = models.ForeignKey(CompanyRegistration, on_delete=models.PROTECT, related_name='payments')
    gateway = models.CharField(max_length=30)
    order_id = models.CharField(max_length=100, db_index=True)
    payment_id = models.CharField(max_length=100, null=True, blank=True, unique=True)
    event_id = models.CharField(max_length=100, null=True, blank=True, unique=True)
    amount_minor = models.BigIntegerField(help_text='Amount in the smallest unit (paise)')
    currency = models.CharField(max_length=3)
    status = models.CharField(max_length=10, default=STATUS_CREATED)
    failure_reason = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'tenants_payment_transaction'
        ordering = ['-created_at']


class PlatformNotification(models.Model):
    """In-app notification for one Platform Admin (bell in Platform Admin)."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    recipient = models.ForeignKey(PlatformAdmin, on_delete=models.CASCADE, related_name='notifications')
    kind = models.CharField(max_length=40)
    title = models.CharField(max_length=200)
    message = models.TextField(blank=True)
    link = models.CharField(max_length=300, blank=True)
    is_read = models.BooleanField(default=False, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        db_table = 'tenants_platform_notification'
        ordering = ['-created_at']

