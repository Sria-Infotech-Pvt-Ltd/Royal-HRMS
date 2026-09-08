from __future__ import annotations

import logging
import re
import uuid
from datetime import timedelta

from django.conf import settings
from django.contrib.auth.hashers import check_password as _check_hash
from django.contrib.auth.hashers import make_password as _make_hash
from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin
from django.contrib.postgres.constraints import ExclusionConstraint
from django.contrib.postgres.fields import DateRangeField, RangeBoundary, RangeOperators
from django.db import models, transaction
from django.db.models import CheckConstraint, F, Func, Q, UniqueConstraint
from django.utils import timezone

from core.encrypted_fields import EncryptedCharField, blind_index
from core.storage import (
    AuthenticatedImageKitStorage,
    company_logo_upload_path,
    document_center_upload_path,
    email_template_attachment_upload_path,
    profile_photo_upload_path,
)

logger = logging.getLogger(__name__)


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
    is_system_role = models.BooleanField(
        default=False,
        help_text=(
            'One of the roles this company was provisioned with (System Admin, '
            'Branch Admin, HR, Manager, Employee) — cannot be deleted, regardless '
            'of name. Permissions and the display name stay fully editable; only '
            'deletion is blocked, so the rest of the app can always assume these '
            'roles exist.'
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
    # True until a human manually edits `designation` (EmployeeDetailView.put()) —
    # lets Position-driven syncs (accounts/services_placement._sync_from_position)
    # keep writing to it until someone deliberately overrides it by hand.
    designation_synced_from_position = models.BooleanField(default=True)
    # Same idea as designation_synced_from_position, but tracked separately —
    # a manual correction to one shouldn't silently freeze sync on the other.
    department_synced_from_position = models.BooleanField(default=True)
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
    profile_photo           = models.ImageField(upload_to=profile_photo_upload_path, null=True, blank=True)
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
# Department/Designation retired here (Stage 6) — OrgUnit/Position/Placement
# below are the real, single source of truth for org structure and hiring.

class OrgUnit(models.Model):
    """
    A node in the formal organisation structure (e.g. "SAP Consulting &
    Delivery" → "S/4HANA Practice") — a genuine hierarchy with its own
    Position/Placement model underneath. `is_department_level` (below) is
    an optional marker an admin sets explicitly on whichever units
    represent a real "department" for eligibility/reporting purposes (e.g.
    LeavePolicy.applicable_departments, the attendance/dashboard department
    filters) — see `services_approval.resolve_employee_department_name()`,
    which walks up from an employee's own unit to the nearest one marked
    this way.
    """
    id         = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name       = models.CharField(max_length=150)
    code       = models.CharField(max_length=30, blank=True)
    parent     = models.ForeignKey(
                     'self', on_delete=models.PROTECT, null=True, blank=True,
                     related_name='children',
                 )
    cost_center = models.CharField(max_length=30, blank=True)
    is_department_level = models.BooleanField(default=False)
    # Deactivate rather than delete once a unit has real history (positions,
    # placements) under it — deleting history is a compliance problem.
    is_active  = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'hrms_org_units'
        ordering = ['name']

    def __str__(self) -> str:
        return self.name


class JobTemplate(models.Model):
    """Reusable job title + grade band a Position can reference — e.g. "SAP
    Architect · L5", shared across org units. Seeded once via migration;
    read-only from the API (no admin CRUD needed for v1)."""
    id         = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name       = models.CharField(max_length=150, unique=True)
    band       = models.CharField(max_length=20, blank=True)
    is_active  = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'hrms_job_templates'
        ordering = ['name']

    def __str__(self) -> str:
        return f'{self.name} ({self.band})' if self.band else self.name


class Position(models.Model):
    """A seat within an OrgUnit — may be vacant. Who holds it, and since when,
    lives on `Placement` (a dated window), not on this model — a seat's
    holder history is queryable, and a future-dated change can be scheduled
    without disturbing today's holder. Exactly one position per OrgUnit may
    have `is_chief=True`; that position's current holder is the unit's head.
    Enforced both in the serializer (unsets any other chief in the same
    unit, for a clean UX) and as a DB-level partial unique constraint
    (`position_one_chief_per_unit`, below) — the spec for this change
    explicitly wants the invariant guaranteed at the database, not only in
    application code."""
    id            = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    org_unit      = models.ForeignKey(OrgUnit, on_delete=models.CASCADE, related_name='positions')
    job_template  = models.ForeignKey(
                        JobTemplate, on_delete=models.SET_NULL, null=True, blank=True,
                        related_name='positions',
                    )
    title         = models.CharField(max_length=150)
    grade         = models.CharField(max_length=20, blank=True)
    is_chief      = models.BooleanField(default=False)
    # Optional — most positions live in the one shared, company-wide tree;
    # set this only when a seat is genuinely tied to one physical branch
    # (e.g. "Recruiter — Kondapur"). Lets the same tree be filtered to a
    # branch-specific view without duplicating OrgUnit/Position per branch.
    branch        = models.ForeignKey(
                        'branch.Branch', on_delete=models.SET_NULL, null=True, blank=True,
                        related_name='positions',
                    )
    # Deactivate rather than delete once a position has placement history —
    # deleting history is a compliance problem (Placement.position is
    # on_delete=PROTECT for the same reason).
    is_active     = models.BooleanField(default=True)
    created_at    = models.DateTimeField(auto_now_add=True)
    updated_at    = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'hrms_positions'
        ordering = ['title']
        constraints = [
            UniqueConstraint(fields=['org_unit'], condition=Q(is_chief=True), name='position_one_chief_per_unit'),
        ]

    def __str__(self) -> str:
        return f'{self.title} — {self.org_unit.name}'


class Placement(models.Model):
    """One employee holding one Position across a date window — this is
    where dates live, replacing the old direct `Position.holder` FK (which
    could only ever say who holds a seat *right now*, and lost that
    information the instant someone was reassigned). `effective_from`/
    `effective_to` are both inclusive; a null `effective_to` means
    open-ended (still current).

    The two DB-level `ExclusionConstraint`s below are the actual source of
    truth for "no double-booking" — not application code:
      - `placement_position_no_overlap`: a seat can't have two people
        holding it on the same day.
      - `placement_employee_no_overlap`: one employee can't hold two seats
        at once, company-wide (confirmed decision — see this feature's
        design notes; NOT a general SAP-style multi-position model).
    Both use an inclusive-inclusive Postgres `daterange(...,'[]')` built at
    the expression level (no stored range column) — Postgres canonicalizes
    this internally, so callers must never *also* manually shift
    `effective_to` by a day when reasoning about overlaps. A null
    `effective_to` becomes unbounded-above automatically inside that
    `daterange()` call.

    Never hard-delete a Position/employee that has placement rows —
    `on_delete=PROTECT` on both FKs enforces this; the history itself is a
    compliance record, not disposable."""
    id             = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    position       = models.ForeignKey(Position, on_delete=models.PROTECT, related_name='placements')
    employee       = models.ForeignKey('User', on_delete=models.PROTECT, related_name='placements')
    effective_from = models.DateField()
    effective_to   = models.DateField(null=True, blank=True)
    note           = models.CharField(max_length=255, blank=True)
    created_at     = models.DateTimeField(auto_now_add=True)
    created_by     = models.ForeignKey(
                         'User', on_delete=models.SET_NULL, null=True, blank=True,
                         related_name='+',
                     )
    updated_at     = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'hrms_placements'
        ordering = ['-effective_from']
        indexes = [models.Index(fields=['position', 'effective_from'])]
        constraints = [
            CheckConstraint(
                condition=Q(effective_to__isnull=True) | Q(effective_to__gte=F('effective_from')),
                name='placement_effective_to_gte_from',
                violation_error_message='The end date cannot be before the start date.',
            ),
            ExclusionConstraint(
                name='placement_position_no_overlap',
                violation_error_message='This position already has an overlapping placement for that date range.',
                expressions=[
                    ('position', RangeOperators.EQUAL),
                    (
                        Func(
                            'effective_from', 'effective_to',
                            RangeBoundary(inclusive_lower=True, inclusive_upper=True),
                            function='daterange', output_field=DateRangeField(),
                        ),
                        RangeOperators.OVERLAPS,
                    ),
                ],
            ),
            ExclusionConstraint(
                name='placement_employee_no_overlap',
                violation_error_message='This employee already has an overlapping placement for that date range.',
                expressions=[
                    ('employee', RangeOperators.EQUAL),
                    (
                        Func(
                            'effective_from', 'effective_to',
                            RangeBoundary(inclusive_lower=True, inclusive_upper=True),
                            function='daterange', output_field=DateRangeField(),
                        ),
                        RangeOperators.OVERLAPS,
                    ),
                ],
            ),
        ]

    def __str__(self) -> str:
        return f'{self.employee.full_name} — {self.position.title} ({self.effective_from} – {self.effective_to or "present"})'


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
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    # The branch this event pertains to (the affected employee/candidate/
    # document/cycle's branch) — NOT necessarily the acting user's own
    # branch, e.g. a system_admin editing a Mumbai employee. Falls back to
    # the actor's branch at call sites that haven't been updated to pass an
    # explicit target branch, and for actions with no meaningful target
    # (login/logout, settings, role management). Plain branch-name string,
    # matching User.branch's convention, so it can be compared directly
    # against request.user.branch for HR's branch-scoped audit view.
    branch     = models.CharField(max_length=100, null=True, blank=True, default='')

    class Meta:
        db_table = 'hrms_audit_logs'
        ordering = ['-created_at']
        indexes = [
            # Phase 4: AuditLogListView / SystemAdminAuditLogsView both filter
            # by module combined with a created_at date-range, on an
            # ever-growing, unbounded table — the standalone created_at index
            # alone can't serve the module-scoped queries efficiently.
            models.Index(fields=['module', 'created_at'], name='auditlog_module_created_idx'),
            # apps.voice_commands.audit._check_anomaly filters by user first
            # (then module/action as cheap post-filters within an already
            # per-user, time-windowed row set) — the index above leads with
            # module instead, so it can't serve this query. Runs on every
            # permission-denied/no-match voice event.
            models.Index(fields=['user', 'created_at'], name='auditlog_user_created_idx'),
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


# ─── Email Log (system-wide) ──────────────────────────────────────────────────

class EmailLog(models.Model):
    """
    One row per email send attempt, written automatically by
    send_template_email() / resend_logged_email() (see apps.accounts.utils) —
    system-wide, not tied to any single app's domain object. Subject/body/
    context are persisted from a REDACTED copy of the original context (see
    utils._redact_context) whenever it carried a password/OTP/token, so a
    resend can replay stored content verbatim without ever exposing a
    credential through this log — has_sensitive_context marks those rows and
    blocks generic resend for them (see EmailLogResendView).
    """
    STATUS_SENT   = 'sent'
    STATUS_FAILED = 'failed'
    STATUS_CHOICES = [
        (STATUS_SENT,   'Sent'),
        (STATUS_FAILED, 'Failed'),
    ]

    id                    = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    recipient_email       = models.EmailField()
    subject               = models.CharField(max_length=500, blank=True, default='')
    body_html             = models.TextField(blank=True, default='')
    template_name         = models.CharField(max_length=100, blank=True, default='')
    context               = models.JSONField(default=dict, blank=True)
    module                = models.CharField(max_length=50, blank=True, default='')
    status                = models.CharField(max_length=10, choices=STATUS_CHOICES)
    error_message         = models.TextField(blank=True, default='')
    triggered_by          = models.ForeignKey(
                                 User, on_delete=models.SET_NULL, null=True, blank=True,
                                 related_name='email_logs_triggered',
                             )
    smtp_settings         = models.ForeignKey(
                                 'SMTPSettings', on_delete=models.SET_NULL, null=True, blank=True,
                                 related_name='email_logs',
                             )
    had_attachments       = models.BooleanField(default=False)
    attachment_filenames  = models.CharField(max_length=500, blank=True, default='')
    has_sensitive_context = models.BooleanField(default=False)
    is_resend             = models.BooleanField(default=False)
    resend_of             = models.ForeignKey(
                                 'self', on_delete=models.SET_NULL, null=True, blank=True,
                                 related_name='resend_attempts',
                             )
    created_at            = models.DateTimeField(auto_now_add=True)
    updated_at            = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'hrms_email_logs'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['status', 'created_at'], name='emaillog_status_created_idx'),
            models.Index(fields=['module', 'created_at'], name='emaillog_module_created_idx'),
        ]

    def __str__(self) -> str:
        return f'[{self.status}] {self.subject} → {self.recipient_email}'

    @classmethod
    def record(cls, **kwargs) -> EmailLog | None:
        """Write a log row; never raises — a logging failure must never mask
        the real send outcome or crash the caller."""
        try:
            return cls.objects.create(**kwargs)
        except Exception:
            logger.exception('Failed to write EmailLog row for %s', kwargs.get('recipient_email'))
            return None


# ─── Company (singleton) ──────────────────────────────────────────────────────

class Company(models.Model):
    """Single legal entity. Only one record ever exists in this table."""

    MONTH_CHOICES = [
        ('January',   'January'),   ('February', 'February'), ('March',    'March'),
        ('April',     'April'),     ('May',       'May'),      ('June',     'June'),
        ('July',      'July'),      ('August',    'August'),   ('September','September'),
        ('October',   'October'),   ('November',  'November'), ('December', 'December'),
    ]

    JURISDICTION_INDIA   = 'india'
    JURISDICTION_FOREIGN = 'foreign'
    JURISDICTION_CHOICES = [
        (JURISDICTION_INDIA,   'India'),
        (JURISDICTION_FOREIGN, 'Foreign (outside India)'),
    ]

    # Covers both jurisdictions in one field — validated against `jurisdiction`
    # at the serializer level rather than split into two DB columns, since
    # only one of the two sets is ever meaningful for a given company.
    ENTITY_TYPE_CHOICES = [
        # India
        ('private_limited',    'Private Limited — Pvt Ltd'),
        ('public_limited',     'Public Limited — Ltd'),
        ('opc',                'One Person Company — OPC'),
        ('llp',                'LLP — Partnership'),
        ('partnership',        'Partnership Firm — Firm'),
        ('sole_proprietorship','Proprietorship — Sole owner'),
        ('huf',                'HUF — Family'),
        ('section8',           'Section 8 — Non-profit'),
        ('trust_society',      'Trust / Society — Charitable'),
        # Foreign
        ('corporation',        'Corporation (Inc.) — Body corporate'),
        ('llc',                'Limited Liability Company — LLC'),
        ('foreign_partnership','Partnership'),
        ('branch_office',      'Branch Office'),
        ('other',              'Other'),
    ]

    MSME_CLASS_MICRO  = 'micro'
    MSME_CLASS_SMALL  = 'small'
    MSME_CLASS_MEDIUM = 'medium'
    MSME_CLASS_NONE   = 'not_registered'
    MSME_CLASS_CHOICES = [
        (MSME_CLASS_MICRO,  'Micro'),
        (MSME_CLASS_SMALL,  'Small'),
        (MSME_CLASS_MEDIUM, 'Medium'),
        (MSME_CLASS_NONE,   'Not registered'),
    ]

    BANK_ACCOUNT_SAVINGS = 'savings'
    BANK_ACCOUNT_CURRENT = 'current'
    BANK_ACCOUNT_TYPE_CHOICES = [
        (BANK_ACCOUNT_SAVINGS, 'Savings'),
        (BANK_ACCOUNT_CURRENT, 'Current'),
    ]

    # Small, curated lists rather than exhaustive ISO/IANA data — covers the
    # currencies/timezones/date formats this app's actual users need, not
    # every possibility in existence.
    CURRENCY_CHOICES = [
        ('INR', 'INR — Indian Rupee (₹)'), ('USD', 'USD — US Dollar ($)'),
        ('EUR', 'EUR — Euro (€)'),         ('GBP', 'GBP — British Pound (£)'),
        ('AED', 'AED — UAE Dirham'),       ('SGD', 'SGD — Singapore Dollar'),
        ('AUD', 'AUD — Australian Dollar'),('CAD', 'CAD — Canadian Dollar'),
        ('JPY', 'JPY — Japanese Yen'),     ('CNY', 'CNY — Chinese Yuan'),
    ]
    DATE_FORMAT_CHOICES = [
        ('DD-MM-YYYY', 'DD-MM-YYYY (31-03-2026)'),
        ('MM-DD-YYYY', 'MM-DD-YYYY (03-31-2026)'),
        ('YYYY-MM-DD', 'YYYY-MM-DD (2026-03-31)'),
        ('DD/MM/YYYY', 'DD/MM/YYYY (31/03/2026)'),
    ]
    TIMEZONE_CHOICES = [
        ('Asia/Kolkata',    'Asia/Kolkata — IST (UTC+5:30)'),
        ('Asia/Dubai',      'Asia/Dubai — GST (UTC+4:00)'),
        ('Asia/Singapore',  'Asia/Singapore — SGT (UTC+8:00)'),
        ('Europe/London',   'Europe/London — GMT/BST'),
        ('America/New_York','America/New_York — ET'),
        ('America/Chicago', 'America/Chicago — CT'),
        ('America/Los_Angeles', 'America/Los_Angeles — PT'),
        ('Australia/Sydney','Australia/Sydney — AET'),
    ]
    INDUSTRY_CHOICES = [
        ('it_services',      'Information Technology & Services'),
        ('manufacturing',    'Manufacturing'),
        ('healthcare',       'Healthcare'),
        ('finance',          'Financial Services'),
        ('retail',           'Retail & E-commerce'),
        ('education',        'Education'),
        ('construction',     'Construction & Real Estate'),
        ('hospitality',      'Hospitality & Travel'),
        ('logistics',        'Logistics & Transportation'),
        ('other',            'Other'),
    ]
    COUNTRY_CHOICES = [
        ('US', 'United States'), ('GB', 'United Kingdom'), ('AE', 'United Arab Emirates'),
        ('SG', 'Singapore'),     ('AU', 'Australia'),      ('CA', 'Canada'),
        ('DE', 'Germany'),       ('FR', 'France'),         ('NL', 'Netherlands'),
        ('other', 'Other'),
    ]

    jurisdiction   = models.CharField(max_length=10, choices=JURISDICTION_CHOICES, default=JURISDICTION_INDIA)
    entity_type    = models.CharField(max_length=30, choices=ENTITY_TYPE_CHOICES, blank=True)
    company_name   = models.CharField(max_length=200)
    trade_name     = models.CharField(max_length=200, blank=True)
    logo           = models.ImageField(upload_to=company_logo_upload_path, null=True, blank=True)
    date_of_incorporation = models.DateField(null=True, blank=True)
    is_listed      = models.BooleanField(default=False, help_text='Whether shares are publicly listed on a stock exchange.')
    holding_company_info = models.CharField(
                         max_length=255, blank=True,
                         help_text='Parent company name and CIN, if this is a subsidiary.',
                     )

    # ── India ──
    cin            = models.CharField(max_length=21, blank=True)
    roc_jurisdiction = models.CharField(max_length=100, blank=True)
    # Encrypted at rest — same PII tier as EmployeeProfile.pan_number (see
    # core/encrypted_fields.py, CLAUDE.md §3). No blind-index hash needed:
    # Company is a singleton table (one row ever), so there's no cross-row
    # uniqueness/lookup to preserve, unlike the employee-level PAN.
    pan            = EncryptedCharField(max_length=255, blank=True)
    tan            = models.CharField(max_length=10, blank=True)

    # ── Foreign ──
    country_of_registration = models.CharField(max_length=10, choices=COUNTRY_CHOICES, blank=True)
    registration_number     = models.CharField(max_length=50, blank=True)
    ein                      = models.CharField(max_length=20, blank=True)

    # ── Other registrations (all optional, India-specific but harmless if blank elsewhere) ──
    udyam_msme          = models.CharField(max_length=20, blank=True)
    msme_class          = models.CharField(max_length=20, choices=MSME_CLASS_CHOICES, default=MSME_CLASS_NONE, blank=True)
    iec                 = models.CharField(max_length=20, blank=True)
    epfo_code           = models.CharField(max_length=30, blank=True)
    esic_code           = models.CharField(max_length=30, blank=True)
    professional_tax_reg = models.CharField(max_length=30, blank=True)

    # ── Directors / signatory / bank ──
    signatory_full_name  = models.CharField(max_length=150, blank=True)
    signatory_designation = models.CharField(max_length=100, blank=True)
    # Encrypted at rest — same reasoning as pan above.
    signatory_din_pan    = EncryptedCharField(max_length=255, blank=True)
    signatory_email      = models.EmailField(blank=True)
    signatory_appears_on_invoices = models.BooleanField(default=True)

    bank_account_holder  = models.CharField(max_length=200, blank=True)
    # Encrypted at rest — same tier as BankDetail.account_number/ifsc_code
    # (apps/payroll/models.py), this is just the company's own account
    # instead of an employee's.
    bank_account_number  = EncryptedCharField(max_length=255, blank=True)
    bank_ifsc            = EncryptedCharField(max_length=255, blank=True)
    bank_account_type    = models.CharField(max_length=10, choices=BANK_ACCOUNT_TYPE_CHOICES, blank=True)

    # ── Business profile ──
    industry            = models.CharField(max_length=30, choices=INDUSTRY_CHOICES, blank=True)
    nic_code            = models.CharField(max_length=10, blank=True)
    nature_of_business  = models.TextField(blank=True)

    # ── Registered office ──
    address        = models.TextField(max_length=500)
    city           = models.CharField(max_length=100)
    state          = models.CharField(max_length=100, blank=True)
    pin_code       = models.CharField(max_length=6, blank=True)

    # ── Communication address ── defaults to the registered office; only
    # populated when it genuinely differs (e.g. a correspondence/billing
    # address separate from the statutory registered office).
    communication_address_same_as_registered = models.BooleanField(default=True)
    communication_address = models.TextField(max_length=500, blank=True)
    communication_city    = models.CharField(max_length=100, blank=True)
    communication_state   = models.CharField(max_length=100, blank=True)
    communication_pin_code = models.CharField(max_length=6, blank=True)

    # ── Regional & formats ──
    default_currency = models.CharField(max_length=3, choices=CURRENCY_CHOICES, default='INR')
    date_format      = models.CharField(max_length=10, choices=DATE_FORMAT_CHOICES, default='DD-MM-YYYY')
    timezone         = models.CharField(max_length=40, choices=TIMEZONE_CHOICES, default='Asia/Kolkata')

    # ── Contact & branding ──
    primary_email  = models.EmailField(blank=True)
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


class CompanyGSTRegistration(models.Model):
    """One row per state the company holds a GST registration in — replaces
    the old single Company.gstin field, since GST law requires a separate
    GSTIN per state of operation."""

    REGISTRATION_REGULAR     = 'regular'
    REGISTRATION_COMPOSITION = 'composition'
    REGISTRATION_CASUAL      = 'casual'
    REGISTRATION_OTHER       = 'other'
    REGISTRATION_TYPE_CHOICES = [
        (REGISTRATION_REGULAR,     'Regular'),
        (REGISTRATION_COMPOSITION, 'Composition'),
        (REGISTRATION_CASUAL,      'Casual'),
        (REGISTRATION_OTHER,       'Other'),
    ]

    id                = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    company           = models.ForeignKey(Company, on_delete=models.CASCADE, related_name='gst_registrations')
    gstin             = models.CharField(max_length=15)
    state             = models.CharField(max_length=100)
    registration_type = models.CharField(max_length=20, choices=REGISTRATION_TYPE_CHOICES, default=REGISTRATION_REGULAR)
    place_of_business = models.CharField(max_length=200, blank=True)
    created_at        = models.DateTimeField(auto_now_add=True)
    updated_at        = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'hrms_company_gst_registration'
        ordering = ['state']
        unique_together = [('company', 'gstin')]

    def __str__(self) -> str:
        return f'{self.gstin} ({self.state})'


class CompanyDirector(models.Model):
    """One row per director/partner/trustee/member — name, designation, and a
    personal identifier. `din` holds whatever ID format that role actually
    uses for this company's entity type (DIN for a company director, PAN for
    a Partnership/Trust partner or trustee, a free-form ID for a foreign
    entity) — see CompanyDirectorSerializer.validate_din()."""

    id           = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    company      = models.ForeignKey(Company, on_delete=models.CASCADE, related_name='directors')
    # Encrypted at rest — for a Partnership/Trust entity type this holds a
    # partner's PAN, not just a DIN (see class docstring), the same PII tier
    # as EmployeeProfile.pan_number. Fernet is non-deterministic, so the
    # uniqueness constraint below can't target this column directly (see
    # din_hash).
    din          = EncryptedCharField(max_length=255)
    # Deterministic blind index of din, same pattern as
    # EmployeeProfile.pan_number_hash — kept in sync in save() below. The
    # (company, din_hash) uniqueness constraint is what actually enforces
    # "no duplicate DIN per company" now; din itself is encrypted so two
    # equal plaintexts never produce equal ciphertext for a DB constraint to
    # catch.
    din_hash     = models.CharField(max_length=64, blank=True, db_index=True)
    name         = models.CharField(max_length=150)
    designation  = models.CharField(max_length=100)
    created_at   = models.DateTimeField(auto_now_add=True)
    updated_at   = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'hrms_company_director'
        ordering = ['name']
        unique_together = [('company', 'din_hash')]

    def save(self, *args, **kwargs):
        # Runs before get_prep_value() encrypts din, so self.din here is
        # always the current plaintext regardless of whether this row was
        # previously encrypted — same reasoning as EmployeeProfile.save().
        self.din_hash = blind_index(self.din) if self.din else ''
        super().save(*args, **kwargs)

    def __str__(self) -> str:
        return f'{self.name} ({self.din})'


# ─── Employee Code Settings (singleton) ──────────────────────────────────────


class EmployeeCodeSettings(models.Model):
    """Singleton row (pk=1) that governs how employee IDs are generated."""
    prefix        = models.CharField(max_length=10, default='EMP')
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
            defaults={'prefix': 'EMP', 'padding': 5, 'next_sequence': 1},
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
                defaults={'prefix': 'EMP', 'padding': 5, 'next_sequence': 1},
            )[0]
            prefix   = cfg.prefix or 'EMP'
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
    file        = models.FileField(upload_to=document_center_upload_path, storage=AuthenticatedImageKitStorage())
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

    # Bank — encrypted at rest (see core/encrypted_fields.py). max_length is
    # sized for Fernet ciphertext, not the plaintext value; real format/length
    # validation for these lives in the serializer layer (validate_account_number,
    # validate_ifsc_code), same as before encryption was added.
    account_number      = EncryptedCharField(max_length=255, blank=True)
    ifsc_code           = EncryptedCharField(max_length=255, blank=True)
    bank_name           = models.CharField(max_length=200, blank=True)
    bank_branch_name    = models.CharField(max_length=200, blank=True)
    account_holder_name = models.CharField(max_length=150, blank=True)
    account_type        = models.CharField(max_length=10, choices=ACCOUNT_CHOICES, blank=True)

    # Statutory identity — PII requiring encryption at rest (CLAUDE.md §3).
    # pan_number can never be looked up by exact match against ciphertext
    # (Fernet is non-deterministic) — pan_number_hash is a deterministic
    # blind index used for that instead; see find_conflicting_pan_profile()
    # and save() below, which keeps it in sync automatically.
    name_as_per_aadhar = EncryptedCharField(max_length=255, blank=True, help_text='Name exactly as printed on the Aadhaar card')
    uan_number         = EncryptedCharField(max_length=255, blank=True, help_text='12-digit Universal Account Number issued by EPFO')
    esi_number         = EncryptedCharField(max_length=255, blank=True, help_text='10-digit ESI Insurance Number (IP Number) issued by ESIC')
    pan_number         = EncryptedCharField(
        max_length=255, blank=True,
        help_text='10-character PAN (e.g. ABCDE1234F) — unique per person, encrypted at rest.',
    )
    pan_number_hash    = models.CharField(max_length=64, blank=True, db_index=True)

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

    # Values for HR-created custom onboarding fields (see OnboardingFieldConfig
    # below) — these have no real column since HR defines them at runtime with
    # no code deploy, so {field_key: value} lives here instead. Built-in fields
    # (father_name, bank details, etc.) are untouched by this and keep using
    # their own real columns above.
    custom_field_values = models.JSONField(default=dict, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'hrms_employee_profiles'

    def __str__(self) -> str:
        return f'Profile — {self.user.email}'

    def save(self, *args, **kwargs):
        # Keep the blind index in sync with pan_number on every save — this
        # runs before get_prep_value() encrypts it, so self.pan_number here
        # is always the current plaintext regardless of whether this row was
        # previously encrypted (see EncryptedCharField's InvalidToken fallback).
        self.pan_number_hash = blind_index(self.pan_number) if self.pan_number else ''

        bank_details_changed = False
        if self.pk:
            previous = EmployeeProfile.objects.filter(pk=self.pk).values('account_number', 'ifsc_code').first()
            if previous:
                bank_details_changed = (
                    (previous['account_number'] and previous['account_number'] != self.account_number)
                    or (previous['ifsc_code'] and previous['ifsc_code'] != self.ifsc_code)
                )

        super().save(*args, **kwargs)

        if bank_details_changed:
            self._alert_bank_details_changed()

    def _alert_bank_details_changed(self) -> None:
        """
        An already-populated bank account number or IFSC was just overwritten
        with a different value — the exact mechanism of payroll diversion
        fraud (quietly redirecting someone's salary by editing their bank
        details). Deliberately does NOT fire on first-time entry (empty ->
        filled), only on an existing value being replaced.

        Set `profile._changed_by = request.user` before calling save() at the
        call site to attribute the change in the audit log; falls back to
        unattributed (still logged, still notifies the employee) if omitted.
        """
        from apps.accounts.models import AuditLog
        actor = getattr(self, '_changed_by', None)
        try:
            AuditLog.objects.create(
                user=actor, action='bank_details_changed', module='employees',
                object_id=str(self.user_id),
                changes={'employee': self.user.employee_id or self.user.email},
                branch=self.user.branch,
            )
        except Exception:
            pass
        try:
            from apps.notifications.models import Notification
            from apps.notifications.signals import _push_live
            notification = Notification.objects.create(
                user=self.user,
                title='Your bank details were changed',
                message=(
                    'Your salary bank account number or IFSC code was just updated on your '
                    'HRMS profile. If you did not make this change, contact HR immediately.'
                ),
                notification_type='security_alert', module='security',
            )
            _push_live(notification)
        except Exception:
            pass


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
    if not pan_number:
        return None
    qs = EmployeeProfile.objects.filter(pan_number_hash=blind_index(pan_number)).select_related('user')
    if exclude_profile_pk:
        qs = qs.exclude(pk=exclude_profile_pk)
    return qs.first()


# ─── Onboarding Field Configuration ────────────────────────────────────────────

class OnboardingFieldConfig(models.Model):
    """
    Configuration for the self-onboarding wizard's steps 0-3 (Personal,
    Education, Bank, Emergency — step 4/Documents is a separate,
    file-upload-based flow and isn't covered here). One row per field.

    is_custom=False rows describe a real EmployeeProfile column (field_key
    matches the model field name exactly) — visible/required/order/label can
    be changed, but the row itself can't be deleted (see the view). is_custom=True
    rows are fields HR created at runtime with no code deploy; their values
    live in EmployeeProfile.custom_field_values instead of a real column.

    is_locked=True fields are shown in the settings UI but visible/required
    can't be changed — for fields the business always wants collected,
    independent of any one HR admin's settings choices.
    """
    TYPE_TEXT      = 'text'
    TYPE_TEXTAREA  = 'textarea'
    TYPE_NUMBER    = 'number'
    TYPE_DATE      = 'date'
    TYPE_DROPDOWN  = 'dropdown'
    TYPE_CHECKBOX  = 'checkbox'
    TYPE_FILE      = 'file'
    FIELD_TYPE_CHOICES = [
        (TYPE_TEXT,     'Text'),
        (TYPE_TEXTAREA, 'Long text'),
        (TYPE_NUMBER,   'Number'),
        (TYPE_DATE,     'Date'),
        (TYPE_DROPDOWN, 'Dropdown'),
        (TYPE_CHECKBOX, 'Checkbox'),
        (TYPE_FILE,     'File / Image'),
    ]

    STEP_PERSONAL  = 0
    STEP_EDUCATION = 1
    STEP_BANK      = 2
    STEP_EMERGENCY = 3
    STEP_CHOICES = [
        (STEP_PERSONAL,  'Personal Information'),
        (STEP_EDUCATION, 'Education & Experience'),
        (STEP_BANK,      'Bank Details'),
        (STEP_EMERGENCY, 'Emergency Contact'),
    ]

    field_key  = models.CharField(max_length=64, unique=True)
    label      = models.CharField(max_length=150)
    field_type = models.CharField(max_length=20, choices=FIELD_TYPE_CHOICES, default=TYPE_TEXT)
    # Dropdown choices only, e.g. ["Option A", "Option B"] — ignored for every other field_type.
    options    = models.JSONField(default=list, blank=True)
    # File fields only: whether multiple files may be uploaded for this field
    # (a growing list) vs a single file that's replaced on reupload — ignored
    # for every other field_type, same convention as `options` above.
    allow_multiple = models.BooleanField(default=False)
    step       = models.PositiveSmallIntegerField(choices=STEP_CHOICES)
    order      = models.PositiveSmallIntegerField(default=0)
    visible    = models.BooleanField(default=True)
    required   = models.BooleanField(default=False)
    is_custom  = models.BooleanField(default=False)
    is_locked  = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'hrms_onboarding_field_configs'
        ordering = ['step', 'order']

    def __str__(self) -> str:
        return f'{self.label} ({self.field_key})'


class DocumentTypeConfig(models.Model):
    """
    Per-company configuration for onboarding Step 5 (Documents) — the
    sibling of OnboardingFieldConfig for steps 0-3. is_custom=False rows are
    the 7 built-in types seeded by a data migration (matching the values
    EmployeeDocument.TYPE_PAN etc. used to enforce via a `choices=` enum);
    they can be hidden/reordered/required-toggled but never deleted, since
    deleting one would orphan any already-uploaded EmployeeDocument rows of
    that type. is_custom=True rows are types HR adds at runtime.

    Unlike OnboardingFieldConfig, every field here (including the 7
    built-ins) is fully editable — no is_locked=True rows are seeded; the
    column exists for parity with its sibling model and the shared settings
    table UI, not because any type is currently protected.
    """
    type_key       = models.CharField(max_length=64, unique=True)
    label          = models.CharField(max_length=150)
    order          = models.PositiveSmallIntegerField(default=0)
    visible        = models.BooleanField(default=True)
    required       = models.BooleanField(default=False)
    # Single file (replaced on reupload) vs a growing list — same convention
    # as OnboardingFieldConfig.allow_multiple for its file-type fields.
    allow_multiple = models.BooleanField(default=False)
    is_custom      = models.BooleanField(default=False)
    is_locked      = models.BooleanField(default=False)
    created_at     = models.DateTimeField(auto_now_add=True)
    updated_at     = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'hrms_document_type_configs'
        ordering = ['order']

    def __str__(self) -> str:
        return f'{self.label} ({self.type_key})'


# ─── Employee Documents ───────────────────────────────────────────────────────

def _employee_doc_path(instance, filename):
    import os
    uid = (
        getattr(instance.user, 'employee_id', None)
        or str(instance.user_id)
    )
    return os.path.join('employee_documents', str(uid), os.path.basename(filename))


class EmployeeDocument(models.Model):
    # Plain string identifiers for the 7 built-in types seeded by
    # DocumentTypeConfig (see below) — no longer a `choices=` enum on the
    # field itself. What document types actually exist/are allowed is now
    # configurable via DocumentTypeConfig; these constants just keep the
    # seeded built-ins' type_key values readable in code.
    TYPE_PAN               = 'pan_card'
    TYPE_AADHAAR           = 'aadhaar_card'
    TYPE_DEGREE            = 'degree_certificate'
    TYPE_EXPERIENCE        = 'experience_letter'
    TYPE_PASSPORT_PHOTO    = 'passport_photo'
    TYPE_CANCELLED_CHEQUE  = 'cancelled_cheque'
    TYPE_OTHER             = 'other'

    ALLOWED_MIME_TYPES = {'image/jpeg', 'image/png', 'application/pdf'}
    MAX_FILE_SIZE      = 5 * 1024 * 1024  # 5 MB

    user          = models.ForeignKey(User, on_delete=models.CASCADE, related_name='employee_documents')
    # Validated against DocumentTypeConfig at the view layer, not via a
    # `choices=` enum — max_length matches DocumentTypeConfig.type_key so a
    # custom (HR-added) type's slug always fits.
    document_type = models.CharField(max_length=64)
    # Django's FileField max_length defaults to 100 — _employee_doc_path() embeds
    # the original filename into the stored path, so anything beyond a short name
    # overflows that default (matches file_name's own width for the same reason).
    file          = models.FileField(upload_to=_employee_doc_path, storage=AuthenticatedImageKitStorage(), max_length=255)
    file_name     = models.CharField(max_length=255)
    file_size     = models.PositiveBigIntegerField()
    uploaded_at   = models.DateTimeField(auto_now_add=True)
    updated_at    = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'hrms_employee_documents'
        ordering = ['document_type', '-uploaded_at']

    def __str__(self) -> str:
        return f'{self.user.email} — {self.document_type}'


# ─── Custom Field File Values ─────────────────────────────────────────────────

def _custom_field_file_path(instance, filename):
    import os
    uid = (
        getattr(instance.user, 'employee_id', None)
        or str(instance.user_id)
    )
    # Separate subfolder just keeps ad-hoc custom-field uploads out of the
    # real employee_documents tree rather than mixing the two file families.
    return os.path.join('custom_field_files', str(uid), os.path.basename(filename))


class CustomFieldFileValue(models.Model):
    """
    File/image values for OnboardingFieldConfig fields with field_type='file'
    (see OnboardingFieldConfig.TYPE_FILE). Deliberately not folded into
    EmployeeProfile.custom_field_values (a plain JSONField) — that dict holds
    only JSON-primitive values for every other custom field type, and a real
    upload needs its own storage row (file path, size, mime validation)
    the same way EmployeeDocument does, not a blob of bytes stuffed into JSON.

    No unique_together on (user, field_key): cardinality is controlled by
    OnboardingFieldConfig.allow_multiple instead, enforced by the view
    (delete-then-create when False, plain create when True) rather than a DB
    constraint, since a single model has to serve both cardinalities
    depending on which field a row belongs to.
    """
    user        = models.ForeignKey(User, on_delete=models.CASCADE, related_name='custom_field_files')
    field_key   = models.CharField(max_length=64)
    file        = models.FileField(upload_to=_custom_field_file_path, storage=AuthenticatedImageKitStorage(), max_length=255)
    file_name   = models.CharField(max_length=255)
    file_size   = models.PositiveBigIntegerField()
    uploaded_at = models.DateTimeField(auto_now_add=True)
    updated_at  = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'hrms_custom_field_file_values'
        ordering = ['field_key', '-uploaded_at']

    def __str__(self) -> str:
        return f'{self.user.email} — {self.field_key}'


# ─── Approval Workflow Rules (global defaults) ────────────────────────────────

class ApprovalWorkflowRule(models.Model):
    WORKFLOW_LEAVE                 = 'leave'
    WORKFLOW_EXPENSE               = 'expense'
    WORKFLOW_ATTENDANCE_CORRECTION = 'attendance_correction'
    WORKFLOW_WFH                   = 'wfh'
    WORKFLOW_CHOICES = [
        (WORKFLOW_LEAVE,                 'Leave Request'),
        (WORKFLOW_EXPENSE,               'Expense Claim'),
        (WORKFLOW_ATTENDANCE_CORRECTION, 'Attendance Correction'),
        (WORKFLOW_WFH,                   'Work From Home Request'),
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
    file        = models.FileField(upload_to=email_template_attachment_upload_path, storage=AuthenticatedImageKitStorage())
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
