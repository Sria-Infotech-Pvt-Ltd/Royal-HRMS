from __future__ import annotations

import logging
import re
import uuid
from datetime import timedelta

from django.conf import settings
from django.contrib.auth.hashers import check_password as _check_hash
from django.contrib.auth.hashers import make_password as _make_hash
from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin
from apps.accounts.migration_utils import PortableExclusionConstraint as ExclusionConstraint
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


# ─── Permission ───────────────────────────────────────────────────────────────

class Permission(models.Model):
    module   = models.CharField(max_length=50)
    action   = models.CharField(max_length=20)
    codename = models.CharField(max_length=100, unique=True)

    # Phase 4 Task A — code-registry-generated metadata. Additive; the
    # registry (apps/accounts/permissions_registry.py) is the source of
    # truth, synced idempotently — never hand-edited to drift from it.
    description = models.TextField(blank=True)
    is_sensitive = models.BooleanField(default=False, help_text='Granting this warrants extra scrutiny (e.g. bank/PAN visibility) — shown in admin UI and SoD checks.')
    implies = models.ManyToManyField('self', symmetrical=False, blank=True, related_name='implied_by', help_text='e.g. x.edit implies x.view — holding this codename also grants every implied one.')
    is_deprecated = models.BooleanField(default=False, help_text='No longer created by the registry, but never deleted while still granted to any role (Task A.2).')

    class Meta:
        db_table = 'hrms_permissions'
        ordering = ['module', 'action']
        indexes = [
            models.Index(fields=['module', 'action'], name='permission_module_action_idx'),
        ]

    def __str__(self) -> str:
        return self.codename


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

    EMPLOYMENT_STATUS_PROBATION = 'probation'
    EMPLOYMENT_STATUS_CONFIRMED = 'confirmed'
    EMPLOYMENT_STATUS_CHOICES   = [
        (EMPLOYMENT_STATUS_PROBATION, 'Probation'),
        (EMPLOYMENT_STATUS_CONFIRMED, 'Confirmed'),
    ]

    # Matches the hire wizard's Employment-type list exactly (previously only
    # enforced as a hardcoded array on the frontend, AddEmployeeModal.tsx's
    # EMP_TYPES — added here as real choices= so the Hire flow's
    # EmployeeCodeSeries (one numbering series per type) has a closed set of
    # valid keys to seed, not free text).
    EMPLOYMENT_TYPE_PERMANENT  = 'Permanent'
    EMPLOYMENT_TYPE_CONTRACT   = 'Contract'
    EMPLOYMENT_TYPE_FREELANCER = 'Freelancer'
    EMPLOYMENT_TYPE_CONSULTANT = 'Consultant'
    EMPLOYMENT_TYPE_PART_TIME  = 'Part-Time'
    EMPLOYMENT_TYPE_TEMPORARY  = 'Temporary'
    EMPLOYMENT_TYPE_INTERN     = 'Intern'
    EMPLOYMENT_TYPE_CHOICES    = [
        (EMPLOYMENT_TYPE_PERMANENT,  'Permanent'),
        (EMPLOYMENT_TYPE_CONTRACT,   'Contract'),
        (EMPLOYMENT_TYPE_FREELANCER, 'Freelancer'),
        (EMPLOYMENT_TYPE_CONSULTANT, 'Consultant'),
        (EMPLOYMENT_TYPE_PART_TIME,  'Part-Time'),
        (EMPLOYMENT_TYPE_TEMPORARY,  'Temporary'),
        (EMPLOYMENT_TYPE_INTERN,     'Intern'),
    ]

    WORK_MODE_OFFICE = 'office'
    WORK_MODE_REMOTE = 'remote'
    WORK_MODE_HYBRID = 'hybrid'
    WORK_MODE_CHOICES = [
        (WORK_MODE_OFFICE, 'Office'),
        (WORK_MODE_REMOTE, 'Remote'),
        (WORK_MODE_HYBRID, 'Hybrid'),
    ]

    PAY_GROUP_MONTHLY  = 'monthly'
    PAY_GROUP_WEEKLY   = 'weekly'
    PAY_GROUP_BIWEEKLY = 'biweekly'
    PAY_GROUP_DAILY    = 'daily'
    PAY_GROUP_CHOICES = [
        (PAY_GROUP_MONTHLY,  'Monthly – India'),
        (PAY_GROUP_WEEKLY,   'Weekly'),
        (PAY_GROUP_BIWEEKLY, 'Bi-Weekly'),
        (PAY_GROUP_DAILY,    'Daily Wage'),
    ]

    ATTENDANCE_SCHEME_STANDARD    = 'standard'
    ATTENDANCE_SCHEME_FLEXIBLE    = 'flexible'
    ATTENDANCE_SCHEME_SHIFT_BASED = 'shift_based'
    ATTENDANCE_SCHEME_CHOICES = [
        (ATTENDANCE_SCHEME_STANDARD,    'Standard'),
        (ATTENDANCE_SCHEME_FLEXIBLE,    'Flexible'),
        (ATTENDANCE_SCHEME_SHIFT_BASED, 'Shift-based'),
    ]

    PAYMENT_METHOD_BANK_TRANSFER = 'bank_transfer'
    PAYMENT_METHOD_CHEQUE        = 'cheque'
    PAYMENT_METHOD_CASH          = 'cash'
    PAYMENT_METHOD_CHOICES = [
        (PAYMENT_METHOD_BANK_TRANSFER, 'Bank Transfer – NEFT'),
        (PAYMENT_METHOD_CHEQUE,        'Cheque'),
        (PAYMENT_METHOD_CASH,          'Cash'),
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
    employee_id     = models.CharField(max_length=20, blank=True, db_index=True)
    department      = models.CharField(max_length=100, blank=True)
    designation     = models.CharField(max_length=100, blank=True)
    # Free text, no choices enum — same convention as department/designation
    # above. Was already collected by the Add Employee form and validated by
    # EmployeeBulkImportRowSerializer, but had nowhere to be saved until now.
    employee_type   = models.CharField(max_length=50, blank=True, default='Permanent', choices=EMPLOYMENT_TYPE_CHOICES)
    # True until a human manually edits `designation` (EmployeeDetailView.put()) —
    # lets Position-driven syncs (accounts/services_placement._sync_from_position)
    # keep writing to it until someone deliberately overrides it by hand.
    designation_synced_from_position = models.BooleanField(default=True)
    # Same idea as designation_synced_from_position, but tracked separately —
    # a manual correction to one shouldn't silently freeze sync on the other.
    department_synced_from_position = models.BooleanField(default=True)
    # DEPRECATED — compared by exact string against Branch.branch_name at
    # ~90 call sites across nearly every app (attendance, payroll, leave,
    # hrms, recruitment, announcements, notifications, dashboard,
    # voice_commands — grepped and enumerated in the PR/commit for this
    # field). No referential integrity: renaming a branch or a typo silently
    # orphans/misses employees with no error. `branch_fk` below is the
    # replacement — being migrated over call-site by call-site rather than
    # in one sweep, since a mistake in any of those ~90 places is a
    # real-money/real-attendance bug, not a cosmetic one. Do not add new
    # code that reads/writes this field — use `branch_fk` instead, and if
    # you're touching an existing call site anyway, migrate it to
    # `branch_fk` as part of that change. Drop this field only once every
    # call site has been migrated (tracked in the same commit history as
    # `branch_fk`'s own introduction).
    branch          = models.CharField(max_length=100, blank=True)
    # Real FK replacement for `branch` above — nullable because (a) not
    # every user has a branch (system_admin accounts, some managers), same
    # as the string field's own blank=True, and (b) a legacy `branch` string
    # that doesn't match any real Branch.branch_name (a typo or a renamed/
    # deleted branch) has nothing valid to point at; SET_NULL rather than
    # CASCADE/PROTECT so deleting a Branch never cascades into deleting the
    # employees who used to belong to it.
    branch_fk       = models.ForeignKey(
                          'branch.Branch', on_delete=models.SET_NULL, null=True, blank=True,
                          related_name='employees',
                      )
    phone           = models.CharField(max_length=20, blank=True)
    date_of_joining = models.DateField(null=True, blank=True)
    reporting_manager = models.ForeignKey(
                            'self',
                            on_delete=models.SET_NULL,
                            null=True,
                            blank=True,
                            related_name='direct_reports',
                        )
    # True only when `reporting_manager` was resolved from an actual placed
    # chief somewhere in this employee's Org Unit chain (_auto_assign_managers
    # -> resolve_employee_org_unit_chief). False for the same function's own
    # "any active manager in the branch" fallback (used when no unit in the
    # chain has a chief placed yet) and for any manually-set reporting_manager
    # (HR picking one explicitly at create/edit time) — both are legitimate,
    # but neither reflects a real org-chart placement, so this flag is purely
    # informational: it lets HR find and close org-chart gaps (place a chief
    # somewhere) rather than that going unnoticed forever behind a working
    # fallback. Never read by permission/approval logic itself.
    reporting_manager_from_org_chart = models.BooleanField(default=False)
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
    # Secondary/matrix reporting line, set from the Hire wizard's Employment
    # step — distinct from reporting_approver above (that's an approval-flow
    # fallback, not a real dotted-line relationship). Purely informational —
    # never read by permission/approval logic, same as
    # reporting_manager_from_org_chart above.
    dotted_line_manager = models.ForeignKey(
                              'self',
                              on_delete=models.SET_NULL,
                              null=True,
                              blank=True,
                              related_name='dotted_line_reports',
                          )
    # Set once, at hire time, on the Hire wizard's Employment step — there is
    # no automatic "N months after joining -> confirmed" job; EmployeeConfirmView
    # (the Confirmation action) still requires a human to trigger it, this is
    # just the target period HR agreed to at hire time for reference.
    probation_period_months = models.PositiveSmallIntegerField(null=True, blank=True)
    notice_period_days      = models.PositiveSmallIntegerField(null=True, blank=True)
    work_location            = models.CharField(max_length=150, blank=True)
    work_mode                = models.CharField(max_length=20, blank=True, choices=WORK_MODE_CHOICES)
    # Which pay-frequency group this employee is paid under — distinct from
    # PayrollCycle (which schedules a single run) and SalaryStructure (which
    # defines earning components); this is what groups employees together
    # for that run. Set at hire time on the Employment step.
    pay_group         = models.CharField(max_length=20, blank=True, choices=PAY_GROUP_CHOICES, default=PAY_GROUP_MONTHLY)
    # Distinct from Shift (attendance.WorkingHoursPolicy, a specific clock-in/
    # clock-out window) — this is the broader attendance-tracking mode the
    # employee is on. Set at hire time; not yet read by any attendance
    # computation (same "real field, not yet a consumer" category as
    # work_location/work_mode above).
    attendance_scheme = models.CharField(max_length=20, blank=True, choices=ATTENDANCE_SCHEME_CHOICES, default=ATTENDANCE_SCHEME_STANDARD)
    payment_method    = models.CharField(max_length=20, blank=True, choices=PAYMENT_METHOD_CHOICES, default=PAYMENT_METHOD_BANK_TRANSFER)
    # The leave plan HR assigned at hire time — informational alongside the
    # app's existing eligibility-driven LeavePolicy resolution (branch/
    # department/employment_type/gender/tenure JSON matching, see
    # LeavePolicy.applicable_*), which is what actually drives LeaveBalance
    # allocation; this field doesn't override that, it records what HR
    # intended at hire for reference on the employee's own record.
    leave_plan = models.ForeignKey(
        'hrms.LeavePolicy', on_delete=models.SET_NULL, null=True, blank=True, related_name='assigned_employees',
    )
    is_active       = models.BooleanField(default=True)
    is_staff      = models.BooleanField(default=False)
    must_change_password    = models.BooleanField(default=True)
    # True from the moment HR sends the onboarding invite until the person has both set their password and logged in once;
    # while True the employee shows as Onboarding (see services_onboarding). Separate from must_change_password, which an
    # admin password reset also sets and must not push a working employee back to Onboarding.
    activation_pending      = models.BooleanField(default=False, db_index=True)
    onboarding_status       = models.CharField(
                                  max_length=20,
                                  choices=ONBOARDING_CHOICES,
                                  default=ONBOARDING_PENDING,
                              )
    # A pending status alone cannot tell us *why* a record is incomplete:
    # interview candidates must complete the employee self-service wizard,
    # whereas a direct Hire Action has already collected those details from
    # HR. Keep that workflow decision separate from its current progress so
    # a later status correction cannot route a direct hire into the wizard.
    requires_self_service_onboarding = models.BooleanField(default=False)
    # Set alongside onboarding_status going to ONBOARDING_REJECTED (see
    # OnboardingApprovalView) — the exact text HR typed in the "Send Back for
    # Corrections" dialog, so the employee sees what to fix when they land
    # back on the wizard, not just a generic "corrections needed". Cleared on
    # resubmit/approval so a stale reason never lingers once it's been acted
    # on. Previously this text only ever existed in a one-time email and an
    # AuditLog row — a candidate who missed/deleted that email, or whose
    # client-side app just stayed stuck on the old "Profile Submitted!"
    # screen (see onboarding/page.tsx's own fix for that), had no way to see
    # it again.
    onboarding_rejection_remarks = models.TextField(blank=True, default='')
    # Assessments are opt-in (assigned manually), so a new person starts with nothing waiting. Assigning one
    # flips this to pending; finishing them flips it back to complete.
    assessment_status       = models.CharField(
                                  max_length=20,
                                  choices=ASSESSMENT_CHOICES,
                                  default=ASSESSMENT_COMPLETE,
                              )
    # New hires start on probation; the Confirmation action (see
    # views.EmployeeConfirmView) is the only thing that flips this to
    # 'confirmed'. Existing employees at the time this field was added were
    # backfilled to 'confirmed' by that migration's data step — the default
    # below only governs employees created after this field existed.
    employment_status       = models.CharField(
                                  max_length=20,
                                  choices=EMPLOYMENT_STATUS_CHOICES,
                                  default=EMPLOYMENT_STATUS_PROBATION,
                              )
    confirmation_date       = models.DateField(null=True, blank=True)
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
    # Phase 5A Task A.2 — additive FK to the new CostCenter master; the
    # text column above is kept and NOT yet synced from this ref (Task L
    # deferred, see PHASE5A_REPORT.md).
    cost_center_ref = models.ForeignKey('CostCenter', on_delete=models.SET_NULL, null=True, blank=True, related_name='org_units')
    is_department_level = models.BooleanField(default=False)
    # Deactivate rather than delete once a unit has real history (positions,
    # placements) under it — deleting history is a compliance problem.
    is_active  = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    # Phase 2 (platform_core) — admin-added custom field values, written
    # only through apps.platform_core.services_attributes.
    attributes = models.JSONField(default=dict, blank=True)

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
    # Phase 5A Task A.2 — additive FK to the new Band master.
    band_ref   = models.ForeignKey('Band', on_delete=models.SET_NULL, null=True, blank=True, related_name='job_templates')
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
    # Phase 5A Task A.2/A.3 — additive FKs; text columns kept, not yet synced.
    grade_ref     = models.ForeignKey('Grade', on_delete=models.SET_NULL, null=True, blank=True, related_name='positions')
    designation_ref = models.ForeignKey('Designation', on_delete=models.SET_NULL, null=True, blank=True, related_name='positions')
    job_family    = models.ForeignKey('JobFamily', on_delete=models.SET_NULL, null=True, blank=True, related_name='positions')
    fte           = models.DecimalField(max_digits=3, decimal_places=2, default=1, help_text='Full-time-equivalent fraction for this seat.')
    headcount_budget = models.PositiveSmallIntegerField(default=1)
    is_chief      = models.BooleanField(default=False)
    # Optional — most positions live in the one shared, company-wide tree;
    # set this only when a seat is genuinely tied to one physical branch
    # (e.g. "Recruiter — Kondapur"). Lets the same tree be filtered to a
    # branch-specific view without duplicating OrgUnit/Position per branch.
    branch        = models.ForeignKey(
                        'branch.Branch', on_delete=models.SET_NULL, null=True, blank=True,
                        related_name='positions',
                    )
    # Access follows the seat, not a Role: whoever holds this position today
    # inherits its PositionPermission rows (see core.permissions) and these
    # two scope flags — the same meaning Role.can_manage_team /
    # Role.can_manage_branch have until Roles are removed.
    can_manage_team   = models.BooleanField(default=False, help_text='The holder appears in manager dropdowns and manages a team.')
    can_manage_branch = models.BooleanField(default=False, help_text='The holder has access to every employee and record in their own branch.')
    exclude_from_payroll   = models.BooleanField(default=False, help_text='The holder is left out of payroll processing (e.g. a system/API seat).')
    exclude_from_headcount = models.BooleanField(default=False, help_text='The holder is left out of headcount-style dashboard counts.')
    # Deactivate rather than delete once a position has placement history —
    # deleting history is a compliance problem (Placement.position is
    # on_delete=PROTECT for the same reason).
    is_active     = models.BooleanField(default=True)
    created_at    = models.DateTimeField(auto_now_add=True)
    updated_at    = models.DateTimeField(auto_now=True)
    # Phase 2 (platform_core) — admin-added custom field values, written
    # only through apps.platform_core.services_attributes.
    attributes    = models.JSONField(default=dict, blank=True)

    class Meta:
        db_table = 'hrms_positions'
        ordering = ['title']
        constraints = [
            UniqueConstraint(fields=['org_unit'], condition=Q(is_chief=True), name='position_one_chief_per_unit'),
        ]

    def __str__(self) -> str:
        return f'{self.title} — {self.org_unit.name}'

    @property
    def is_vacant(self) -> bool:
        """Phase 5A Task A.3 — derived, not stored: true if no current
        (open-ended or today-covering) Placement exists for this seat."""
        from django.utils import timezone
        today = timezone.localdate()
        return not self.placements.filter(effective_from__lte=today).filter(
            Q(effective_to__isnull=True) | Q(effective_to__gte=today)
        ).exists()


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


class PositionPermission(models.Model):
    """One permission granted to whoever holds a Position (access follows the seat, not a role).

    Effective permissions for a person = the permissions of the seat they currently hold (their Placement
    covering today) — see core.permissions. Never granted to a person directly.
    """
    id         = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    position   = models.ForeignKey(Position, on_delete=models.CASCADE, related_name='position_permissions')
    permission = models.ForeignKey(Permission, on_delete=models.CASCADE, related_name='position_permissions')
    granted_by = models.ForeignKey('User', on_delete=models.SET_NULL, null=True, blank=True, related_name='+')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'hrms_position_permissions'
        unique_together = ('position', 'permission')

    def __str__(self) -> str:
        return f'{self.position.title} → {self.permission.codename}'


class BaselinePermission(models.Model):
    """A permission EVERY employee has, whatever seat they hold (self-service: own leave, attendance, payslips...).

    Replaces the permissions of the old "default employee" role. Edited by full-access users in Settings.
    """
    id         = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    permission = models.OneToOneField(Permission, on_delete=models.CASCADE, related_name='baseline_grant')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'hrms_baseline_permissions'

    def __str__(self) -> str:
        return f'baseline → {self.permission.codename}'


class EmployeePermission(models.Model):
    """An extra permission granted to ONE employee, on top of the company baseline and the permissions of the seat
    they hold. Lets a single person get access without inventing a separate position for them.

    Additive only: it never removes anything the baseline or the seat gives. It follows the person, not the seat,
    so it stays if they move to another seat. Edited by full-access users in Settings > Access.
    """
    id         = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    employee   = models.ForeignKey('accounts.User', on_delete=models.CASCADE, related_name='extra_permissions')
    permission = models.ForeignKey(Permission, on_delete=models.CASCADE, related_name='employee_grants')
    granted_by = models.ForeignKey('accounts.User', null=True, blank=True, on_delete=models.SET_NULL, related_name='+')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'hrms_employee_permissions'
        constraints = [
            models.UniqueConstraint(fields=['employee', 'permission'], name='employee_permission_uniq'),
        ]

    def __str__(self) -> str:
        return f'{self.employee_id} → {self.permission.codename}'


class HireAction(models.Model):
    """Stage 1 of the two-stage Hire flow — a reservation record created by
    the "Hire an employee" modal (action type, reason, effective date,
    position) BEFORE any User row exists. The hiring wizard then fills in
    the rest against this record; "Hire employee" (Stage 2, HireActionCompleteView)
    is what actually creates the real User — mirroring the same sequence
    EmployeeListCreateView.post already runs today (create_user, assign_position,
    assign_weekly_off, leave allocation, welcome email), just triggered from
    here instead of a single synchronous request.

    Follows SeparationRequest's shape (apps/hrms/models.py) as the closest
    existing effective-dated, stateful action: UUID pk, explicit db_table,
    status choices, created_by, created_at/updated_at.
    """
    REASON_NEW_POSITION      = 'new_position'
    REASON_REPLACEMENT       = 'replacement'
    REASON_BACKFILL          = 'backfill'
    REASON_BUSINESS_EXPANSION = 'business_expansion'
    REASON_REHIRE            = 'rehire'
    REASON_CHOICES = [
        (REASON_NEW_POSITION,       'New position'),
        (REASON_REPLACEMENT,        'Replacement'),
        (REASON_BACKFILL,           'Backfill'),
        (REASON_BUSINESS_EXPANSION, 'Business expansion'),
        (REASON_REHIRE,             'Rehire'),
    ]

    STATUS_DRAFT     = 'draft'
    STATUS_COMPLETED = 'completed'
    STATUS_DISCARDED = 'discarded'
    STATUS_CHOICES = [
        (STATUS_DRAFT,     'Draft'),
        (STATUS_COMPLETED, 'Completed'),
        (STATUS_DISCARDED, 'Discarded'),
    ]

    id             = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    reason         = models.CharField(max_length=30, choices=REASON_CHOICES)
    effective_from = models.DateField()
    position       = models.ForeignKey(Position, on_delete=models.PROTECT, related_name='hire_actions')
    # Blank until the Employment step is saved — the employee number is only
    # ever reserved once employment_type is known (each type has its own
    # EmployeeCodeSeries), never at Stage 1 creation.
    employment_type      = models.CharField(max_length=50, blank=True, choices=User.EMPLOYMENT_TYPE_CHOICES)
    reserved_employee_id = models.CharField(max_length=20, blank=True)
    # Everything else the wizard collects before a real User exists (personal
    # identity, work location/mode, probation/notice period, weekly off/shift
    # picks, salary structure + CTC, tax regime, family/education/asset entries
    # not yet backed by their own row) — one flexible JSON blob rather than a
    # long list of nullable columns for what is, by definition, transient
    # draft state: it's only ever read once, by HireActionCompleteView, to
    # build the real User/Placement/EmployeeSalaryConfig/etc. rows. Matches
    # this app's existing convention for flexible field sets (e.g.
    # LeavePolicy.applicable_* JSON) rather than inventing a new pattern.
    draft_data     = models.JSONField(default=dict, blank=True)
    # Uploaded on the Personal Identity step, before any User row exists —
    # same field type/upload path/validation as User.profile_photo, just
    # living here until Stage 2 copies it onto the real employee record
    # (see HireActionCompleteView).
    photo          = models.ImageField(upload_to=profile_photo_upload_path, null=True, blank=True)
    status         = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_DRAFT, db_index=True)
    created_by     = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='hire_actions_created')
    # Set only once Stage 2 completes — the real, permanent User record.
    created_employee = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True, related_name='hire_action_origin',
    )
    created_at     = models.DateTimeField(auto_now_add=True)
    updated_at     = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'hrms_hire_actions'
        ordering = ['-created_at']

    def __str__(self) -> str:
        return f'Hire — {self.position.title} ({self.get_status_display()})'


def _hire_action_doc_path(instance, filename):
    import os
    return os.path.join('hire_action_documents', str(instance.hire_action_id), os.path.basename(filename))


class HireActionDocument(models.Model):
    """Pre-employee document uploads for the Hire wizard (PAN/Aadhaar on the
    Statutory step, plus every item on the Documents step) — mirrors
    EmployeeDocument's shape but keyed to a HireAction since no User row
    exists yet. Validated against the same DocumentTypeConfig rows real
    employee document uploads use, so the type list never has to be
    maintained twice. Copied onto real EmployeeDocument rows at Stage 2
    (HireActionCompleteView), the same way HireAction.photo above copies
    onto User.profile_photo — then deleted here, since the real
    EmployeeDocument row is the one that matters from that point on."""
    id            = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    hire_action   = models.ForeignKey(HireAction, on_delete=models.CASCADE, related_name='documents')
    document_type = models.CharField(max_length=64)
    # The client-generated (`temp-...`) id of the specific education/
    # experience entry this file belongs to — blank for every other document
    # type, which stay one-slot-per-type (PAN, Aadhaar, Passport, etc). Lets
    # "Attach certificate"/"Attach experience letter" keep one file per
    # qualification/employer instead of one shared slot for the whole step,
    # even though those entries themselves are only real rows (EducationRecord/
    # WorkExperienceRecord) from Stage 2 onward — this field is what makes a
    # per-entry attachment possible before that point.
    entry_ref     = models.CharField(max_length=64, blank=True)
    file          = models.FileField(upload_to=_hire_action_doc_path, storage=AuthenticatedImageKitStorage(), max_length=255)
    file_name     = models.CharField(max_length=255)
    file_size     = models.PositiveBigIntegerField()
    # SHA-256 of the file's bytes — lets the upload view catch the same file
    # being uploaded twice under two different document types (e.g. the PAN
    # photo accidentally re-used for Aadhaar) without re-reading every other
    # file from storage on each new upload. Not a substitute for real content
    # verification (nothing here confirms a "PAN card" upload is actually a
    # PAN card) — just the one cheap, honest check available without a real
    # OCR/ID-verification service.
    content_hash  = models.CharField(max_length=64, blank=True, db_index=True)
    uploaded_at   = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'hrms_hire_action_documents'
        ordering = ['document_type', '-uploaded_at']

    def __str__(self) -> str:
        return f'{self.hire_action_id} — {self.document_type}'


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
    # Populated by the "Perform an action" modal (Employee Directory / Employee
    # Detail page) — covers both its Promotion and Org assignment action types,
    # since both piggyback on this same PUT-driven record. blank=True/no
    # default keeps every pre-existing row (created before this field existed)
    # valid with an empty reason rather than a fabricated one.
    PROMOTION_REASON_PERFORMANCE   = 'performance_based'
    PROMOTION_REASON_ROLE_CHANGE   = 'role_change'
    PROMOTION_REASON_MARKET        = 'market_correction'
    PROMOTION_REASON_RESTRUCTURING = 'restructuring'
    ORG_REASON_TEAM_RESTRUCTURING  = 'team_restructuring'
    ORG_REASON_MANAGER_CHANGE      = 'manager_change'
    ORG_REASON_LOCATION_TRANSFER   = 'location_transfer'
    ORG_REASON_DEPARTMENT_CHANGE   = 'department_change'
    REASON_OTHER                   = 'other'
    REASON_CHOICES = [
        (PROMOTION_REASON_PERFORMANCE,   'Performance based'),
        (PROMOTION_REASON_ROLE_CHANGE,   'Role change'),
        (PROMOTION_REASON_MARKET,        'Market correction'),
        (PROMOTION_REASON_RESTRUCTURING, 'Restructuring'),
        (ORG_REASON_TEAM_RESTRUCTURING,  'Team restructuring'),
        (ORG_REASON_MANAGER_CHANGE,      'Manager change'),
        (ORG_REASON_LOCATION_TRANSFER,   'Location transfer'),
        (ORG_REASON_DEPARTMENT_CHANGE,   'Department change'),
        (REASON_OTHER,                   'Other'),
    ]
    reason = models.CharField(max_length=30, choices=REASON_CHOICES, blank=True, default='')
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
    PURPOSE_RESET  = 'reset'
    PURPOSE_INVITE = 'invite'
    PURPOSE_CHOICES = (
        (PURPOSE_RESET,  'Forgot-password reset'),
        (PURPOSE_INVITE, 'New-hire account activation invite'),
    )

    STATUS_SENT      = 'sent'
    STATUS_OPENED    = 'opened'
    STATUS_ACTIVATED = 'activated'
    STATUS_EXPIRED   = 'expired'

    id         = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user       = models.ForeignKey(User, on_delete=models.CASCADE, related_name='reset_tokens')
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField(db_index=True)
    is_used    = models.BooleanField(default=False, db_index=True)
    # purpose/opened_at only matter for PURPOSE_INVITE — a forgot-password
    # token is a one-shot OTP-adjacent flow with no "did they open the
    # email" concept the admin side needs to track; a hire invite link is
    # exactly the kind of thing HR needs Sent/Opened/Activated/Expired
    # visibility into (was it delivered? did the new hire even see it?).
    purpose    = models.CharField(max_length=10, choices=PURPOSE_CHOICES, default=PURPOSE_RESET)
    opened_at  = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = 'hrms_password_reset_tokens'

    def __str__(self) -> str:
        return f'ResetToken({self.user.email}, used={self.is_used})'

    def is_valid(self) -> bool:
        return not self.is_used and timezone.now() < self.expires_at

    @property
    def status(self) -> str:
        """Sent -> Opened -> Activated, or Expired if the window passed
        before either of those happened. Only meaningful for invite tokens,
        but computed generically since nothing else depends on purpose."""
        if self.is_used:
            return self.STATUS_ACTIVATED
        if timezone.now() >= self.expires_at:
            return self.STATUS_EXPIRED
        if self.opened_at:
            return self.STATUS_OPENED
        return self.STATUS_SENT

    def mark_opened(self) -> None:
        if not self.opened_at:
            self.opened_at = timezone.now()
            self.save(update_fields=['opened_at'])

    @classmethod
    @transaction.atomic
    def create_for_user(cls, user: User, *, purpose: str = PURPOSE_RESET, validity_hours: float = 1) -> PasswordResetToken:
        """Invalidate all outstanding tokens of this purpose for this user
        then issue a new one — a resent invite must make the previous
        link stop working, same principle as a repeated forgot-password
        request already had for PURPOSE_RESET."""
        cls.objects.filter(user=user, purpose=purpose, is_used=False).update(is_used=True)
        return cls.objects.create(
            user       = user,
            purpose    = purpose,
            expires_at = timezone.now() + timedelta(hours=validity_hours),
        )


# ─── External API Keys ──────────────────────────────────────────────────────

class ExternalAPIKey(models.Model):
    """
    Credentials for another internal system (e.g. the Project Budget &
    Tracking tool) to call this app's read-only external APIs — those
    systems have no HRMS login of their own (no User row, no JWT session),
    so the normal cookie-based auth flow doesn't apply to them.

    Only the SHA-256 hash of the raw key is ever stored, never the key
    itself — the raw value is shown to whoever generates it exactly once
    (same principle as a password: this app should never be able to show
    it again, only verify a presented key against the stored hash).
    """
    id            = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name          = models.CharField(
                        max_length=100, unique=True,
                        help_text='Which system this key belongs to, e.g. "project_budget_tool".',
                    )
    key_hash      = models.CharField(max_length=64, unique=True, db_index=True)
    is_active     = models.BooleanField(default=True)
    created_by    = models.ForeignKey(
                        User, on_delete=models.SET_NULL, null=True, blank=True,
                        related_name='created_external_api_keys',
                    )
    created_at    = models.DateTimeField(auto_now_add=True)
    last_used_at  = models.DateTimeField(null=True, blank=True)

    # Phase 4 Task J — additive scoping. Existing keys get
    # scope_codenames=[] (meaning "no explicit scope recorded yet" — see
    # the migration note in PHASE4_REPORT.md: this phase does NOT attempt
    # to reverse-engineer which endpoints each existing key currently
    # calls into an equivalent scope set, since getting that wrong would
    # either silently break a live integration or silently widen it).
    # Enforcement of scope_codenames is NOT wired into the existing
    # external-API views in this phase — see PHASE4_REPORT.md.
    scope_codenames = models.JSONField(default=list, blank=True, help_text='Permission codenames this key is restricted to. Empty = unrestricted (legacy behaviour, unchanged).')
    legal_entity  = models.ForeignKey('platform_core.LegalEntity', on_delete=models.SET_NULL, null=True, blank=True, related_name='+')
    ip_allowlist  = models.JSONField(default=list, blank=True, help_text='CIDR strings. Empty = no IP restriction (legacy behaviour, unchanged).')
    expires_at    = models.DateTimeField(null=True, blank=True)
    rotated_from  = models.ForeignKey('self', on_delete=models.SET_NULL, null=True, blank=True, related_name='rotated_to')
    rate_limit_tier = models.CharField(max_length=20, blank=True, default='', help_text='Free-text tier label consumed by the throttle layer; empty = today\'s existing throttle behaviour, unchanged.')

    class Meta:
        db_table = 'accounts_external_api_keys'
        ordering = ['name']

    def __str__(self):
        return f'{self.name} ({"active" if self.is_active else "revoked"})'

    def is_expired(self) -> bool:
        return bool(self.expires_at and self.expires_at <= timezone.now())

    def allows_scope(self, codename: str) -> bool:
        """Empty scope_codenames = unrestricted, matching every existing
        key's current (unscoped) behaviour exactly — Task J.2's "existing
        keys keep working" requirement."""
        return not self.scope_codenames or codename in self.scope_codenames

    def allows_ip(self, ip_address: str) -> bool:
        if not self.ip_allowlist:
            return True
        import ipaddress
        try:
            addr = ipaddress.ip_address(ip_address)
        except ValueError:
            return False
        return any(addr in ipaddress.ip_network(cidr, strict=False) for cidr in self.ip_allowlist)


class APIKeyUsageLog(models.Model):
    """Task J.1's usage log — endpoint, status, timestamp, IP. NEVER a
    payload (Rule 6 — never log sensitive values)."""
    api_key    = models.ForeignKey(ExternalAPIKey, on_delete=models.CASCADE, related_name='usage_logs')
    endpoint   = models.CharField(max_length=255)
    status_code = models.PositiveSmallIntegerField()
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    occurred_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'accounts_api_key_usage_logs'
        ordering = ['-occurred_at']
        indexes = [models.Index(fields=['api_key', 'occurred_at'], name='akul_key_time_idx')]

    def __str__(self):
        return f'{self.api_key_id}:{self.endpoint} ({self.status_code})'


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
    # Encrypted at rest (Fernet, core/encrypted_fields.py) — this is a real,
    # working credential (a mailbox password or a provider API key like
    # Resend's), not a reference to one, so it needs the same protection as
    # PAN/bank details elsewhere in this app. max_length=512, not 255 — Fernet
    # ciphertext (IV + HMAC + padded ciphertext, base64-encoded) runs to
    # roughly 1.4x the plaintext length plus ~75 bytes of fixed overhead, so
    # a 255-char plaintext (this field's own historical max, and long enough
    # for most provider API keys) needs headroom well past 255 once encrypted.
    password            = EncryptedCharField(max_length=512)
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
            prefix = cfg.prefix or 'EMP'
            # This counter and EmployeeCodeSeries' per-employment-type
            # counters below share the same default prefix ('EMP') but never
            # coordinate with each other — two independently-incrementing
            # sequences using the same prefix WILL eventually both produce
            # the same ID (confirmed in production: two real employees ended
            # up with the identical employee_id, breaking every _get_employee
            # lookup for that code). Skipping forward past any sequence
            # number already claimed by a real User is a collision-proof
            # guard regardless of how out of sync the two counters get.
            while True:
                seq    = str(cfg.next_sequence).zfill(cfg.padding)
                emp_id = f'{prefix}{seq}'
                cfg.next_sequence += 1
                if not User.objects.filter(employee_id=emp_id).exists():
                    break
            cfg.save(update_fields=['next_sequence', 'updated_at'])
        return emp_id


# ─── Employee Code Series (per employment type) ──────────────────────────────

class EmployeeCodeSeries(models.Model):
    """One numbering series per employment type — e.g. Permanent hires get
    EMP00001, EMP00002…, Interns get their own INT00001 series, etc. Replaces
    EmployeeCodeSettings' single global counter for the Hire wizard (which
    reserves a number once Employment type is chosen, before the rest of
    hiring is complete) — EmployeeCodeSettings itself is left in place and
    still used by its 3 existing call sites (plain employee creation, portal-
    to-employee conversion, bulk import) so nothing that already worked
    changes; only the new Hire wizard calls generate_employee_id_for_type()."""
    employment_type = models.CharField(max_length=50, unique=True, choices=User.EMPLOYMENT_TYPE_CHOICES)
    prefix          = models.CharField(max_length=10, default='EMP')
    padding         = models.PositiveSmallIntegerField(default=5)
    next_sequence   = models.PositiveIntegerField(default=1)
    updated_at      = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'hrms_employee_code_series'
        ordering = ['employment_type']

    def __str__(self) -> str:
        return f'{self.employment_type}: {self.prefix} (padding {self.padding})'

    @classmethod
    def generate_employee_id_for_type(cls, employment_type: str) -> str:
        """Same reserve-and-increment pattern as EmployeeCodeSettings.generate_employee_id,
        scoped to one series per employment type. get_or_create's defaults seed
        a brand-new employment type's series from EmployeeCodeSettings' own
        current prefix/padding (not a hardcoded 'EMP'/5) so a type added after
        this feature shipped still starts from a sensible, already-configured
        format rather than silently reverting to the class default."""
        from django.db import transaction as _tx

        with _tx.atomic():
            base = EmployeeCodeSettings.get()
            series = cls.objects.select_for_update().get_or_create(
                employment_type=employment_type,
                defaults={'prefix': base.prefix, 'padding': base.padding, 'next_sequence': 1},
            )[0]
            # Same collision guard as EmployeeCodeSettings.generate_employee_id
            # above — this series and that singleton counter (and every other
            # employment type's own series) can all produce the same prefix,
            # and increment completely independently of each other.
            while True:
                seq    = str(series.next_sequence).zfill(series.padding)
                emp_id = f'{series.prefix}{seq}'
                series.next_sequence += 1
                if not User.objects.filter(employee_id=emp_id).exists():
                    break
            series.save(update_fields=['next_sequence', 'updated_at'])
        return emp_id

    @classmethod
    def release_employee_id(cls, employment_type: str, emp_id: str) -> bool:
        """Gives a reserved number back when its draft is thrown away, but only if it is still the newest number of its
        series (nothing was issued after it) and no employee holds it. Otherwise it stays a gap, as real HRMS/payroll
        numbering tolerates, rather than risk handing the same number out twice. True when the number was returned."""
        from django.db import transaction as _tx

        with _tx.atomic():
            series = cls.objects.select_for_update().filter(employment_type=employment_type).first()
            if series is None or not emp_id.startswith(series.prefix):
                return False
            digits = emp_id[len(series.prefix):]
            if not digits.isdigit() or int(digits) != series.next_sequence - 1:
                return False
            if User.objects.filter(employee_id=emp_id).exists():
                return False
            series.next_sequence -= 1
            series.save(update_fields=['next_sequence', 'updated_at'])
        return True


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
    # Only meaningful for CATEGORY_POLICY documents (e.g. "3.2") — left blank
    # for forms/templates/other where a version string has no meaning. The
    # ESS Policies & assets tab falls back to showing the category alone
    # when this is blank rather than fabricating a version.
    version         = models.CharField(max_length=20, blank=True, default='')
    effective_date  = models.DateField(null=True, blank=True)
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
    MARITAL_SEPARATED = 'separated'
    MARITAL_CHOICES  = [
        (MARITAL_SINGLE,   'Single'),
        (MARITAL_MARRIED,  'Married'),
        (MARITAL_DIVORCED, 'Divorced'),
        (MARITAL_WIDOWED,  'Widowed'),
        (MARITAL_SEPARATED, 'Separated'),
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
    # Set at hire time on the Hire wizard's Personal identity step.
    salutation         = models.CharField(max_length=10, blank=True)
    middle_name        = models.CharField(max_length=100, blank=True)
    # Defaults to "salutation first middle last" if never explicitly
    # overridden — see the Hire wizard's own "+ Suggest" button — but stored
    # as its own field (not derived on every read) since HR can rename it
    # afterward independent of the legal name fields on User.full_name.
    display_name       = models.CharField(max_length=150, blank=True)
    nationality        = models.CharField(max_length=100, blank=True, default='Indian')
    place_of_birth     = models.CharField(max_length=150, blank=True)
    date_of_birth      = models.DateField(null=True, blank=True)
    gender             = models.CharField(max_length=10, choices=GENDER_CHOICES, blank=True)
    marital_status     = models.CharField(max_length=20, choices=MARITAL_CHOICES, blank=True)
    father_name        = models.CharField(max_length=150, blank=True)
    # Collected on the Hire wizard's Personal identity step (HireWizardClient
    # .identityExtras.mother_name) since that UI was first built, but never
    # actually had a real column to persist to — HireActionCompleteView
    # silently dropped it at hire completion. Added now alongside
    # languages_known so both close that gap for real.
    mother_name        = models.CharField(max_length=150, blank=True)
    # Free-text, comma-separated (matches LanguagesSelect.tsx's own stored
    # format) rather than a related table — this is display-only metadata,
    # not a field anything else joins against.
    languages_known    = models.CharField(max_length=255, blank=True)
    blood_group        = models.CharField(max_length=5, choices=BLOOD_CHOICES, blank=True)
    # Distinct from User.email (the work email, used for login) — a
    # personal address the employee can be reached on outside the org,
    # shown alongside work email on the profile record.
    personal_email     = models.EmailField(blank=True)
    current_address       = models.TextField(blank=True)
    # current_address/permanent_address hold only the house/street/area line —
    # village, district, state and PIN code are broken out into their own
    # columns below so each is independently reportable/filterable rather than
    # buried inside one free-text blob (mirrors Company's address/city/state/
    # pin_code split above). *_address_line2 is a purely optional second line
    # (apartment/floor/landmark) — never required, unlike line 1.
    current_address_line2 = models.CharField(max_length=200, blank=True)
    current_village    = models.CharField(max_length=150, blank=True)
    current_district   = models.CharField(max_length=100, blank=True)
    current_state      = models.CharField(max_length=100, blank=True)
    current_pin_code   = models.CharField(max_length=6, blank=True)
    permanent_address  = models.TextField(blank=True)
    permanent_address_line2 = models.CharField(max_length=200, blank=True)
    permanent_village  = models.CharField(max_length=150, blank=True)
    permanent_district = models.CharField(max_length=100, blank=True)
    permanent_state    = models.CharField(max_length=100, blank=True)
    permanent_pin_code = models.CharField(max_length=6, blank=True)
    # When True, permanent_* above are kept mirroring current_* on every save
    # (see save() below) instead of being entered separately — most
    # employees' permanent address is the same as where they currently live,
    # so this avoids asking for the same district/state/PIN twice. Mirrors
    # Company.communication_address_same_as_registered's role, except that
    # field only relaxes a validation requirement — this one actively
    # overwrites permanent_* on save so every reader of those columns
    # (HR's employee profile, the approval drawer, self-service "My
    # Profile") gets a correct value without needing its own fallback logic.
    permanent_same_as_current = models.BooleanField(default=False)

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

    # Bank-change verification gate — a self-service edit to *already-filled*
    # bank details (the same condition _alert_bank_details_changed() below
    # already treats as suspicious) is held here pending HR review instead of
    # overwriting the live fields payroll actually reads. First-time entry
    # (empty -> filled) skips this and writes directly — no fraud risk in
    # giving your bank details for the first time. See _save_profile_step()
    # in views/shared.py for where this gate is actually applied.
    BANK_CHANGE_NONE     = 'none'
    BANK_CHANGE_PENDING  = 'pending'
    BANK_CHANGE_STATUS_CHOICES = [
        (BANK_CHANGE_NONE,    'No pending change'),
        (BANK_CHANGE_PENDING, 'Pending HR review'),
    ]
    bank_change_status       = models.CharField(max_length=10, choices=BANK_CHANGE_STATUS_CHOICES, default=BANK_CHANGE_NONE, blank=True)
    bank_change_requested_at = models.DateTimeField(null=True, blank=True)
    pending_account_number      = EncryptedCharField(max_length=255, blank=True)
    pending_ifsc_code           = EncryptedCharField(max_length=255, blank=True)
    pending_bank_name           = models.CharField(max_length=200, blank=True)
    pending_bank_branch_name    = models.CharField(max_length=200, blank=True)
    pending_account_holder_name = models.CharField(max_length=150, blank=True)
    pending_account_type        = models.CharField(max_length=10, choices=ACCOUNT_CHOICES, blank=True)

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
    aadhaar_number     = EncryptedCharField(max_length=255, blank=True, help_text='12-digit Aadhaar number issued by UIDAI')

    # Provident Fund / ESI coverage — uan_number/esi_number above already
    # store the *numbers*; these are the separate "is this employee covered
    # at all" declarations and PF's own member ID, none of which existed
    # before (uan_number alone doesn't say whether PF applies).
    pf_covered  = models.BooleanField(default=True, help_text='Whether this employee is covered under the Provident Fund scheme')
    pf_number   = EncryptedCharField(max_length=255, blank=True, help_text='EPF member/account ID (distinct from the UAN)')
    esi_covered = models.BooleanField(default=False, help_text='Whether this employee is covered under ESI — normally auto-eligible below the wage threshold')

    DISABILITY_VISUAL       = 'visual'
    DISABILITY_HEARING      = 'hearing'
    DISABILITY_LOCOMOTOR    = 'locomotor'
    DISABILITY_INTELLECTUAL = 'intellectual'
    DISABILITY_MULTIPLE     = 'multiple'
    DISABILITY_OTHER        = 'other'
    DISABILITY_TYPE_CHOICES = [
        (DISABILITY_VISUAL,       'Visual'),
        (DISABILITY_HEARING,      'Hearing'),
        (DISABILITY_LOCOMOTOR,    'Locomotor'),
        (DISABILITY_INTELLECTUAL, 'Intellectual'),
        (DISABILITY_MULTIPLE,     'Multiple'),
        (DISABILITY_OTHER,        'Other'),
    ]
    # Voluntary self-declarations — record-keeping obligations under the
    # RPwD Act 2016 and EPF Form 11 respectively, not something a private
    # employer requires for its own sake. Neither existed on this model at all.
    is_disabled                   = models.BooleanField(default=False, help_text='Specially abled declaration (RPwD Act 2016)')
    disability_type               = models.CharField(max_length=20, choices=DISABILITY_TYPE_CHOICES, blank=True)
    disability_percentage         = models.PositiveSmallIntegerField(null=True, blank=True)
    disability_certificate_number = models.CharField(max_length=50, blank=True)
    is_international_worker       = models.BooleanField(default=False, help_text='International Worker declaration (EPF Form 11)')
    international_worker_country  = models.CharField(max_length=100, blank=True)
    passport_number    = EncryptedCharField(max_length=255, blank=True)
    passport_expiry    = models.DateField(null=True, blank=True)
    passport_issue_date       = models.DateField(null=True, blank=True)
    passport_place_of_issue   = models.CharField(max_length=100, blank=True)
    passport_country_of_issue = models.CharField(max_length=100, blank=True)
    # Free text, not a structured skills-tag list — this is a hire-time
    # summary ("React, payroll operations, team leadership"), not a
    # searchable skills matrix; building a real tag/taxonomy system is a
    # separate feature, not something to half-build here.
    core_skills    = models.CharField(max_length=500, blank=True)
    certifications = models.CharField(max_length=500, blank=True)

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

    _PERMANENT_ADDRESS_FIELDS = (
        'permanent_address', 'permanent_address_line2', 'permanent_village',
        'permanent_district', 'permanent_state', 'permanent_pin_code',
    )

    def save(self, *args, **kwargs):
        # Keep the blind index in sync with pan_number on every save — this
        # runs before get_prep_value() encrypts it, so self.pan_number here
        # is always the current plaintext regardless of whether this row was
        # previously encrypted (see EncryptedCharField's InvalidToken fallback).
        self.pan_number_hash = blind_index(self.pan_number) if self.pan_number else ''

        # Mirror current_* into permanent_* whenever the "same as current"
        # flag is on — done here rather than in each of the several call
        # sites that can save this model (onboarding step save, HR employee
        # edit, self-service "My Profile") so it can never drift out of sync
        # depending on which path was used. Runs on every save while the flag
        # is set, not just when current_* actually changed, so a profile that
        # somehow got out of sync self-heals on its next save.
        if self.permanent_same_as_current:
            self.permanent_address  = self.current_address
            self.permanent_address_line2 = self.current_address_line2
            self.permanent_village  = self.current_village
            self.permanent_district = self.current_district
            self.permanent_state    = self.current_state
            self.permanent_pin_code = self.current_pin_code
            update_fields = kwargs.get('update_fields')
            if update_fields is not None:
                kwargs['update_fields'] = list(set(update_fields) | set(self._PERMANENT_ADDRESS_FIELDS))

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

    def submit_bank_change(self, fields: dict) -> None:
        """Self-service edit to already-filled bank details — held in the
        pending_* columns instead of overwriting what payroll reads, until
        HR reviews it (see approve_bank_change/reject_bank_change)."""
        self.pending_account_number      = fields.get('account_number', self.account_number)
        self.pending_ifsc_code           = fields.get('ifsc_code', self.ifsc_code)
        self.pending_bank_name           = fields.get('bank_name', self.bank_name)
        self.pending_bank_branch_name    = fields.get('bank_branch_name', self.bank_branch_name)
        self.pending_account_holder_name = fields.get('account_holder_name', self.account_holder_name)
        self.pending_account_type        = fields.get('account_type', self.account_type)
        self.bank_change_status = self.BANK_CHANGE_PENDING
        self.bank_change_requested_at = timezone.now()
        self.save(update_fields=[
            'pending_account_number', 'pending_ifsc_code', 'pending_bank_name',
            'pending_bank_branch_name', 'pending_account_holder_name', 'pending_account_type',
            'bank_change_status', 'bank_change_requested_at',
        ])
        self._notify_bank_change_submitted()

    def approve_bank_change(self, actor=None) -> None:
        self.account_number      = self.pending_account_number
        self.ifsc_code           = self.pending_ifsc_code
        self.bank_name           = self.pending_bank_name
        self.bank_branch_name    = self.pending_bank_branch_name
        self.account_holder_name = self.pending_account_holder_name
        self.account_type        = self.pending_account_type
        self._clear_pending_bank_change()
        self._changed_by = actor
        self.save()
        self._notify_bank_change_decision(approved=True)

    def reject_bank_change(self, actor=None) -> None:
        self._clear_pending_bank_change()
        self.save(update_fields=[
            'pending_account_number', 'pending_ifsc_code', 'pending_bank_name',
            'pending_bank_branch_name', 'pending_account_holder_name', 'pending_account_type',
            'bank_change_status', 'bank_change_requested_at',
        ])
        self._notify_bank_change_decision(approved=False)

    def _clear_pending_bank_change(self) -> None:
        self.pending_account_number = ''
        self.pending_ifsc_code = ''
        self.pending_bank_name = ''
        self.pending_bank_branch_name = ''
        self.pending_account_holder_name = ''
        self.pending_account_type = ''
        self.bank_change_status = self.BANK_CHANGE_NONE
        self.bank_change_requested_at = None

    def _notify_bank_change_submitted(self) -> None:
        try:
            from apps.notifications.models import Notification
            from apps.notifications.signals import _push_live
            from core.access import users_with_permission
            hr_users = User.objects.filter(users_with_permission('employees.edit'), is_active=True).distinct()
            for hr_user in hr_users:
                notification = Notification.objects.create(
                    user=hr_user,
                    title='Bank detail change awaiting review',
                    message=(
                        f'{self.user.full_name or self.user.email} submitted a change to their '
                        'salary bank account details — review before it takes effect for payroll.'
                    ),
                    notification_type='approval_request', module='employees',
                )
                _push_live(notification)
        except Exception:
            pass

    def _notify_bank_change_decision(self, *, approved: bool) -> None:
        try:
            from apps.notifications.models import Notification
            from apps.notifications.signals import _push_live
            notification = Notification.objects.create(
                user=self.user,
                title='Bank detail change ' + ('approved' if approved else 'rejected'),
                message=(
                    'Your requested bank detail change has been approved and now applies to payroll.'
                    if approved else
                    'Your requested bank detail change was rejected by HR. Your previous bank details remain in effect.'
                ),
                notification_type='approval_result', module='employees',
            )
            _push_live(notification)
        except Exception:
            pass

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


EDUCATION_LEVEL_SSC          = 'ssc'
EDUCATION_LEVEL_INTERMEDIATE = 'intermediate'
EDUCATION_LEVEL_DIPLOMA      = 'diploma'
EDUCATION_LEVEL_BACHELORS    = 'bachelors'
EDUCATION_LEVEL_MASTERS      = 'masters'
EDUCATION_LEVEL_DOCTORATE    = 'doctorate'

EDUCATION_LEVEL_OTHER = 'other'

EDUCATION_LEVEL_CHOICES = [
    (EDUCATION_LEVEL_SSC,          'SSC / 10th'),
    (EDUCATION_LEVEL_INTERMEDIATE, 'Intermediate / 12th'),
    (EDUCATION_LEVEL_DIPLOMA,      'Diploma'),
    (EDUCATION_LEVEL_BACHELORS,    "Bachelor's"),
    (EDUCATION_LEVEL_MASTERS,      "Master's"),
    (EDUCATION_LEVEL_DOCTORATE,    'Doctorate'),
    (EDUCATION_LEVEL_OTHER,        'Other'),
]

# Highest-first — used by services_education_experience.py to pick which
# single entry to mirror onto EmployeeProfile's legacy flat fields (the
# "highest qualification actually on file", not just whichever was edited
# most recently). "Other" ranks lowest — a real recognized level always
# wins for the legacy summary field unless "Other" is literally the only
# thing on file.
EDUCATION_LEVEL_RANK = [
    EDUCATION_LEVEL_DOCTORATE, EDUCATION_LEVEL_MASTERS, EDUCATION_LEVEL_BACHELORS,
    EDUCATION_LEVEL_DIPLOMA, EDUCATION_LEVEL_INTERMEDIATE, EDUCATION_LEVEL_SSC,
    EDUCATION_LEVEL_OTHER,
]


class EducationExperienceFieldConfig(models.Model):
    """Show/require toggles for the optional fields on each Education/
    Experience list entry (EducationRecord/WorkExperienceRecord below).

    Deliberately NOT the same mechanism as OnboardingFieldConfig — that
    system is "one config row = one flat scalar value" per employee, which
    is exactly what stopped fitting once Education/Experience became
    genuine repeatable lists (see EducationRecord's own docstring). This is
    a much narrower, fixed set of rows: HR can show/hide and require any of
    the *existing* optional fields on an entry, but can't add a brand-new
    custom field the way OnboardingFieldConfig allows — every entry still
    needs somewhere to store an arbitrary new value, and building that for
    a repeatable list (vs. one flat profile) is a bigger, separate feature.

    Level/Institution (education) and Employer Name/Designation
    (experience) are the structural minimum identifying an entry and are
    intentionally absent here — always shown, always required, not
    configurable. Everything else on an entry has a row here, seeded once
    by migration, visible=True/required=False by default; HR can only
    toggle visible/required on existing rows, never create or delete one."""

    LIST_EDUCATION  = 'education'
    LIST_EXPERIENCE = 'experience'
    LIST_TYPE_CHOICES = [
        (LIST_EDUCATION,  'Education'),
        (LIST_EXPERIENCE, 'Experience'),
    ]

    id        = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    list_type = models.CharField(max_length=20, choices=LIST_TYPE_CHOICES)
    field_key = models.CharField(max_length=50)
    label     = models.CharField(max_length=100)
    visible   = models.BooleanField(default=True)
    required  = models.BooleanField(default=False)
    order     = models.PositiveSmallIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'hrms_education_experience_field_configs'
        unique_together = ('list_type', 'field_key')
        ordering = ['list_type', 'order']

    def __str__(self) -> str:
        return f'{self.list_type}.{self.field_key}'


class EducationRecord(models.Model):
    """One row per qualification an employee has completed — a genuine,
    unbounded, add/remove-any-number-of-entries list (matching
    WorkExperienceRecord below, and real HRMS practice — Keka's own
    Education card uses this same degree/institution/percentage/date-range
    shape, confirmed from their help docs). `level` is a fixed set of common
    qualifications (SSC through Doctorate) plus `EDUCATION_LEVEL_OTHER`,
    which pairs with `custom_level_label` for anything not covered (a
    professional certification, etc.) — `display_label()` returns whichever
    of the two is the right one to show. No unique-per-level constraint:
    two Bachelor's degrees, or two "Other" certifications, are both valid.
    See EDUCATION_LEVEL_RANK for how these feed EmployeeProfile's legacy
    flat education fields (highest_qualification etc.) — those stay as an
    auto-synced summary for the other UI surfaces that haven't been rebuilt
    to read this table directly yet (Employee Detail's own Edit Employee
    tab, My Profile, the candidate-review Onboarding Drawer)."""
    id                  = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    employee            = models.ForeignKey('User', on_delete=models.CASCADE, related_name='education_records')
    level               = models.CharField(max_length=20, choices=EDUCATION_LEVEL_CHOICES)
    custom_level_label  = models.CharField(max_length=100, blank=True)
    institution         = models.CharField(max_length=200, blank=True)
    specialization      = models.CharField(max_length=200, blank=True)
    # Free text, not a numeric field — real-world grading varies ("85%",
    # "8.5 CGPA", "First Class") and this codebase has no reason to
    # normalize across those schemes.
    percentage          = models.CharField(max_length=20, blank=True)
    start_date          = models.DateField(null=True, blank=True)
    end_date            = models.DateField(null=True, blank=True)
    order               = models.PositiveSmallIntegerField(default=0)
    # Phase 5A Task G.1 — structured score, parsed best-effort from
    # `percentage` where possible; `percentage` itself is untouched.
    SCORE_TYPE_PERCENTAGE = 'percentage'
    SCORE_TYPE_CGPA = 'cgpa'
    SCORE_TYPE_GRADE = 'grade'
    SCORE_TYPE_CHOICES = [(SCORE_TYPE_PERCENTAGE, 'Percentage'), (SCORE_TYPE_CGPA, 'CGPA'), (SCORE_TYPE_GRADE, 'Grade')]
    score_type          = models.CharField(max_length=20, choices=SCORE_TYPE_CHOICES, blank=True)
    score_value         = models.DecimalField(max_digits=6, decimal_places=2, null=True, blank=True)
    score_scale         = models.DecimalField(max_digits=6, decimal_places=2, null=True, blank=True, help_text='e.g. 10 for a CGPA out of 10.')
    is_highest          = models.BooleanField(default=False, help_text='Derived by EDUCATION_LEVEL_RANK, admin-overridable.')
    is_completed        = models.BooleanField(default=True)
    created_at          = models.DateTimeField(auto_now_add=True)
    updated_at          = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'hrms_education_records'
        ordering = ['order', '-end_date']

    def __str__(self) -> str:
        return f'{self.employee.full_name} — {self.display_label()}'

    def display_label(self) -> str:
        if self.level == EDUCATION_LEVEL_OTHER and self.custom_level_label:
            return self.custom_level_label
        return self.get_level_display()

    def has_any_data(self) -> bool:
        return bool(self.institution or self.specialization or self.percentage or self.start_date or self.end_date)


class WorkExperienceRecord(models.Model):
    """One row per previous employer — a genuine, unbounded, add/remove-any-
    number-of-entries list (unlike EducationRecord's fixed checklist above).
    `end_date=None` means "currently working there" (only meaningful for a
    record an employee is adding about a concurrent/most-recent job before
    joining here — this table is their history prior to this company, not
    their employment here). `order` is manually re-sequenced by the
    frontend on add/remove so the list displays in the sequence the
    employee entered it, independent of `start_date` (which may be blank).
    See EmployeeProfile's legacy previous_employer/previous_designation/
    leaving_reason fields for the auto-synced single-entry summary other
    surfaces still read — never computed/summed here (see
    EmployeeProfile.total_experience_years, still a separate manual field,
    not derived from these rows — accurately summing possibly-overlapping
    or open-ended employment ranges is out of scope)."""
    id                  = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    EMPLOYMENT_TYPE_CHOICES = [
        ('full_time',  'Full-time'),
        ('part_time',  'Part-time'),
        ('internship', 'Internship'),
        ('contract',   'Contract'),
        ('freelance',  'Freelance'),
    ]

    employee            = models.ForeignKey('User', on_delete=models.CASCADE, related_name='experience_records')
    employer_name       = models.CharField(max_length=200)
    designation         = models.CharField(max_length=200, blank=True)
    employment_type     = models.CharField(max_length=20, choices=EMPLOYMENT_TYPE_CHOICES, blank=True)
    start_date          = models.DateField(null=True, blank=True)
    end_date            = models.DateField(null=True, blank=True)
    responsibilities    = models.TextField(blank=True)
    reason_for_leaving  = models.TextField(blank=True)
    order               = models.PositiveSmallIntegerField(default=0)
    # Phase 5A Task G.2 — `country` is new; `employment_type` itself is
    # NOT touched here (converting it to the shared EMPLOYMENT_TYPE
    # lookup is explicitly coordinated with Phase 5B, which owns
    # User.employee_type's conversion — not done in this pass).
    country             = models.ForeignKey('platform_core.Country', on_delete=models.SET_NULL, null=True, blank=True, related_name='+')
    is_verified         = models.BooleanField(default=False)
    verified_by         = models.ForeignKey('User', on_delete=models.SET_NULL, null=True, blank=True, related_name='+')
    created_at          = models.DateTimeField(auto_now_add=True)
    updated_at          = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'hrms_work_experience_records'
        ordering = ['order', '-start_date']

    def __str__(self) -> str:
        return f'{self.employee.full_name} — {self.employer_name}'


class FamilyMember(models.Model):
    """One row per dependant/family member — a genuine, unbounded add/remove
    list (same shape as WorkExperienceRecord above), captured for both
    emergency/EPF-nomination purposes. `is_dependent` mirrors the mockup's
    own per-relationship default (Spouse/Child default Yes, Sibling No) —
    enforced client-side only, stored as submitted."""
    id               = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    RELATIONSHIP_CHOICES = [
        ('father',  'Father'),
        ('mother',  'Mother'),
        ('spouse',  'Spouse'),
        ('child',   'Child'),
        ('sibling', 'Sibling'),
    ]
    GENDER_CHOICES = [
        ('male',   'Male'),
        ('female', 'Female'),
        ('other',  'Other'),
    ]

    employee     = models.ForeignKey('User', on_delete=models.CASCADE, related_name='family_members')
    name         = models.CharField(max_length=150)
    relationship = models.CharField(max_length=10, choices=RELATIONSHIP_CHOICES)
    date_of_birth = models.DateField(null=True, blank=True)
    gender       = models.CharField(max_length=10, choices=GENDER_CHOICES, blank=True)
    blood_group  = models.CharField(max_length=5, blank=True)
    is_dependent = models.BooleanField(default=False)
    order        = models.PositiveSmallIntegerField(default=0)
    # Phase 5A Task F.1 — best-effort split of `name`, original preserved.
    first_name   = models.CharField(max_length=100, blank=True)
    last_name    = models.CharField(max_length=100, blank=True)
    is_nominee_eligible = models.BooleanField(default=True)
    occupation   = models.CharField(max_length=150, blank=True)
    created_at   = models.DateTimeField(auto_now_add=True)
    updated_at   = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'hrms_family_members'
        ordering = ['order', 'created_at']

    def __str__(self) -> str:
        return f'{self.employee.full_name} — {self.name} ({self.get_relationship_display()})'


class EPFNominee(models.Model):
    """One row per EPF/gratuity nominee. The nominee's name/relationship
    come from FamilyMember rather than being re-typed — matches the
    mockup's own "pick from family" UX and keeps the two lists in sync by
    construction rather than by a separate sync step. `share_percentage`
    across an employee's nominees must sum to 100% per scheme — enforced in
    the view layer (apps/accounts/views_family_nomination.py), not the DB,
    same convention as everything else in this "bespoke onboarding step"
    family (see services_education_experience.py's docstring)."""
    id     = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    SCHEME_CHOICES = [
        ('epf_eps',  'EPF + EPS'),
        ('gratuity', 'Gratuity'),
        ('both',     'Both'),
    ]

    employee         = models.ForeignKey('User', on_delete=models.CASCADE, related_name='epf_nominees')
    family_member    = models.ForeignKey(FamilyMember, on_delete=models.CASCADE, related_name='nominations')
    scheme           = models.CharField(max_length=10, choices=SCHEME_CHOICES, default='epf_eps')
    share_percentage = models.PositiveSmallIntegerField(default=0)
    order            = models.PositiveSmallIntegerField(default=0)
    created_at       = models.DateTimeField(auto_now_add=True)
    updated_at       = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'hrms_epf_nominees'
        ordering = ['order', 'created_at']

    def __str__(self) -> str:
        return f'{self.employee.full_name} — nominee {self.family_member.name} ({self.share_percentage}%)'


class CompanyAsset(models.Model):
    """One row per physical asset issued to an employee — a genuine,
    unbounded add/remove list, same shape as the other bespoke-step models
    above. `returned_at` stays null while the asset is still with the
    employee; this app has no separate asset-inventory/stock model, so an
    asset row exists only in the context of the employee it's issued to."""
    id           = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    ASSET_TYPE_CHOICES = [
        ('laptop',       'Laptop'),
        ('mobile_phone', 'Mobile Phone'),
        ('monitor',      'Monitor'),
        ('headset',      'Headset'),
        ('sim_card',     'SIM Card'),
        ('access_card',  'Access Card'),
    ]
    CONDITION_CHOICES = [
        ('new',         'New'),
        ('good',        'Good'),
        ('refurbished', 'Refurbished'),
    ]

    employee    = models.ForeignKey('User', on_delete=models.CASCADE, related_name='company_assets')
    asset_type  = models.CharField(max_length=20, choices=ASSET_TYPE_CHOICES)
    tag_number  = models.CharField(max_length=100, blank=True)
    condition   = models.CharField(max_length=20, choices=CONDITION_CHOICES, default='new')
    issued_at   = models.DateField(null=True, blank=True)
    returned_at = models.DateField(null=True, blank=True)
    order       = models.PositiveSmallIntegerField(default=0)
    created_at  = models.DateTimeField(auto_now_add=True)
    updated_at  = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'hrms_company_assets'
        ordering = ['order', 'created_at']

    def __str__(self) -> str:
        return f'{self.employee.full_name} — {self.get_asset_type_display()}'


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


class OnboardingSection(models.Model):
    """
    An HR-created custom section/tab in the onboarding wizard, in addition to
    the 4 built-in steps (Personal/Education/Bank/Emergency, steps 0-3 on
    OnboardingFieldConfig) and the separate Documents step (4). Only ever
    holds custom sections — the built-ins aren't modeled here at all, so
    adding this table can't affect them.

    `step` is server-assigned (see OnboardingSectionListCreateView), always
    5 or higher, monotonically increasing and never reused, so it can never
    collide with the 5 reserved built-in step numbers (0-4). OnboardingFieldConfig
    rows for a custom section just use this `step` value like any other.
    """
    id         = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    step       = models.PositiveSmallIntegerField(unique=True)
    label      = models.CharField(max_length=100)
    icon       = models.CharField(max_length=50, default='ti-folder')
    order      = models.PositiveSmallIntegerField(default=0)
    # Deactivate rather than delete once a section still has fields under it
    # — see the view's delete-blocked-if-referenced check.
    is_active  = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'hrms_onboarding_sections'
        ordering = ['order', 'label']

    def __str__(self) -> str:
        return self.label


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

    VERIFICATION_PENDING          = 'pending'
    VERIFICATION_VERIFIED         = 'verified'
    VERIFICATION_NEEDS_CORRECTION = 'needs_correction'
    VERIFICATION_CHOICES = (
        (VERIFICATION_PENDING,          'Pending review'),
        (VERIFICATION_VERIFIED,         'Verified'),
        (VERIFICATION_NEEDS_CORRECTION, 'Needs correction'),
    )
    # HR's per-document review at onboarding approval time — separate from
    # the document simply existing (uploaded_at/_missing_required_docs
    # already cover "was something uploaded"). A document can be present but
    # illegible/wrong/expired, which is exactly what this field lets HR flag
    # before approving, with verification_note explaining what's wrong.
    verification_status = models.CharField(max_length=20, choices=VERIFICATION_CHOICES, default=VERIFICATION_PENDING)
    verification_note   = models.CharField(max_length=500, blank=True, default='')
    verified_by          = models.ForeignKey(
                                User, on_delete=models.SET_NULL, null=True, blank=True,
                                related_name='+',
                            )
    verified_at           = models.DateTimeField(null=True, blank=True)

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
    # Who approves, by relationship to the employee (replaces the old per-role approver):
    # their reporting manager, or their assigned HR partner. Blank = no approver at that level.
    APPROVER_REPORTING_MANAGER = 'reporting_manager'
    APPROVER_HR                = 'hr'
    APPROVER_CHOICES = [
        (APPROVER_REPORTING_MANAGER, 'Reporting manager'),
        (APPROVER_HR,                'HR partner'),
    ]
    l1_approver_kind = models.CharField(max_length=20, choices=APPROVER_CHOICES, blank=True, default='')
    l2_approver_kind = models.CharField(max_length=20, choices=APPROVER_CHOICES, blank=True, default='')
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
        return f'{self.get_workflow_type_display()} — L1: {self.get_l1_approver_kind_display() or "None"}'


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


# ─── Phase 5A — structured employee master data (additive) ─────────────────
# Split into separate files purely to respect this project's ~300-line
# file guideline; re-exported here so `from apps.accounts.models import X`
# keeps working for every new model, same convention as platform_core's
# own models/ package split in Phase 2.
from apps.accounts.models_org_masters import Band, Grade, JobFamily, Designation, CostCenter  # noqa: E402,F401
from apps.accounts.models_contact_address import ContactMethod, Address  # noqa: E402,F401
from apps.accounts.models_identity_bank import IdentityDocumentType, IdentityDocument, BankAccount  # noqa: E402,F401
from apps.accounts.models_family_skills import (  # noqa: E402,F401
    EmergencyContact, Nomination, SkillMaster, EmployeeSkill, EmployeeCertification,
    EmployeeLanguage, StatutoryEnrolment,
)

# ─── Phase 5B — employment lifecycle: actions, relationships (additive) ────
from apps.accounts.models_relationships import EmployeeRelationship  # noqa: E402,F401
from apps.accounts.models_actions import ActionType, EmploymentAction  # noqa: E402,F401

# ─── Phase 8B Task E/F — policy document versions/acknowledgements, asset master/allocations (additive) ───
from apps.accounts.models_policy_document_v2 import PolicyDocumentVersion, PolicyAcknowledgement  # noqa: E402,F401
from apps.accounts.models_asset_v2 import Asset, AssetAllocation  # noqa: E402,F401

# Phase 8B gap-closure — asset requests + depreciation rule table (additive).
from apps.accounts.models_asset_v2b import AssetRequest, AssetDepreciationRule  # noqa: E402,F401

# Imported last so Django registers it with the app; kept in its own module
# because models.py is already far beyond a reasonable file length.
from .models_personnel_action import PersonnelActionRequest  # noqa: E402,F401

# Edit Record panel drafts (additive) — see models_edit_draft.py.
from .models_edit_draft import EmployeeEditDraft  # noqa: E402,F401

# New-hire onboarding history (additive) — see models_onboarding_event.py.
from .models_onboarding_event import OnboardingEvent  # noqa: E402,F401

# Reusable bulk permission bundles (additive) — see models_permission_template.py.
from .models_permission_template import PermissionTemplate  # noqa: E402,F401
