from __future__ import annotations

import re
import uuid
from datetime import timedelta

from django.conf import settings
from django.contrib.auth.hashers import check_password as _check_hash
from django.contrib.auth.hashers import make_password as _make_hash
from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin
from django.db import models, transaction
from django.db.models import F
from django.utils import timezone


# ─── Role & Permission ────────────────────────────────────────────────────────

class Role(models.Model):
    name             = models.CharField(max_length=50, unique=True)
    display_name     = models.CharField(max_length=100)
    is_active        = models.BooleanField(default=True)
    can_manage_team  = models.BooleanField(
        default=False,
        help_text='Users with this role appear in manager dropdowns and can manage a team.',
    )
    can_manage_branch = models.BooleanField(
        default=False,
        help_text=(
            'Users with this role have unconditional access to every employee, '
            'request, and record within their own branch — not limited to '
            'employees specifically assigned to them (unlike HR) or their direct '
            'reports (unlike a manager). Scoped to one branch, unlike settings.edit '
            'which is org-wide.'
        ),
    )
    created_at   = models.DateTimeField(auto_now_add=True, null=True)
    updated_at   = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'hrms_roles'

    def __str__(self) -> str:
        return self.display_name


class Permission(models.Model):
    module   = models.CharField(max_length=50)
    action   = models.CharField(max_length=20)
    codename = models.CharField(max_length=100, unique=True)

    class Meta:
        db_table = 'hrms_permissions'
        ordering = ['module', 'action']
        indexes = [
            models.Index(fields=['module', 'action'], name='permission_module_action_idx'),
        ]

    def __str__(self) -> str:
        return self.codename


class RolePermission(models.Model):
    role       = models.ForeignKey(Role,       on_delete=models.CASCADE, related_name='role_permissions')
    permission = models.ForeignKey(Permission, on_delete=models.CASCADE, related_name='role_permissions')
    granted_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table      = 'hrms_role_permissions'
        unique_together = ('role', 'permission')

    def __str__(self) -> str:
        return f'{self.role.name} → {self.permission.codename}'


# ─── User ─────────────────────────────────────────────────────────────────────

class UserManager(BaseUserManager):
    def create_user(self, email: str, password: str | None = None, **extra_fields) -> User:
        if not email:
            raise ValueError('Email address is required')
        email = self.normalize_email(email)
        user  = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email: str, password: str | None = None, **extra_fields) -> User:
        extra_fields.setdefault('is_staff',           True)
        extra_fields.setdefault('is_superuser',       True)
        extra_fields.setdefault('must_change_password', False)
        if not extra_fields.get('is_staff'):
            raise ValueError('Superuser must have is_staff=True.')
        if not extra_fields.get('is_superuser'):
            raise ValueError('Superuser must have is_superuser=True.')
        if 'role' not in extra_fields:
            try:
                extra_fields['role'] = Role.objects.get(name='system_admin')
            except Role.DoesNotExist:
                pass
        return self.create_user(email, password, **extra_fields)


class User(AbstractBaseUser, PermissionsMixin):

    ONBOARDING_PENDING   = 'pending'
    ONBOARDING_DRAFT     = 'draft'
    ONBOARDING_SUBMITTED = 'submitted'
    ONBOARDING_COMPLETE  = 'complete'
    ONBOARDING_REJECTED  = 'rejected'
    ONBOARDING_CHOICES   = [
        (ONBOARDING_PENDING,   'Pending'),
        (ONBOARDING_DRAFT,     'In Progress'),
        (ONBOARDING_SUBMITTED, 'Submitted — awaiting approval'),
        (ONBOARDING_COMPLETE,  'Complete'),
        (ONBOARDING_REJECTED,  'Needs Revision'),
    ]

    ASSESSMENT_PENDING  = 'pending'
    ASSESSMENT_COMPLETE = 'complete'
    ASSESSMENT_CHOICES  = [
        (ASSESSMENT_PENDING,  'Pending'),
        (ASSESSMENT_COMPLETE, 'Complete'),
    ]

    # Profile photo — a plain displayable image (shown in the sidebar, header,
    # and Profile page), unrelated to apps.attendance's face-ID verification
    # feature which stores a numeric face descriptor, never an image.
    PROFILE_PHOTO_ALLOWED_MIME_TYPES = {'image/jpeg', 'image/png'}
    PROFILE_PHOTO_MIN_SIZE           = 100 * 1024   # 100 KB
    PROFILE_PHOTO_MAX_SIZE           = 200 * 1024   # 200 KB

    id          = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    email       = models.EmailField(unique=True)
    full_name   = models.CharField(max_length=150)
    role        = models.ForeignKey(
                      Role,
                      on_delete=models.SET_NULL,
                      null=True,
                      blank=True,
                      related_name='users',
                  )
    employee_id     = models.CharField(max_length=20, blank=True, db_index=True)
    department      = models.CharField(max_length=100, blank=True)
    designation     = models.CharField(max_length=100, blank=True)
    branch          = models.CharField(max_length=100, blank=True)
    phone           = models.CharField(max_length=20, blank=True)
    date_of_joining = models.DateField(null=True, blank=True)
    reporting_manager = models.ForeignKey(
                            'self',
                            on_delete=models.SET_NULL,
                            null=True,
                            blank=True,
                            related_name='direct_reports',
                        )
    hr = models.ForeignKey(
             'self',
             on_delete=models.SET_NULL,
             null=True,
             blank=True,
             related_name='hr_employees',
         )
    # Manager-role users have no reporting_manager (they ARE the manager for
    # others — see _auto_assign_managers) and HR-role users often auto-assign
    # to their branch's manager but may end up with none either. This gives
    # Manager/HR profiles a designated approver for their own requests (e.g.
    # separation) instead of leaving that stage permanently unreachable.
    reporting_approver = models.ForeignKey(
                              'self',
                              on_delete=models.SET_NULL,
                              null=True,
                              blank=True,
                              related_name='approver_for',
                          )
    is_active       = models.BooleanField(default=True)
    is_staff      = models.BooleanField(default=False)
    must_change_password    = models.BooleanField(default=True)
    onboarding_status       = models.CharField(
                                  max_length=20,
                                  choices=ONBOARDING_CHOICES,
                                  default=ONBOARDING_PENDING,
                              )
    assessment_status       = models.CharField(
                                  max_length=20,
                                  choices=ASSESSMENT_CHOICES,
                                  default=ASSESSMENT_PENDING,
                              )
    failed_login_attempts   = models.PositiveSmallIntegerField(default=0)
    locked_until            = models.DateTimeField(null=True, blank=True)
    last_login_ip           = models.GenericIPAddressField(null=True, blank=True)
    profile_photo           = models.ImageField(upload_to='profile_photos/', null=True, blank=True)
    date_joined  = models.DateTimeField(auto_now_add=True)
    updated_at   = models.DateTimeField(auto_now=True)

    USERNAME_FIELD  = 'email'
    REQUIRED_FIELDS = ['full_name']

    objects = UserManager()

    class Meta:
        db_table = 'hrms_users'
        indexes = [
            models.Index(fields=['role', 'is_active'],  name='user_role_active_idx'),
            models.Index(fields=['department'],          name='user_department_idx'),
            models.Index(fields=['designation'],         name='user_designation_idx'),
            # Phase 4: `branch` is a plain CharField with no index at all today,
            # despite being filtered repeatedly (payroll cycle scoping, branch
            # admin screens, dashboard counts) — matches the existing
            # (role, is_active) precedent above.
            models.Index(fields=['branch', 'is_active'], name='user_branch_active_idx'),
            # Phase 4: onboarding_status is filtered alongside is_active in
            # several dashboard aggregate-count queries (onboarding funnel
            # widgets) with no supporting index today.
            models.Index(fields=['onboarding_status', 'is_active'], name='user_onboard_active_idx'),
        ]

    def __str__(self) -> str:
        return self.email

    # ── Lockout helpers ───────────────────────────────────────────────────────

    def is_locked(self) -> bool:
        """Return True if the account is currently locked out."""
        if not self.locked_until:
            return False
        if timezone.now() < self.locked_until:
            return True
        # Lock has expired — clear it atomically (fire-and-forget; failure is harmless)
        User.objects.filter(pk=self.pk, locked_until=self.locked_until).update(
            locked_until=None,
            failed_login_attempts=0,
        )
        self.locked_until           = None
        self.failed_login_attempts  = 0
        return False

    @transaction.atomic
    def increment_failed_login(self) -> None:

        max_attempts    = getattr(settings, 'LOGIN_MAX_ATTEMPTS', 5)
        lockout_minutes = getattr(settings, 'LOGIN_LOCKOUT_MINUTES', 30)

        # Atomic increment — safe under concurrent requests
        User.objects.filter(pk=self.pk).update(
            failed_login_attempts=F('failed_login_attempts') + 1
        )
        self.refresh_from_db(fields=['failed_login_attempts'])

        if self.failed_login_attempts >= max_attempts:
            lock_until = timezone.now() + timedelta(minutes=lockout_minutes)
            User.objects.filter(pk=self.pk).update(locked_until=lock_until)
            self.locked_until = lock_until

    def reset_failed_login(self, ip_address: str | None = None) -> None:
        """Reset lockout state on successful login."""
        update_fields = {
            'failed_login_attempts': 0,
            'locked_until': None,
        }
        if ip_address:
            update_fields['last_login_ip'] = ip_address
        User.objects.filter(pk=self.pk).update(**update_fields)
        self.failed_login_attempts  = 0
        self.locked_until           = None
        if ip_address:
            self.last_login_ip = ip_address


# ─── Organisation Structure ───────────────────────────────────────────────────

class Department(models.Model):
    name        = models.CharField(max_length=100, unique=True)
    description = models.CharField(max_length=300, blank=True)
    manager     = models.ForeignKey(
                      'User',
                      on_delete=models.SET_NULL,
                      null=True, blank=True,
                      related_name='managed_departments',
                  )
    is_active   = models.BooleanField(default=True)
    created_at  = models.DateTimeField(auto_now_add=True)
    updated_at  = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'hrms_departments'
        ordering = ['name']

    def __str__(self) -> str:
        return self.name


class Designation(models.Model):
    name        = models.CharField(max_length=100)
    department  = models.ForeignKey(
                      Department, on_delete=models.CASCADE, related_name='designations'
                  )
    level       = models.PositiveIntegerField(
        default=0,
        help_text=(
            'Seniority level used to validate promotions (higher = more senior). '
            '0 means "not yet configured" — promotion hierarchy validation is '
            'skipped for a designation until it is given a real level > 0.'
        ),
    )
    is_active   = models.BooleanField(default=True)
    created_at  = models.DateTimeField(auto_now_add=True)
    updated_at  = models.DateTimeField(auto_now=True)

    class Meta:
        db_table        = 'hrms_designations'
        unique_together = ('name', 'department')
        ordering        = ['name']

    def __str__(self) -> str:
        return f'{self.name} ({self.department.name})'


class PromotionRecord(models.Model):
    """Immutable audit trail of designation/role changes made through
    EmployeeDetailView.put(). One row per PUT call that actually changed
    designation and/or role — never updated or deleted after creation.

    Designation/role are snapshotted as plain strings (matching
    User.designation, a bare CharField with no FK) rather than FKs, so a
    later rename/deletion of a Designation/Role never rewrites history.
    """
    employee = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name='promotion_records',
    )
    previous_designation = models.CharField(max_length=100, blank=True)
    new_designation = models.CharField(max_length=100, blank=True)
    previous_role = models.CharField(max_length=50, blank=True)
    new_role = models.CharField(max_length=50, blank=True)
    effective_date = models.DateField()
    remarks = models.TextField(blank=True, default='')
    promoted_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='promotions_made',
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'hrms_promotion_records'
        ordering = ['-effective_date', '-created_at']
        indexes = [
            models.Index(fields=['employee', '-effective_date'], name='promo_employee_effdate_idx'),
        ]

    def __str__(self) -> str:
        return f'{self.employee.full_name}: {self.previous_designation} -> {self.new_designation} ({self.effective_date})'


# ─── OTP Verification ─────────────────────────────────────────────────────────

class OTPVerification(models.Model):
    
    user       = models.ForeignKey(User, on_delete=models.CASCADE, related_name='otps')
    otp        = models.CharField(max_length=128)   # stores the hash, not the plain OTP
    attempts   = models.PositiveSmallIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField(db_index=True)
    is_used    = models.BooleanField(default=False, db_index=True)

    class Meta:
        db_table = 'otp_verifications'
        ordering = ['-created_at']
        indexes  = [
            models.Index(fields=['user', 'is_used', 'expires_at']),
        ]

    def __str__(self) -> str:
        return f'OTP for {self.user.email} (used={self.is_used})'

    def is_valid(self) -> bool:
        max_attempts = getattr(settings, 'OTP_MAX_ATTEMPTS', 5)
        return (
            not self.is_used
            and self.attempts <= max_attempts
            and timezone.now() < self.expires_at
        )

    def check_otp(self, plain_otp: str) -> bool:
        """Verify a plain OTP against the stored hash."""
        return _check_hash(plain_otp, self.otp)

    @classmethod
    @transaction.atomic
    def create_for_user(cls, user: User) -> tuple[OTPVerification, str]:
       
        from apps.accounts.utils import generate_otp  # avoid circular import

        cls.objects.filter(user=user, is_used=False).update(is_used=True)

        expiry_minutes = getattr(settings, 'OTP_EXPIRY_MINUTES', 10)
        plain_otp      = generate_otp()

        otp_obj = cls.objects.create(
            user       = user,
            otp        = _make_hash(plain_otp),   # store the hash
            expires_at = timezone.now() + timedelta(minutes=expiry_minutes),
        )
        return otp_obj, plain_otp


# ─── Password Reset Token ──────────────────────────────────────────────────────

class PasswordResetToken(models.Model):
    id         = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user       = models.ForeignKey(User, on_delete=models.CASCADE, related_name='reset_tokens')
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField(db_index=True)
    is_used    = models.BooleanField(default=False, db_index=True)

    class Meta:
        db_table = 'hrms_password_reset_tokens'

    def __str__(self) -> str:
        return f'ResetToken({self.user.email}, used={self.is_used})'

    def is_valid(self) -> bool:
        return not self.is_used and timezone.now() < self.expires_at

    @classmethod
    @transaction.atomic
    def create_for_user(cls, user: User) -> PasswordResetToken:
        """Invalidate all outstanding tokens for this user then issue a new one."""
        cls.objects.filter(user=user, is_used=False).update(is_used=True)
        return cls.objects.create(
            user       = user,
            expires_at = timezone.now() + timedelta(minutes=60),
        )


# ─── Audit Log ────────────────────────────────────────────────────────────────

class AuditLog(models.Model):
    """Immutable append-only audit trail. User FK is SET_NULL so logs survive user deletion."""
    user       = models.ForeignKey(
                     User, on_delete=models.SET_NULL, null=True, blank=True,
                     related_name='audit_logs',
                 )
    action     = models.CharField(max_length=100)
    module     = models.CharField(max_length=50)
    object_id  = models.CharField(max_length=100, blank=True)
    changes    = models.JSONField(default=dict)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    branch     = models.CharField(max_length=100, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    # The branch this event pertains to (the affected employee/candidate/
    # document/cycle's branch) — NOT necessarily the acting user's own
    # branch, e.g. a system_admin editing a Mumbai employee. Falls back to
    # the actor's branch at call sites that haven't been updated to pass an
    # explicit target branch, and for actions with no meaningful target
    # (login/logout, settings, role management). Plain branch-name string,
    # matching User.branch's convention, so it can be compared directly
    # against request.user.branch for HR's branch-scoped audit view.
    branch     = models.CharField(max_length=100, blank=True, default='')

    class Meta:
        db_table = 'hrms_audit_logs'
        ordering = ['-created_at']
        indexes = [
            # Phase 4: AuditLogListView / SystemAdminAuditLogsView both filter
            # by module combined with a created_at date-range, on an
            # ever-growing, unbounded table — the standalone created_at index
            # alone can't serve the module-scoped queries efficiently.
            models.Index(fields=['module', 'created_at'], name='auditlog_module_created_idx'),
        ]

    def __str__(self) -> str:
        actor = self.user.email if self.user_id else 'system'
        return f'[{self.module}] {self.action} by {actor}'


# ─── SMTP Settings ────────────────────────────────────────────────────────────

class SMTPSettings(models.Model):

    class SMTPType(models.TextChoices):
        LOCAL  = 'local',  'Local (Gmail / Custom SMTP)'
        SERVER = 'server', 'Server (Dedicated Mail Server)'

    class Priority(models.TextChoices):
        NORMAL = 'normal', 'Normal'
        HIGH   = 'high',   'High'
        LOW    = 'low',    'Low'

    class ReceiverEmailType(models.TextChoices):
        EMAIL_ID          = 'email_id',          'Email ID'
        PERSONAL_EMAIL_ID = 'personal_email_id', 'Personal Email ID'

    name                = models.CharField(max_length=100, unique=True)
    smtp_type           = models.CharField(
                              max_length=10,
                              choices=SMTPType.choices,
                              default=SMTPType.LOCAL,
                          )
    host                = models.CharField(max_length=255)
    port                = models.PositiveIntegerField(default=587)
    username            = models.CharField(max_length=255)   # may be email OR plain username
    password            = models.CharField(max_length=255)
    use_tls             = models.BooleanField(default=True)
    sender_name         = models.CharField(max_length=255, blank=True)
    from_email          = models.EmailField(max_length=255)
    bcc_email           = models.EmailField(max_length=255, blank=True)
    priority            = models.CharField(
                              max_length=10, choices=Priority.choices, default=Priority.NORMAL
                          )
    receiver_email_type = models.CharField(
                              max_length=20,
                              choices=ReceiverEmailType.choices,
                              default=ReceiverEmailType.EMAIL_ID,
                          )
    is_active           = models.BooleanField(default=False)
    updated_at          = models.DateTimeField(auto_now=True)
    updated_by          = models.ForeignKey(
                              User, on_delete=models.SET_NULL, null=True, blank=True,
                              related_name='smtp_updates',
                          )

    class Meta:
        db_table         = 'hrms_smtp_settings'
        verbose_name     = 'SMTP Settings'
        verbose_name_plural = 'SMTP Settings'

    def __str__(self) -> str:
        status = 'active' if self.is_active else 'inactive'
        return f'{self.name} — {status}'

    @classmethod
    def get_active(cls) -> SMTPSettings | None:
        return cls.objects.filter(is_active=True).first()

    @transaction.atomic
    def activate(self) -> None:
        """Activate this config and deactivate the other — atomically."""
        SMTPSettings.objects.exclude(pk=self.pk).update(is_active=False)
        SMTPSettings.objects.filter(pk=self.pk).update(is_active=True)
        self.is_active = True


# ─── Email Templates ──────────────────────────────────────────────────────────

class EmailTemplateCategory(models.Model):
    name         = models.CharField(max_length=50, unique=True)
    display_name = models.CharField(max_length=100)
    is_builtin   = models.BooleanField(default=False)
    order        = models.PositiveSmallIntegerField(default=0)

    class Meta:
        db_table = 'hrms_email_template_categories'
        ordering = ['order', 'display_name']

    def __str__(self) -> str:
        return self.display_name


class EmailTemplate(models.Model):

    name                = models.CharField(max_length=100, unique=True)
    display_name        = models.CharField(max_length=200)
    description         = models.CharField(max_length=500, blank=True)
    template_type       = models.CharField(max_length=50, default='notification')
    subject             = models.CharField(max_length=500)
    body                = models.TextField()
    is_active           = models.BooleanField(default=True)
    is_builtin          = models.BooleanField(default=False)
    available_variables = models.JSONField(
                              default=list,
                              help_text='List of {VARIABLE} names supported by this template.',
                          )
    updated_at          = models.DateTimeField(auto_now=True)
    updated_by          = models.ForeignKey(
                              User,
                              on_delete=models.SET_NULL,
                              null=True,
                              blank=True,
                              related_name='email_template_updates',
                          )

    class Meta:
        db_table = 'hrms_email_templates'
        ordering = ['template_type', 'display_name']

    def __str__(self) -> str:
        return self.display_name

    def render(self, context: dict) -> tuple[str, str]:
        subject = self.subject
        body    = self.body
        for key, value in context.items():
            # Strip CR/LF to prevent SMTP header injection via subject line
            safe_value  = str(value).replace('\r', '').replace('\n', ' ')
            placeholder = '{' + key + '}'
            subject     = subject.replace(placeholder, safe_value)
            body        = body.replace(placeholder, safe_value)
        return subject, body


# ─── Company (singleton) ──────────────────────────────────────────────────────

class Company(models.Model):
    """Single legal entity. Only one record ever exists in this table."""

    MONTH_CHOICES = [
        ('January',   'January'),   ('February', 'February'), ('March',    'March'),
        ('April',     'April'),     ('May',       'May'),      ('June',     'June'),
        ('July',      'July'),      ('August',    'August'),   ('September','September'),
        ('October',   'October'),   ('November',  'November'), ('December', 'December'),
    ]

    company_name   = models.CharField(max_length=200)
    trade_name     = models.CharField(max_length=200, blank=True)
    logo           = models.ImageField(upload_to='company/', null=True, blank=True)
    gstin          = models.CharField(max_length=15)
    cin            = models.CharField(max_length=21)
    pan            = models.CharField(max_length=10)
    tan            = models.CharField(max_length=10)
    address        = models.TextField(max_length=500)
    city           = models.CharField(max_length=100)
    state          = models.CharField(max_length=100)
    pin_code       = models.CharField(max_length=6)
    website        = models.CharField(max_length=255, blank=True)
    official_phone = models.CharField(max_length=15, blank=True)
    portal_url     = models.CharField(
                         max_length=255, blank=True,
                         help_text='Employee onboarding portal URL sent in invitation emails.',
                     )
    financial_year_start_month = models.CharField(
                         max_length=10,
                         choices=MONTH_CHOICES,
                         default='April',
                         help_text='First month of the financial year (e.g. "April" for Apr–Mar).',
                     )
    updated_at     = models.DateTimeField(auto_now=True)
    updated_by     = models.ForeignKey(
                         User,
                         on_delete=models.SET_NULL,
                         null=True,
                         blank=True,
                         related_name='company_updates',
                     )

    class Meta:
        db_table = 'hrms_company'

    def __str__(self) -> str:
        return self.company_name


# ─── Employee Code Settings (singleton) ──────────────────────────────────────


class EmployeeCodeSettings(models.Model):
    """Singleton row (pk=1) that governs how employee IDs are generated."""
    prefix        = models.CharField(max_length=10, default='RSS')
    padding       = models.PositiveSmallIntegerField(default=5)
    next_sequence = models.PositiveIntegerField(default=1)
    updated_at    = models.DateTimeField(auto_now=True)
    updated_by    = models.ForeignKey(
                        User,
                        on_delete=models.SET_NULL,
                        null=True,
                        blank=True,
                        related_name='employee_code_updates',
                    )

    class Meta:
        db_table = 'hrms_employee_code_settings'

    def __str__(self) -> str:
        return f'{self.prefix} (format: prefix + initial + DD + month + surname)'

    @classmethod
    def get(cls) -> 'EmployeeCodeSettings':
        obj, _ = cls.objects.get_or_create(
            pk=1,
            defaults={'prefix': 'RSS', 'padding': 5, 'next_sequence': 1},
        )
        return obj

    @classmethod
    def generate_employee_id(
        cls,
        first_name: str,
        last_name: str,
        date_of_joining=None,
    ) -> str:
        """Generate sequential ID: prefix + zero-padded sequence number.

        Format example: RSS + 00020 (padding=5, next_sequence=20) → RSS00020
        Increments next_sequence atomically after each ID is claimed.
        """
        from django.db import transaction as _tx

        with _tx.atomic():
            cfg = cls.objects.select_for_update().get_or_create(
                pk=1,
                defaults={'prefix': 'RSS', 'padding': 5, 'next_sequence': 1},
            )[0]
            prefix   = cfg.prefix or 'RSS'
            seq      = str(cfg.next_sequence).zfill(cfg.padding)
            emp_id   = f'{prefix}{seq}'
            cfg.next_sequence += 1
            cfg.save(update_fields=['next_sequence', 'updated_at'])
        return emp_id


# ─── Birthday Settings (singleton) ───────────────────────────────────────────

class BirthdaySettings(models.Model):
    """Singleton row (pk=1) that governs the automatic birthday wishes feature.

    The birthday email's subject/body is intentionally NOT duplicated here —
    it's already admin-editable via the 'birthday_wish' EmailTemplate row
    (Settings → Email Templates). This model only covers what that page
    doesn't: the master on/off switch and the dashboard/notification copy.
    """
    is_enabled = models.BooleanField(default=True)
    banner_message_template = models.TextField(
        default='We wish you a wonderful year filled with happiness, good '
                'health, success, and prosperity. Have an amazing birthday! 🎂',
    )
    employee_notification_template = models.TextField(
        default='We wish you a wonderful birthday and a successful year ahead.',
    )
    team_notification_template = models.TextField(
        default="Today is {employee_name}'s birthday. Take a moment to wish "
                'your teammate a wonderful birthday.',
    )
    manager_notification_template = models.TextField(
        default="Today is {employee_name}'s birthday. Your team member is "
                'celebrating their birthday today.',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    updated_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='birthday_settings_updates',
    )

    class Meta:
        db_table = 'hrms_birthday_settings'

    def __str__(self) -> str:
        return 'Birthday Settings (enabled)' if self.is_enabled else 'Birthday Settings (disabled)'

    @classmethod
    def get(cls) -> 'BirthdaySettings':
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj


# ─── Document Center ──────────────────────────────────────────────────────────

class Document(models.Model):
    CATEGORY_POLICY   = 'policy'
    CATEGORY_FORM     = 'form'
    CATEGORY_TEMPLATE = 'template'
    CATEGORY_OTHER    = 'other'
    CATEGORY_CHOICES  = [
        (CATEGORY_POLICY,   'Policy'),
        (CATEGORY_FORM,     'Form'),
        (CATEGORY_TEMPLATE, 'Template'),
        (CATEGORY_OTHER,    'Other'),
    ]

    MIME_TO_TYPE = {
        'application/pdf':                                                            'PDF',
        'application/msword':                                                         'DOC',
        'application/vnd.openxmlformats-officedocument.wordprocessingml.document':   'DOCX',
        'application/vnd.ms-excel':                                                   'XLS',
        'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet':         'XLSX',
        'application/vnd.ms-powerpoint':                                              'PPT',
        'application/vnd.openxmlformats-officedocument.presentationml.presentation': 'PPTX',
        'image/jpeg': 'JPG',
        'image/png':  'PNG',
        'text/plain': 'TXT',
        'text/csv':   'CSV',
    }
    ALLOWED_MIME_TYPES = set(MIME_TO_TYPE.keys())
    MAX_FILE_SIZE      = 25 * 1024 * 1024   # 25 MB

    title       = models.CharField(max_length=200)
    description = models.TextField(blank=True, default='')
    category    = models.CharField(max_length=20, choices=CATEGORY_CHOICES, default=CATEGORY_OTHER)
    file        = models.FileField(upload_to='documents/%Y/%m/')
    file_name   = models.CharField(max_length=255)
    file_type   = models.CharField(max_length=10)       # PDF / DOCX / XLSX …
    file_size   = models.PositiveBigIntegerField()       # bytes
    branch      = models.ForeignKey(
                      'branch.Branch',
                      on_delete=models.SET_NULL,
                      null=True, blank=True,
                      related_name='documents',
                  )
    uploaded_by = models.ForeignKey(
                      User,
                      on_delete=models.SET_NULL,
                      null=True,
                      related_name='uploaded_documents',
                  )
    uploaded_at = models.DateTimeField(auto_now_add=True)
    updated_at  = models.DateTimeField(auto_now=True)
    is_active   = models.BooleanField(default=True)

    class Meta:
        db_table = 'hrms_documents'
        ordering = ['-uploaded_at']
        indexes  = [
            models.Index(fields=['category'],    name='doc_category_idx'),
            models.Index(fields=['branch'],      name='doc_branch_idx'),
            models.Index(fields=['uploaded_at'], name='doc_uploaded_at_idx'),
        ]

    def __str__(self) -> str:
        return self.title


# ─── Employee Profile (onboarding wizard data) ────────────────────────────────

class EmployeeProfile(models.Model):
    GENDER_MALE    = 'male'
    GENDER_FEMALE  = 'female'
    GENDER_OTHER   = 'other'
    GENDER_CHOICES = [
        (GENDER_MALE,   'Male'),
        (GENDER_FEMALE, 'Female'),
        (GENDER_OTHER,  'Other / Prefer not to say'),
    ]

    MARITAL_SINGLE   = 'single'
    MARITAL_MARRIED  = 'married'
    MARITAL_DIVORCED = 'divorced'
    MARITAL_WIDOWED  = 'widowed'
    MARITAL_CHOICES  = [
        (MARITAL_SINGLE,   'Single'),
        (MARITAL_MARRIED,  'Married'),
        (MARITAL_DIVORCED, 'Divorced'),
        (MARITAL_WIDOWED,  'Widowed'),
    ]

    BLOOD_CHOICES = [
        ('A+', 'A+'), ('A-', 'A-'), ('B+', 'B+'), ('B-', 'B-'),
        ('O+', 'O+'), ('O-', 'O-'), ('AB+', 'AB+'), ('AB-', 'AB-'),
    ]

    ACCOUNT_SAVINGS = 'savings'
    ACCOUNT_CURRENT = 'current'
    ACCOUNT_CHOICES = [
        (ACCOUNT_SAVINGS, 'Savings'),
        (ACCOUNT_CURRENT, 'Current'),
    ]

    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')

    # Personal
    date_of_birth      = models.DateField(null=True, blank=True)
    gender             = models.CharField(max_length=10, choices=GENDER_CHOICES, blank=True)
    marital_status     = models.CharField(max_length=20, choices=MARITAL_CHOICES, blank=True)
    father_name        = models.CharField(max_length=150, blank=True)
    blood_group        = models.CharField(max_length=5, choices=BLOOD_CHOICES, blank=True)
    current_address    = models.TextField(blank=True)
    permanent_address  = models.TextField(blank=True)

    # Education
    highest_qualification = models.CharField(max_length=200, blank=True)
    institution           = models.CharField(max_length=200, blank=True)
    year_of_passing       = models.PositiveSmallIntegerField(null=True, blank=True)
    specialization        = models.CharField(max_length=200, blank=True)

    # Experience
    total_experience_years = models.DecimalField(max_digits=4, decimal_places=1, null=True, blank=True)
    previous_employer      = models.CharField(max_length=200, blank=True)
    previous_designation   = models.CharField(max_length=200, blank=True)
    leaving_reason         = models.TextField(blank=True)

    # Bank
    account_number      = models.CharField(max_length=20, blank=True)
    ifsc_code           = models.CharField(max_length=11, blank=True)
    bank_name           = models.CharField(max_length=200, blank=True)
    bank_branch_name    = models.CharField(max_length=200, blank=True)
    account_holder_name = models.CharField(max_length=150, blank=True)
    account_type        = models.CharField(max_length=10, choices=ACCOUNT_CHOICES, blank=True)

    # Statutory identity — PII requiring encryption at rest (see CLAUDE.md §3);
    # stored as plain CharField today, matching this model's other sensitive
    # fields (account_number, ifsc_code) — no field-level encryption exists
    # yet anywhere in this codebase.
    name_as_per_aadhar = models.CharField(max_length=150, blank=True, help_text='Name exactly as printed on the Aadhaar card')
    uan_number         = models.CharField(max_length=12, blank=True, help_text='12-digit Universal Account Number issued by EPFO')
    pan_number         = models.CharField(
        max_length=10, blank=True,
        help_text='10-character PAN (e.g. ABCDE1234F) — unique per person, PII requiring encryption at rest.',
    )

    # Emergency Contact
    emergency_name         = models.CharField(max_length=150, blank=True)
    emergency_relationship = models.CharField(max_length=50, blank=True)
    emergency_phone        = models.CharField(max_length=20, blank=True)
    emergency_email        = models.EmailField(blank=True)

    # Birthday wish tracking
    birthday_wish_sent_year = models.PositiveSmallIntegerField(
        null=True, blank=True,
        help_text='Year in which the last birthday wish email was sent. '
                  'Used to prevent duplicate sends on Celery beat retries.',
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'hrms_employee_profiles'

    def __str__(self) -> str:
        return f'Profile — {self.user.email}'


PAN_RE = re.compile(r'^[A-Z]{5}[0-9]{4}[A-Z]$')


def normalize_and_validate_pan(value: str) -> str:
    """
    Uppercase/strip a PAN and check its format (5 letters, 4 digits, 1 letter
    — e.g. ABCDE1234F). Raises ValueError with a user-facing message if
    invalid. Shared by every entry point that can set pan_number (onboarding
    approval, self-service profile, bulk import) so the format check can
    never drift between them.
    """
    value = value.strip().upper()
    if not PAN_RE.match(value):
        raise ValueError('Enter a valid PAN (e.g. ABCDE1234F) — 5 letters, 4 digits, 1 letter.')
    return value


def find_conflicting_pan_profile(pan_number: str, exclude_profile_pk=None) -> 'EmployeeProfile | None':
    """
    Return the other EmployeeProfile already holding this PAN, if any.

    PAN is a permanent government ID tied to one real person for life —
    unlike email, it can't legitimately be re-entered differently, so a
    match here always means the same person is being registered twice
    (e.g. re-hired under a new email in a different branch), not a
    coincidence. Global check, not branch-scoped, for exactly that reason.
    """
    qs = EmployeeProfile.objects.filter(pan_number=pan_number).select_related('user')
    if exclude_profile_pk:
        qs = qs.exclude(pk=exclude_profile_pk)
    return qs.first()


# ─── Employee Documents ───────────────────────────────────────────────────────

def _employee_doc_path(instance, filename):
    import os
    uid = (
        getattr(instance.user, 'employee_id', None)
        or str(instance.user_id)
    )
    return os.path.join('employee_documents', str(uid), os.path.basename(filename))


class EmployeeDocument(models.Model):
    TYPE_PAN               = 'pan_card'
    TYPE_AADHAAR           = 'aadhaar_card'
    TYPE_DEGREE            = 'degree_certificate'
    TYPE_EXPERIENCE        = 'experience_letter'
    TYPE_PASSPORT_PHOTO    = 'passport_photo'
    TYPE_CANCELLED_CHEQUE  = 'cancelled_cheque'
    TYPE_OTHER             = 'other'
    TYPE_CHOICES    = [
        (TYPE_PAN,              'PAN Card'),
        (TYPE_AADHAAR,          'Aadhaar Card'),
        (TYPE_DEGREE,           'Degree Certificate'),
        (TYPE_EXPERIENCE,       'Experience Letter'),
        (TYPE_PASSPORT_PHOTO,   'Passport Photo'),
        (TYPE_CANCELLED_CHEQUE, 'Cancelled Cheque'),
        (TYPE_OTHER,            'Other'),
    ]

    ALLOWED_MIME_TYPES = {'image/jpeg', 'image/png', 'application/pdf'}
    MAX_FILE_SIZE      = 5 * 1024 * 1024  # 5 MB

    user          = models.ForeignKey(User, on_delete=models.CASCADE, related_name='employee_documents')
    document_type = models.CharField(max_length=30, choices=TYPE_CHOICES)
    # Django's FileField max_length defaults to 100 — _employee_doc_path() embeds
    # the original filename into the stored path, so anything beyond a short name
    # overflows that default (matches file_name's own width for the same reason).
    file          = models.FileField(upload_to=_employee_doc_path, max_length=255)
    file_name     = models.CharField(max_length=255)
    file_size     = models.PositiveBigIntegerField()
    uploaded_at   = models.DateTimeField(auto_now_add=True)
    updated_at    = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'hrms_employee_documents'
        ordering = ['document_type', '-uploaded_at']

    def __str__(self) -> str:
        return f'{self.user.email} — {self.document_type}'


# ─── Approval Workflow Rules (global defaults) ────────────────────────────────

class ApprovalWorkflowRule(models.Model):
    WORKFLOW_LEAVE                 = 'leave'
    WORKFLOW_EXPENSE               = 'expense'
    WORKFLOW_ATTENDANCE_CORRECTION = 'attendance_correction'
    WORKFLOW_CHOICES = [
        (WORKFLOW_LEAVE,                 'Leave Request'),
        (WORKFLOW_EXPENSE,               'Expense Claim'),
        (WORKFLOW_ATTENDANCE_CORRECTION, 'Attendance Correction'),
    ]

    workflow_type    = models.CharField(max_length=25, choices=WORKFLOW_CHOICES, unique=True)
    l1_approver_role = models.ForeignKey(
                           'Role',
                           on_delete=models.SET_NULL,
                           null=True,
                           blank=True,
                           related_name='rules_as_l1',
                       )
    l2_approver_role = models.ForeignKey(
                           'Role',
                           on_delete=models.SET_NULL,
                           null=True,
                           blank=True,
                           related_name='rules_as_l2',
                       )
    updated_at = models.DateTimeField(auto_now=True)
    updated_by = models.ForeignKey(
                     User,
                     on_delete=models.SET_NULL,
                     null=True,
                     blank=True,
                     related_name='approval_rule_updates',
                 )

    class Meta:
        db_table = 'hrms_approval_workflow_rules'

    def __str__(self) -> str:
        l1_name = self.l1_approver_role.display_name if self.l1_approver_role else 'None'
        return f'{self.get_workflow_type_display()} — L1: {l1_name}'


# ─── Employee Approval Overrides (per-employee) ───────────────────────────────

class EmployeeApprovalOverride(models.Model):
    """Per-employee override for a specific workflow's approvers.
    If l1_override or l2_override is null, the global ApprovalWorkflowRule applies."""

    employee      = models.ForeignKey(
                        User,
                        on_delete=models.CASCADE,
                        related_name='approval_overrides',
                    )
    workflow_type = models.CharField(
                        max_length=25,
                        choices=ApprovalWorkflowRule.WORKFLOW_CHOICES,
                    )
    l1_override   = models.ForeignKey(
                        User,
                        on_delete=models.SET_NULL,
                        null=True,
                        blank=True,
                        related_name='l1_approval_overrides',
                    )
    l2_override   = models.ForeignKey(
                        User,
                        on_delete=models.SET_NULL,
                        null=True,
                        blank=True,
                        related_name='l2_approval_overrides',
                    )
    updated_at = models.DateTimeField(auto_now=True)
    updated_by = models.ForeignKey(
                     User,
                     on_delete=models.SET_NULL,
                     null=True,
                     blank=True,
                     related_name='approval_override_updates',
                 )

    class Meta:
        db_table        = 'hrms_employee_approval_overrides'
        unique_together = ('employee', 'workflow_type')

    def __str__(self) -> str:
        return f'{self.employee.email} — {self.workflow_type}'


class EmailTemplateAttachment(models.Model):
    ALLOWED_MIME_TYPES = {
        'image/jpeg', 'image/png', 'image/gif', 'image/webp',
        'application/pdf',
        'application/msword',
        'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
        'application/vnd.ms-excel',
        'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
    }

    template    = models.ForeignKey(EmailTemplate, on_delete=models.CASCADE, related_name='attachments')
    file        = models.FileField(upload_to='email_template_attachments/')
    filename    = models.CharField(max_length=255)
    mime_type   = models.CharField(max_length=100)
    size        = models.PositiveIntegerField(help_text='File size in bytes')
    uploaded_at = models.DateTimeField(auto_now_add=True)
    uploaded_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='uploaded_template_attachments',
    )

    class Meta:
        db_table = 'hrms_email_template_attachments'
        ordering = ['uploaded_at']

    def __str__(self) -> str:
        return self.filename
