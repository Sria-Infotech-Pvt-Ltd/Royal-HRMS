from __future__ import annotations

import uuid
from datetime import date, datetime, time, timedelta
from decimal import Decimal
from zoneinfo import ZoneInfo

_IST = ZoneInfo('Asia/Kolkata')

from django.conf import settings
from django.db import models

# ─── Weekly Days constants (used by model + serializers) ──────────────────────

DAYS_OF_WEEK = [
    'monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday', 'sunday',
]

DAY_TYPE_WORKING  = 'working'
DAY_TYPE_OFF      = 'off'
DAY_TYPE_HALF_DAY = 'half_day'

DAY_TYPE_CHOICES = [
    (DAY_TYPE_WORKING,  'Working Day'),
    (DAY_TYPE_OFF,      'Weekly Off'),
    (DAY_TYPE_HALF_DAY, 'Half Day'),
]


class WorkingHoursPolicy(models.Model):
    """
    Organization-level working hours configuration.

    Stores one named policy (e.g. 'Standard 9-to-6', 'Night Shift') per record.
    One policy can be flagged as the default; only one default is allowed at a time.
    Deletion is soft (is_active=False) so historical assignment records are preserved.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    # ── Identity ─────────────────────────────────────────────────────────────
    name = models.CharField(max_length=100)
    policy_code = models.CharField(
        max_length=30,
        unique=True,
        help_text='Short unique code, e.g. WH-001. Auto-generated if omitted.',
    )
    description = models.TextField(blank=True, default='')

    # ── Schedule ─────────────────────────────────────────────────────────────
    start_time = models.TimeField(help_text='Shift start time.')
    end_time = models.TimeField(
        help_text='Shift end time. May cross midnight (e.g. 22:00 → 06:00).',
    )

    # ── Duration config (in minutes) ─────────────────────────────────────────
    break_duration = models.PositiveSmallIntegerField(
        default=0,
        help_text='Total break duration in minutes (e.g. 60 for a 1-hour lunch break).',
    )
    grace_period = models.PositiveSmallIntegerField(
        default=0,
        help_text='Late-arrival grace period in minutes before a punch is marked late.',
    )

    # ── Hour limits (stored in decimal hours, e.g. 8.50 = 8 h 30 m) ─────────
    minimum_working_hours = models.DecimalField(
        max_digits=4,
        decimal_places=2,
        default=0,
        help_text='Minimum hours an employee must work to count as present.',
    )
    maximum_working_hours = models.DecimalField(
        max_digits=4,
        decimal_places=2,
        default=0,
        help_text='Maximum hours clocked before overtime rules apply.',
    )

    # ── Status ────────────────────────────────────────────────────────────────
    is_default = models.BooleanField(
        default=False,
        help_text='At most one policy may be the default. Enforced at save time.',
    )
    is_active = models.BooleanField(default=True)

    # ── Audit ─────────────────────────────────────────────────────────────────
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='created_working_hour_policies',
    )
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='updated_working_hour_policies',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'attendance_working_hours_policy'
        ordering = ['-is_default', 'name']
        indexes = [
            models.Index(fields=['is_active'],            name='whp_active_idx'),
            models.Index(fields=['is_default'],           name='whp_default_idx'),
            models.Index(fields=['is_active', 'is_default'], name='whp_active_default_idx'),
        ]

    def __str__(self) -> str:
        return f'{self.name} ({self.policy_code})'

    # ── Computed property ─────────────────────────────────────────────────────

    @property
    def standard_working_hours(self) -> float:
        """
        Net hours = (end_time − start_time) − break_duration.
        Handles overnight shifts (end_time < start_time → add 1 day).
        Returns hours rounded to 2 decimal places.
        """
        today = date.today()
        start_dt = datetime.combine(today, self.start_time)
        end_dt = datetime.combine(today, self.end_time)
        if end_dt <= start_dt:
            # Overnight shift
            end_dt += timedelta(days=1)
        total_seconds = (end_dt - start_dt).total_seconds()
        net_seconds = total_seconds - (self.break_duration * 60)
        return round(max(net_seconds, 0) / 3600, 2)


# ─── Weekly Day Policy ────────────────────────────────────────────────────────

class WeeklyDayPolicy(models.Model):
    """
    Defines the weekly schedule for an organization.

    Each day is tagged as: working, off, or half_day.
    At least one day must be 'working'.
    Only one policy can be the default at a time (enforced at serializer save).
    Deletion is soft (is_active=False).
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    # ── Identity ─────────────────────────────────────────────────────────────
    name = models.CharField(max_length=100)
    policy_code = models.CharField(
        max_length=30,
        unique=True,
        help_text='Short unique code, e.g. WD-001. Auto-generated if omitted.',
    )
    description = models.TextField(blank=True, default='')

    # ── Day schedule — one field per day ─────────────────────────────────────
    monday    = models.CharField(max_length=10, choices=DAY_TYPE_CHOICES, default=DAY_TYPE_WORKING)
    tuesday   = models.CharField(max_length=10, choices=DAY_TYPE_CHOICES, default=DAY_TYPE_WORKING)
    wednesday = models.CharField(max_length=10, choices=DAY_TYPE_CHOICES, default=DAY_TYPE_WORKING)
    thursday  = models.CharField(max_length=10, choices=DAY_TYPE_CHOICES, default=DAY_TYPE_WORKING)
    friday    = models.CharField(max_length=10, choices=DAY_TYPE_CHOICES, default=DAY_TYPE_WORKING)
    saturday  = models.CharField(max_length=10, choices=DAY_TYPE_CHOICES, default=DAY_TYPE_OFF)
    sunday    = models.CharField(max_length=10, choices=DAY_TYPE_CHOICES, default=DAY_TYPE_OFF)

    # ── Status ────────────────────────────────────────────────────────────────
    is_default = models.BooleanField(
        default=False,
        help_text='At most one policy may be the default.',
    )
    is_active = models.BooleanField(default=True)

    # ── Audit ─────────────────────────────────────────────────────────────────
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='created_weekly_day_policies',
    )
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='updated_weekly_day_policies',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'attendance_weekly_day_policy'
        ordering = ['-is_default', 'name']
        indexes = [
            models.Index(fields=['is_active'],  name='wdp_active_idx'),
            models.Index(fields=['is_default'], name='wdp_default_idx'),
        ]

    def __str__(self) -> str:
        return f'{self.name} ({self.policy_code})'

    # ── Computed properties ───────────────────────────────────────────────────

    @property
    def working_days(self) -> list[str]:
        return [d for d in DAYS_OF_WEEK if getattr(self, d) == DAY_TYPE_WORKING]

    @property
    def weekly_off_days(self) -> list[str]:
        return [d for d in DAYS_OF_WEEK if getattr(self, d) == DAY_TYPE_OFF]

    @property
    def half_day_off_days(self) -> list[str]:
        return [d for d in DAYS_OF_WEEK if getattr(self, d) == DAY_TYPE_HALF_DAY]

    @property
    def working_days_count(self) -> int:
        return len(self.working_days)


# ─── Employee Weekly Off Assignment ───────────────────────────────────────────

class EmployeeWeeklyOffAssignment(models.Model):
    """
    Assigns a WeeklyDayPolicy to a specific employee, effective from a given date.

    History is preserved, never overwritten: assigning a new pattern closes out
    the employee's previously-open row (sets its effective_to) instead of
    deleting or mutating it, so historical attendance/leave/payroll calculations
    for past dates keep resolving against whatever pattern was actually in
    effect on that date. See services_weekly_off_assignment.py for the
    create/close-out logic and core.cache_service.WeeklyOffCacheService for the
    centralized resolver every attendance/leave calculation must go through.

    effective_to = null means "currently open" (in effect until superseded).
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    employee = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='weekly_off_assignments',
    )
    policy = models.ForeignKey(
        WeeklyDayPolicy,
        on_delete=models.PROTECT,
        related_name='employee_assignments',
        help_text='PROTECT — a policy actively assigned to an employee cannot be deleted out from under them.',
    )

    effective_from = models.DateField()
    effective_to = models.DateField(
        null=True, blank=True,
        help_text='Null means this assignment is currently open (in effect until superseded).',
    )

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='created_weekly_off_assignments',
    )
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='updated_weekly_off_assignments',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'attendance_employee_weekly_off_assignment'
        ordering = ['-effective_from']
        indexes = [
            models.Index(fields=['employee', 'effective_from'], name='ewoa_emp_from_idx'),
            models.Index(fields=['employee', 'effective_to'],   name='ewoa_emp_to_idx'),
        ]

    def __str__(self) -> str:
        return f'{self.employee_id} → {self.policy.policy_code} from {self.effective_from}'

    def covers(self, for_date) -> bool:
        return self.effective_from <= for_date and (self.effective_to is None or self.effective_to >= for_date)


# ─── Punch Rules Policy ───────────────────────────────────────────────────────

class PunchRulesPolicy(models.Model):
    """
    Configures how employee punches are validated and processed.

    punch_mode = 'single'   → employee punches IN once; auto-checkout handles the OUT.
    punch_mode = 'multiple' → employee can punch IN/OUT multiple times (e.g. for breaks);
                              max_punch_count caps the total number of punch events per day.

    When auto_checkout_enabled is True, auto_checkout_time must be supplied.
    Only one policy can be the default at a time.
    """

    PUNCH_MODE_SINGLE   = 'single'
    PUNCH_MODE_MULTIPLE = 'multiple'
    PUNCH_MODE_CHOICES  = [
        (PUNCH_MODE_SINGLE,   'Single Punch'),
        (PUNCH_MODE_MULTIPLE, 'Multiple Punch'),
    ]

    MISSING_PUNCH_ABSENT        = 'mark_absent'
    MISSING_PUNCH_HALF_DAY      = 'mark_half_day'
    MISSING_PUNCH_REGULARIZE    = 'require_regularization'
    MISSING_PUNCH_AUTO          = 'auto_regularize'
    MISSING_PUNCH_CHOICES       = [
        (MISSING_PUNCH_ABSENT,      'Mark as Absent'),
        (MISSING_PUNCH_HALF_DAY,    'Mark as Half Day'),
        (MISSING_PUNCH_REGULARIZE,  'Require Regularization'),
        (MISSING_PUNCH_AUTO,        'Auto Regularize'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    # ── Identity ─────────────────────────────────────────────────────────────
    name        = models.CharField(max_length=100)
    policy_code = models.CharField(
        max_length=30,
        unique=True,
        help_text='Short unique code, e.g. PR-001. Auto-generated if omitted.',
    )
    description = models.TextField(blank=True, default='')

    # ── Punch mode ────────────────────────────────────────────────────────────
    punch_mode = models.CharField(
        max_length=10,
        choices=PUNCH_MODE_CHOICES,
        default=PUNCH_MODE_MULTIPLE,
        help_text='Single: one punch-in required, auto-checkout handles out. '
                  'Multiple: unlimited in/out pairs up to max_punch_count.',
    )

    # ── Punch count cap ───────────────────────────────────────────────────────
    max_punch_count = models.PositiveSmallIntegerField(
        default=2,
        help_text='Maximum punch events per day (each IN or OUT counts as one). '
                  'Forced to 1 when punch_mode is "single". Min 2 for "multiple".',
    )

    # ── Auto checkout ─────────────────────────────────────────────────────────
    auto_checkout_enabled = models.BooleanField(
        default=False,
        help_text='When True, the system automatically punches out the employee '
                  'at auto_checkout_time if they have not already punched out.',
    )
    auto_checkout_time = models.TimeField(
        null=True,
        blank=True,
        help_text='Required when auto_checkout_enabled is True.',
    )

    # ── Early checkout grace ──────────────────────────────────────────────────
    early_checkout_grace = models.PositiveSmallIntegerField(
        default=0,
        help_text='Minutes before scheduled shift end that an employee can '
                  'punch out without the departure being flagged as early checkout.',
    )

    # ── Missing punch handling ────────────────────────────────────────────────
    missing_punch_action = models.CharField(
        max_length=25,
        choices=MISSING_PUNCH_CHOICES,
        default=MISSING_PUNCH_REGULARIZE,
        help_text='Action taken when an employee has an IN punch but no OUT punch (or vice versa).',
    )

    # ── Status ────────────────────────────────────────────────────────────────
    is_default = models.BooleanField(default=False)
    is_active  = models.BooleanField(default=True)

    # ── Audit ─────────────────────────────────────────────────────────────────
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='created_punch_rules_policies',
    )
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='updated_punch_rules_policies',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'attendance_punch_rules_policy'
        ordering = ['-is_default', 'name']
        indexes = [
            models.Index(fields=['is_active'],  name='prp_active_idx'),
            models.Index(fields=['is_default'], name='prp_default_idx'),
        ]

    def __str__(self) -> str:
        return f'{self.name} ({self.policy_code})'


# ─── Overtime Policy ──────────────────────────────────────────────────────────

class OvertimePolicy(models.Model):
    """
    Configures how overtime is calculated, capped, rounded, and approved.

    Thresholds are stored in minutes for precision.
    Multipliers apply to holiday and weekly-off overtime (e.g. 2.0 = double pay).
    0 for daily/monthly caps means no cap is enforced.
    """

    ROUND_OFF_NONE   = 'none'
    ROUND_OFF_15_MIN = '15_min'
    ROUND_OFF_30_MIN = '30_min'
    ROUND_OFF_60_MIN = '60_min'
    ROUND_OFF_CHOICES = [
        (ROUND_OFF_NONE,   'No Rounding'),
        (ROUND_OFF_15_MIN, 'Round to nearest 15 minutes'),
        (ROUND_OFF_30_MIN, 'Round to nearest 30 minutes'),
        (ROUND_OFF_60_MIN, 'Round to nearest 60 minutes'),
    ]

    APPROVAL_NOT_REQUIRED = 'none'
    APPROVAL_AUTO         = 'auto'
    APPROVAL_MANUAL       = 'manual'
    APPROVAL_CHOICES = [
        (APPROVAL_NOT_REQUIRED, 'Not Required'),
        (APPROVAL_AUTO,         'Auto Approve'),
        (APPROVAL_MANUAL,       'Requires Approval'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    # ── Identity ─────────────────────────────────────────────────────────────
    name        = models.CharField(max_length=100)
    policy_code = models.CharField(
        max_length=30,
        unique=True,
        help_text='Short unique code, e.g. OT-001. Auto-generated if omitted.',
    )
    description = models.TextField(blank=True, default='')

    # ── OT thresholds ─────────────────────────────────────────────────────────
    minimum_overtime_minutes = models.PositiveSmallIntegerField(
        default=30,
        help_text='Minutes beyond shift end before overtime counting begins. '
                  'Work within this buffer is not treated as overtime.',
    )
    maximum_overtime_minutes_per_day = models.PositiveSmallIntegerField(
        default=0,
        help_text='Daily overtime cap in minutes. 0 = no cap.',
    )
    maximum_overtime_minutes_per_month = models.PositiveIntegerField(
        default=0,
        help_text='Monthly overtime cap in minutes. 0 = no cap.',
    )

    # ── Rounding ──────────────────────────────────────────────────────────────
    round_off_rule = models.CharField(
        max_length=10,
        choices=ROUND_OFF_CHOICES,
        default=ROUND_OFF_NONE,
        help_text='How calculated overtime minutes are rounded before recording.',
    )

    # ── Approval ──────────────────────────────────────────────────────────────
    approval_type = models.CharField(
        max_length=10,
        choices=APPROVAL_CHOICES,
        default=APPROVAL_MANUAL,
        help_text='Whether overtime requires explicit manager/HR approval.',
    )

    # ── Holiday overtime ──────────────────────────────────────────────────────
    count_holiday_overtime = models.BooleanField(
        default=True,
        help_text='Track and compensate overtime worked on declared holidays.',
    )
    holiday_overtime_multiplier = models.DecimalField(
        max_digits=3,
        decimal_places=1,
        default='2.0',
        help_text='Pay multiplier for holiday overtime (e.g. 2.0 = double pay). Min 1.0.',
    )

    # ── Weekly off overtime ───────────────────────────────────────────────────
    count_weekly_off_overtime = models.BooleanField(
        default=True,
        help_text='Track and compensate overtime worked on weekly off days.',
    )
    weekly_off_overtime_multiplier = models.DecimalField(
        max_digits=3,
        decimal_places=1,
        default='2.0',
        help_text='Pay multiplier for weekly-off overtime (e.g. 1.5 = time and a half). Min 1.0.',
    )

    # ── Status ────────────────────────────────────────────────────────────────
    is_default = models.BooleanField(default=False)
    is_active  = models.BooleanField(default=True)

    # ── Audit ─────────────────────────────────────────────────────────────────
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='created_overtime_policies',
    )
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='updated_overtime_policies',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'attendance_overtime_policy'
        ordering = ['-is_default', 'name']
        indexes = [
            models.Index(fields=['is_active'],  name='otp_active_idx'),
            models.Index(fields=['is_default'], name='otp_default_idx'),
        ]

    def __str__(self) -> str:
        return f'{self.name} ({self.policy_code})'


# ─── Late Mark & LOP Policy ───────────────────────────────────────────────────

class LateMarkLOPPolicy(models.Model):
    """
    Defines when accumulated late marks trigger a Loss-of-Pay (LOP) deduction.

    late_marks_per_lop = 0  → Late marks are tracked but never convert to LOP
                              (tracking-only mode).
    late_marks_per_lop > 0  → Every N consecutive late marks within a calendar
                              month result in one LOP deduction of lop_deduction_unit.
                              The counter resets on the 1st of each month.

    Only one policy can be the default at a time.
    Deletion is soft (is_active=False).
    """

    LOP_UNIT_FULL_DAY = 'full_day'
    LOP_UNIT_HALF_DAY = 'half_day'
    LOP_UNIT_CHOICES = [
        (LOP_UNIT_FULL_DAY, 'Full Day'),
        (LOP_UNIT_HALF_DAY, 'Half Day'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    # ── Identity ─────────────────────────────────────────────────────────────
    name = models.CharField(max_length=100)
    policy_code = models.CharField(
        max_length=30,
        unique=True,
        help_text='Short unique code, e.g. LM-001. Auto-generated if omitted.',
    )
    description = models.TextField(blank=True, default='')

    # ── Late mark threshold ───────────────────────────────────────────────────
    late_marks_per_lop = models.PositiveSmallIntegerField(
        default=3,
        help_text=(
            'Number of late marks within a calendar month that trigger one LOP deduction. '
            '0 = tracking only (late marks recorded but no LOP is applied).'
        ),
    )

    # ── LOP deduction size ────────────────────────────────────────────────────
    lop_deduction_unit = models.CharField(
        max_length=10,
        choices=LOP_UNIT_CHOICES,
        default=LOP_UNIT_FULL_DAY,
        help_text='Whether each LOP deduction counts as a full day or a half day.',
    )

    # ── Status ────────────────────────────────────────────────────────────────
    is_default = models.BooleanField(
        default=False,
        help_text='At most one policy may be the default.',
    )
    is_active = models.BooleanField(default=True)

    # ── Audit ─────────────────────────────────────────────────────────────────
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='created_late_mark_lop_policies',
    )
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='updated_late_mark_lop_policies',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'attendance_late_mark_lop_policy'
        ordering = ['-is_default', 'name']
        indexes = [
            models.Index(fields=['is_active'],  name='lml_active_idx'),
            models.Index(fields=['is_default'], name='lml_default_idx'),
        ]

    def __str__(self) -> str:
        return f'{self.name} ({self.policy_code})'

    @property
    def is_lop_enabled(self) -> bool:
        """True when late marks actually trigger LOP deductions (not tracking-only)."""
        return self.late_marks_per_lop > 0


# ─── Absence Alert Policy ─────────────────────────────────────────────────────

class AbsenceAlertPolicy(models.Model):
    """
    Triggers a notification when an employee is absent for N+ consecutive
    working days without an approved leave request.

    is_enabled = False → alerts are configured but suppressed (e.g. during a
                         holiday season when expected absence is high).
    absent_days_threshold → the minimum run of consecutive unexplained absent
                            days before the alert fires.
    notification_recipients → who receives the alert email/notification.

    Only one policy can be the default at a time.
    Deletion is soft (is_active=False).
    """

    NOTIFY_MANAGER_AND_HR = 'manager_and_hr'
    NOTIFY_HR_ONLY        = 'hr_only'
    NOTIFY_MANAGER_ONLY   = 'manager_only'
    NOTIFY_CHOICES = [
        (NOTIFY_MANAGER_AND_HR, 'Manager + HR'),
        (NOTIFY_HR_ONLY,        'HR Only'),
        (NOTIFY_MANAGER_ONLY,   'Manager Only'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    # ── Identity ─────────────────────────────────────────────────────────────
    name = models.CharField(max_length=100)
    policy_code = models.CharField(
        max_length=30,
        unique=True,
        help_text='Short unique code, e.g. AA-001. Auto-generated if omitted.',
    )
    description = models.TextField(blank=True, default='')

    # ── Alert config ──────────────────────────────────────────────────────────
    is_enabled = models.BooleanField(
        default=True,
        help_text='When False, absence alerts are suppressed for this policy.',
    )
    absent_days_threshold = models.PositiveSmallIntegerField(
        default=3,
        help_text=(
            'Number of consecutive unexplained absent working days before '
            'an alert is triggered. Must be at least 1.'
        ),
    )
    notification_recipients = models.CharField(
        max_length=15,
        choices=NOTIFY_CHOICES,
        default=NOTIFY_MANAGER_AND_HR,
        help_text='Who receives the absence alert notification.',
    )

    # ── Status ────────────────────────────────────────────────────────────────
    is_default = models.BooleanField(
        default=False,
        help_text='At most one policy may be the default.',
    )
    is_active = models.BooleanField(default=True)

    # ── Audit ─────────────────────────────────────────────────────────────────
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='created_absence_alert_policies',
    )
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='updated_absence_alert_policies',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'attendance_absence_alert_policy'
        ordering = ['-is_default', 'name']
        indexes = [
            models.Index(fields=['is_active'],  name='aap_active_idx'),
            models.Index(fields=['is_default'], name='aap_default_idx'),
        ]

    def __str__(self) -> str:
        return f'{self.name} ({self.policy_code})'


# ══════════════════════════════════════════════════════════════════════════════
#  Unified Attendance Settings  (one record per organisation)
#
#  The "Save Attendance Rules" page writes ALL six sections in a single request
#  wrapped in transaction.atomic().  Each section lives in its own table for
#  normalisation; they all hang off AttendanceSettings via OneToOne.
# ══════════════════════════════════════════════════════════════════════════════

class AttendanceSettings(models.Model):
    """
    Top-level configuration record — one active record per organisation.
    Child models link back here via OneToOneField.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    is_active  = models.BooleanField(default=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL, null=True, blank=True,
        related_name='created_attendance_settings',
    )
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL, null=True, blank=True,
        related_name='updated_attendance_settings',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'attendance_settings'

    def __str__(self) -> str:
        return f'AttendanceSettings ({self.pk})'


class AttendanceWorkingHours(models.Model):
    """Shift timing, grace period, break deduction for the organisation."""

    settings = models.OneToOneField(
        AttendanceSettings,
        on_delete=models.CASCADE,
        related_name='working_hours',
    )
    shift_start            = models.TimeField(default=time(9, 0))
    shift_end              = models.TimeField(default=time(18, 0))
    grace_period_minutes   = models.PositiveSmallIntegerField(
        default=15,
        help_text='Minutes of late-arrival tolerance before punch is flagged late.',
    )
    missing_punch_grace_minutes = models.PositiveSmallIntegerField(
        default=10,
        help_text=(
            'Minutes after shift end before a missing clock-out triggers an un-punch alert. '
            'Employee is marked Incomplete and notified after shift_end + this value.'
        ),
    )
    break_duration_minutes = models.PositiveSmallIntegerField(
        default=30,
        help_text='Break deduction in minutes. 0 = no deduction.',
    )

    class Meta:
        db_table = 'attendance_settings_working_hours'

    def __str__(self) -> str:
        return f'WorkingHours for {self.settings_id}'


class AttendanceWeeklyOff(models.Model):
    """Weekly off-day configuration. True = day is a weekly off (non-working)."""

    settings   = models.OneToOneField(
        AttendanceSettings,
        on_delete=models.CASCADE,
        related_name='weekly_off',
    )
    monday     = models.BooleanField(default=False)
    tuesday    = models.BooleanField(default=False)
    wednesday  = models.BooleanField(default=False)
    thursday   = models.BooleanField(default=False)
    friday     = models.BooleanField(default=False)
    saturday   = models.BooleanField(default=True)
    sunday     = models.BooleanField(default=True)

    class Meta:
        db_table = 'attendance_settings_weekly_off'

    def __str__(self) -> str:
        return f'WeeklyOff for {self.settings_id}'

    @property
    def off_days(self) -> list[str]:
        days = ['monday','tuesday','wednesday','thursday','friday','saturday','sunday']
        return [d for d in days if getattr(self, d)]

    @property
    def working_days_count(self) -> int:
        return 7 - len(self.off_days)


class AttendancePunchRules(models.Model):
    """Minimum hours required for full-day / half-day presence, plus early-exit grace."""

    settings = models.OneToOneField(
        AttendanceSettings,
        on_delete=models.CASCADE,
        related_name='punch_rules',
    )
    min_hours_full_day        = models.DecimalField(
        max_digits=4, decimal_places=2, default=Decimal('8.00'),
        help_text='Minimum clocked hours to count as a full present day.',
    )
    min_hours_half_day        = models.DecimalField(
        max_digits=4, decimal_places=2, default=Decimal('4.00'),
        help_text='Minimum clocked hours to count as a half-day present.',
    )
    early_exit_grace_minutes  = models.PositiveSmallIntegerField(
        default=30,
        help_text='Minutes before shift end that an early departure is forgiven.',
    )

    class Meta:
        db_table = 'attendance_settings_punch_rules'

    def __str__(self) -> str:
        return f'PunchRules for {self.settings_id}'


class AttendanceOvertimeRules(models.Model):
    """Overtime eligibility threshold and pay multipliers."""

    settings = models.OneToOneField(
        AttendanceSettings,
        on_delete=models.CASCADE,
        related_name='overtime_rules',
    )
    ot_threshold_hours      = models.DecimalField(
        max_digits=4, decimal_places=2, default=Decimal('9.00'),
        help_text='Total hours worked in a day before overtime begins.',
    )
    ot_multiplier_regular   = models.DecimalField(
        max_digits=3, decimal_places=2, default=Decimal('1.50'),
        help_text='Pay multiplier for regular weekday overtime (e.g. 1.5 = time-and-a-half).',
    )
    ot_multiplier_holiday   = models.DecimalField(
        max_digits=3, decimal_places=2, default=Decimal('2.00'),
        help_text='Pay multiplier for overtime worked on declared holidays.',
    )

    class Meta:
        db_table = 'attendance_settings_overtime_rules'

    def __str__(self) -> str:
        return f'OvertimeRules for {self.settings_id}'


class AttendanceLateMarkRules(models.Model):
    """How accumulated late marks convert to Loss-of-Pay (LOP) deductions."""

    LOP_UNIT_FULL_DAY = 'full_day'
    LOP_UNIT_HALF_DAY = 'half_day'
    LOP_UNIT_CHOICES  = [
        (LOP_UNIT_FULL_DAY, 'Full Day'),
        (LOP_UNIT_HALF_DAY, 'Half Day (0.5 day)'),
    ]

    settings           = models.OneToOneField(
        AttendanceSettings,
        on_delete=models.CASCADE,
        related_name='late_mark_rules',
    )
    late_marks_per_lop = models.PositiveSmallIntegerField(
        default=3,
        help_text=(
            'Number of late marks in a calendar month that trigger one LOP deduction. '
            '0 = tracking only — late marks recorded but no LOP applied.'
        ),
    )
    lop_deduction_unit = models.CharField(
        max_length=10,
        choices=LOP_UNIT_CHOICES,
        default=LOP_UNIT_FULL_DAY,
    )

    class Meta:
        db_table = 'attendance_settings_late_mark_rules'

    def __str__(self) -> str:
        return f'LateMarkRules for {self.settings_id}'


class AttendanceAbsenceAlert(models.Model):
    """Alert HR/manager when an employee is absent N+ consecutive days without leave."""

    NOTIFY_MANAGER_AND_HR = 'manager_and_hr'
    NOTIFY_HR_ONLY        = 'hr_only'
    NOTIFY_MANAGER_ONLY   = 'manager_only'
    NOTIFY_CHOICES        = [
        (NOTIFY_MANAGER_AND_HR, 'Manager + HR'),
        (NOTIFY_HR_ONLY,        'HR Only'),
        (NOTIFY_MANAGER_ONLY,   'Manager Only'),
    ]

    settings          = models.OneToOneField(
        AttendanceSettings,
        on_delete=models.CASCADE,
        related_name='absence_alert',
    )
    is_enabled        = models.BooleanField(default=True)
    alert_after_days  = models.PositiveSmallIntegerField(
        default=3,
        help_text='Consecutive absent working days (without approved leave) that trigger the alert.',
    )
    notify_whom       = models.CharField(
        max_length=15,
        choices=NOTIFY_CHOICES,
        default=NOTIFY_MANAGER_AND_HR,
    )

    class Meta:
        db_table = 'attendance_settings_absence_alert'

    def __str__(self) -> str:
        return f'AbsenceAlert for {self.settings_id}'


class AttendanceFaceVerificationRules(models.Model):
    """
    Org-wide face ID verification toggle (Attendance Settings -> Face ID
    Verification card).

    is_mandatory is the single source of truth for the whole feature, not
    just a stricter mode of it:
      - True  — every employee must register a face ID (see
        FaceRegistrationRequest) and every web-sourced clock-in/out requires
        a live face match against their approved registration before the
        punch is accepted (FaceVerificationService.verify_for_punch).
      - False — the feature is switched off organisation-wide: employees
        cannot submit new registrations (they're shown a "contact admin"
        message instead) and punches never require a face match, even for
        someone who registered while this was previously True.
    """

    settings     = models.OneToOneField(
        AttendanceSettings,
        on_delete=models.CASCADE,
        related_name='face_verification',
    )
    is_mandatory = models.BooleanField(
        default=False,
        help_text='When on, face ID registration is mandatory for every employee and is enforced at web clock-in/out.',
    )

    class Meta:
        db_table = 'attendance_settings_face_verification'

    def __str__(self) -> str:
        return f'FaceVerificationRules for {self.settings_id}'


# ══════════════════════════════════════════════════════════════════════════════
#  Attendance Transactions — Punch, Record, Correction
#
#  Punches are immutable raw events.  The processor converts them into one
#  AttendanceRecord per employee per day.  The dashboard reads only records.
# ══════════════════════════════════════════════════════════════════════════════

class AttendancePunch(models.Model):
    """
    Immutable raw punch event — every IN/OUT stored independently, never overwritten.

    Stores complete audit information: GPS coordinates, device info, IP address,
    geofence validation result, and attendance mode.  Every field is preserved
    permanently for compliance and fraud detection.

    source = 'web'       → clocked through the browser dashboard
    source = 'mobile'    → clocked through the mobile app
    source = 'biometric' → hardware biometric device push
    source = 'manual'    → HR/admin created manually
    source = 'system'    → auto-checkout by the attendance processor
    source = 'voice'     → clocked through a voice command. Still issued from
                            the same browser tab as 'web' though, so it DOES
                            have camera access — the voice-initiated clock-in
                            conversation (apps.voice_commands.
                            conversation_clock_in_face) opens it for a
                            "taking facial proof" step when face verification
                            is mandatory, same as the manual ClockWidget does.
                            Only 'mobile'/'biometric'/'manual'/'system' are
                            genuinely camera-less and stay exempt below.

    attendance_mode = 'office'          → validated against branch geofence
    attendance_mode = 'wfh'             → work from home, no geofence check
    attendance_mode = 'field'           → field work, location recorded only
    attendance_mode = 'client_location' → at client site, location recorded only
    attendance_mode = 'remote_office'   → remote co-working space
    """

    PUNCH_IN  = 'IN'
    PUNCH_OUT = 'OUT'
    PUNCH_TYPE_CHOICES = [
        (PUNCH_IN,  'Punch In'),
        (PUNCH_OUT, 'Punch Out'),
    ]

    SOURCE_WEB       = 'web'
    SOURCE_MOBILE    = 'mobile'
    SOURCE_BIOMETRIC = 'biometric'
    SOURCE_MANUAL    = 'manual'
    SOURCE_SYSTEM    = 'system'
    SOURCE_VOICE     = 'voice'
    SOURCE_CHOICES   = [
        (SOURCE_WEB,       'Web'),
        (SOURCE_MOBILE,    'Mobile'),
        (SOURCE_BIOMETRIC, 'Biometric'),
        (SOURCE_MANUAL,    'Manual'),
        (SOURCE_SYSTEM,    'System'),
        (SOURCE_VOICE,     'Voice Command'),
    ]

    MODE_OFFICE          = 'office'
    MODE_WFH             = 'wfh'
    MODE_FIELD           = 'field'
    MODE_CLIENT_LOCATION = 'client_location'
    MODE_REMOTE_OFFICE   = 'remote_office'
    ATTENDANCE_MODE_CHOICES = [
        (MODE_OFFICE,          'Office'),
        (MODE_WFH,             'Work From Home'),
        (MODE_FIELD,           'Field Work'),
        (MODE_CLIENT_LOCATION, 'Client Location'),
        (MODE_REMOTE_OFFICE,   'Remote Office'),
    ]

    # ── Identity ──────────────────────────────────────────────────────────────
    id             = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    employee       = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='attendance_punches',
    )
    branch         = models.ForeignKey(
        'branch.Branch',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='attendance_punches',
        help_text='Resolved branch at the time of punch.',
    )

    # ── Punch core ────────────────────────────────────────────────────────────
    punch_type      = models.CharField(max_length=3, choices=PUNCH_TYPE_CHOICES)
    punched_at      = models.DateTimeField(help_text='Server timestamp of the punch event.')
    device_time     = models.DateTimeField(
        null=True, blank=True,
        help_text='Timestamp reported by the client device (may differ from server time).',
    )
    source          = models.CharField(max_length=10, choices=SOURCE_CHOICES, default=SOURCE_WEB)
    attendance_mode = models.CharField(
        max_length=16, choices=ATTENDANCE_MODE_CHOICES, default=MODE_OFFICE,
    )
    is_regularized  = models.BooleanField(
        default=False,
        help_text='True when added via an approved attendance correction.',
    )

    # ── GPS & Geofence ────────────────────────────────────────────────────────
    latitude            = models.DecimalField(
        max_digits=12, decimal_places=8, null=True, blank=True,
        help_text='Employee GPS latitude at punch time.',
    )
    longitude           = models.DecimalField(
        max_digits=12, decimal_places=8, null=True, blank=True,
        help_text='Employee GPS longitude at punch time.',
    )
    accuracy            = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True,
        help_text='GPS accuracy reported by the device in metres.',
    )
    calculated_distance = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True,
        help_text='Haversine distance in metres between employee and branch coordinates.',
    )
    is_inside_geofence  = models.BooleanField(
        null=True,
        help_text=(
            'True = inside allowed radius. '
            'False = outside. '
            'None = geofence not evaluated (branch has no coordinates or WFH mode).'
        ),
    )

    # ── Device & Network audit ────────────────────────────────────────────────
    ip_address       = models.GenericIPAddressField(null=True, blank=True)
    browser          = models.CharField(max_length=500, blank=True, default='')
    operating_system = models.CharField(max_length=200, blank=True, default='')
    device_name      = models.CharField(max_length=200, blank=True, default='')
    device_id        = models.CharField(
        max_length=255, blank=True, default='',
        help_text='Persistent device fingerprint or browser fingerprint ID.',
    )

    # ── Face verification ─────────────────────────────────────────────────────
    face_verified       = models.BooleanField(
        default=False,
        help_text='True only when the employee has an approved face registration '
                   'and their submitted face matched it at punch time.',
    )
    face_match_distance = models.FloatField(
        null=True, blank=True,
        help_text='Euclidean distance between submitted and registered face '
                   'descriptors. Null when face verification did not apply.',
    )

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'attendance_punches'
        ordering = ['punched_at']
        indexes = [
            models.Index(fields=['employee', 'punched_at'],       name='punch_emp_time_idx'),
            models.Index(fields=['employee', 'punch_type'],       name='punch_emp_type_idx'),
            models.Index(fields=['employee', 'is_inside_geofence'], name='punch_emp_geofence_idx'),
            models.Index(fields=['branch', 'punched_at'],         name='punch_branch_time_idx'),
        ]

    def __str__(self) -> str:
        return f'{self.employee_id} {self.punch_type} @ {self.punched_at}'

    @property
    def punch_date(self) -> date:
        return self.punched_at.astimezone(_IST).date()

    @property
    def punch_time_display(self) -> str:
        return self.punched_at.astimezone(_IST).strftime('%H:%M')


class AttendanceRecord(models.Model):
    """
    Processed daily attendance result for one employee — one row per (employee, date).

    Populated and updated by AttendanceProcessorService after every punch.
    The dashboard reads only this table — never raw punches.
    """

    STATUS_PRESENT    = 'present'
    STATUS_LATE       = 'late'
    STATUS_ABSENT     = 'absent'
    STATUS_HALF_DAY   = 'half_day'
    STATUS_WEEKLY_OFF = 'weekly_off'
    STATUS_HOLIDAY    = 'holiday'
    STATUS_ON_LEAVE   = 'on_leave'
    STATUS_INCOMPLETE = 'incomplete'   # clocked in, shift ended, no clock-out yet
    STATUS_CHOICES    = [
        (STATUS_PRESENT,    'Present'),
        (STATUS_LATE,       'Late'),
        (STATUS_ABSENT,     'Absent'),
        (STATUS_HALF_DAY,   'Half Day'),
        (STATUS_WEEKLY_OFF, 'Weekly Off'),
        (STATUS_HOLIDAY,    'Holiday'),
        (STATUS_ON_LEAVE,   'On Leave'),
        (STATUS_INCOMPLETE, 'Incomplete'),
    ]

    # Frontend display labels (must match DayStatus in CalendarGrid.tsx)
    STATUS_DISPLAY_MAP = {
        STATUS_PRESENT:    'Present',
        STATUS_LATE:       'Late',
        STATUS_ABSENT:     'Absent',
        STATUS_HALF_DAY:   'Half Day',
        STATUS_WEEKLY_OFF: 'Weekly Off',
        STATUS_HOLIDAY:    'Holiday',
        STATUS_ON_LEAVE:   'On Leave',
        STATUS_INCOMPLETE: 'Incomplete',
    }

    id                     = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    employee               = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='attendance_records',
    )
    date                   = models.DateField()
    status                 = models.CharField(max_length=12, choices=STATUS_CHOICES)
    first_punch_in         = models.TimeField(null=True, blank=True)
    last_punch_out         = models.TimeField(null=True, blank=True)
    total_working_minutes  = models.PositiveIntegerField(
        default=0,
        help_text='Net working time in minutes after break deduction.',
    )
    overtime_minutes       = models.PositiveIntegerField(default=0)
    is_late                = models.BooleanField(default=False)
    is_early_exit          = models.BooleanField(default=False)
    note                   = models.CharField(max_length=200, blank=True, default='')
    created_at             = models.DateTimeField(auto_now_add=True)
    updated_at             = models.DateTimeField(auto_now=True)

    class Meta:
        db_table        = 'attendance_records'
        unique_together = [('employee', 'date')]
        indexes         = [
            models.Index(fields=['employee', 'date'],   name='rec_emp_date_idx'),
            models.Index(fields=['employee', 'status'], name='rec_emp_status_idx'),
            models.Index(fields=['date'],               name='rec_date_idx'),
            models.Index(fields=['date', 'status'],     name='rec_date_status_idx'),
        ]

    def __str__(self) -> str:
        return f'{self.employee_id} — {self.date} — {self.status}'

    @property
    def status_display(self) -> str:
        return self.STATUS_DISPLAY_MAP.get(self.status, self.status)

    @property
    def total_hours_display(self) -> str:
        """Returns '9h 07m' format expected by the frontend."""
        if not self.total_working_minutes:
            return '—'
        h = self.total_working_minutes // 60
        m = self.total_working_minutes % 60
        return f'{h}h {m:02d}m'

    @property
    def clock_in_display(self) -> str | None:
        """Returns 'HH:MM' string or None."""
        return self.first_punch_in.strftime('%H:%M') if self.first_punch_in else None

    @property
    def clock_out_display(self) -> str | None:
        return self.last_punch_out.strftime('%H:%M') if self.last_punch_out else None


class AttendanceCorrection(models.Model):
    """
    Employee-submitted regularization request for a missed or incorrect punch.

    Workflow: submitted → pending → approved/rejected by manager or HR.
    An approved correction creates a regularized AttendancePunch and triggers
    reprocessing of the attendance record for that date.
    """

    PUNCH_IN   = 'IN'
    PUNCH_OUT  = 'OUT'
    PUNCH_BOTH = 'BOTH'
    PUNCH_TYPE_CHOICES = [
        (PUNCH_IN,   'Clock In (IN)'),
        (PUNCH_OUT,  'Clock Out (OUT)'),
        (PUNCH_BOTH, 'Both IN & OUT'),
    ]

    REASON_BIOMETRIC  = 'biometric_error'
    REASON_FORGOT     = 'forgot_to_punch'
    REASON_FIELD_WORK = 'field_work'
    REASON_SYSTEM     = 'system_downtime'
    REASON_OTHER      = 'other'
    REASON_CHOICES    = [
        (REASON_BIOMETRIC,  'Device malfunction / biometric error'),
        (REASON_FORGOT,     'Forgot to punch'),
        (REASON_FIELD_WORK, 'Work from field (client visit)'),
        (REASON_SYSTEM,     'System / server downtime'),
        (REASON_OTHER,      'Other'),
    ]

    STATUS_PENDING    = 'pending'
    STATUS_L2_PENDING = 'l2_pending'
    STATUS_APPROVED   = 'approved'
    STATUS_REJECTED   = 'rejected'
    STATUS_CHOICES  = [
        (STATUS_PENDING,    'Pending'),
        (STATUS_L2_PENDING, 'L2 Pending'),
        (STATUS_APPROVED,   'Approved'),
        (STATUS_REJECTED,   'Rejected'),
    ]

    STAGE_APPROVED = 'approved'
    STAGE_REJECTED = 'rejected'
    STAGE_STATUS_CHOICES = [
        (STAGE_APPROVED, 'Approved'),
        (STAGE_REJECTED, 'Rejected'),
    ]

    id                  = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    employee            = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='attendance_corrections',
    )
    date                = models.DateField()
    punch_type          = models.CharField(max_length=4, choices=PUNCH_TYPE_CHOICES)
    requested_in_time   = models.TimeField(
        null=True, blank=True,
        help_text='Correct punch-in time. Required when punch_type is IN or BOTH.',
    )
    requested_out_time  = models.TimeField(
        null=True, blank=True,
        help_text='Correct punch-out time. Required when punch_type is OUT or BOTH.',
    )
    reason              = models.CharField(max_length=20, choices=REASON_CHOICES)
    notes               = models.TextField(blank=True, default='')
    status              = models.CharField(
        max_length=10, choices=STATUS_CHOICES, default=STATUS_PENDING,
    )
    reviewed_by         = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='reviewed_corrections',
    )
    reviewed_at         = models.DateTimeField(null=True, blank=True)

    # L1 approval (manager)
    l1_approver    = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='l1_attendance_corrections',
    )
    l1_status      = models.CharField(max_length=10, choices=STAGE_STATUS_CHOICES, null=True, blank=True)
    l1_remarks     = models.TextField(blank=True, default='')
    l1_actioned_at = models.DateTimeField(null=True, blank=True)

    # L2 approval (HR)
    l2_approver    = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='l2_attendance_corrections',
    )
    l2_status      = models.CharField(max_length=10, choices=STAGE_STATUS_CHOICES, null=True, blank=True)
    l2_remarks     = models.TextField(blank=True, default='')
    l2_actioned_at = models.DateTimeField(null=True, blank=True)

    created_by          = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='created_corrections',
    )
    created_at          = models.DateTimeField(auto_now_add=True)
    updated_at          = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'attendance_corrections'
        indexes  = [
            models.Index(fields=['employee', 'date'],   name='corr_emp_date_idx'),
            models.Index(fields=['employee', 'status'], name='corr_emp_status_idx'),
            # Phase 4: global HR/admin dashboard action-queue counters filter
            # by status alone (no employee) — neither existing composite
            # (both employee-leading) can serve that without an employee bound.
            models.Index(fields=['status'], name='corr_status_idx'),
        ]

    def __str__(self) -> str:
        return f'Correction: {self.employee_id} — {self.date} ({self.status})'


# ══════════════════════════════════════════════════════════════════════════════
#  Overtime Entry  (HR-managed OT records)
# ══════════════════════════════════════════════════════════════════════════════

class AttendanceOvertime(models.Model):
    OT_TYPE_REGULAR    = 'regular'
    OT_TYPE_HOLIDAY    = 'holiday'
    OT_TYPE_WEEKLY_OFF = 'weekly_off'
    OT_TYPE_CHOICES    = [
        (OT_TYPE_REGULAR,    'Regular (1.5×)'),
        (OT_TYPE_HOLIDAY,    'Holiday (2.0×)'),
        (OT_TYPE_WEEKLY_OFF, 'Weekly Off (1.5×)'),
    ]

    STATUS_PENDING  = 'pending'
    STATUS_APPROVED = 'approved'
    STATUS_REJECTED = 'rejected'
    STATUS_CHOICES  = [
        (STATUS_PENDING,  'Pending'),
        (STATUS_APPROVED, 'Approved'),
        (STATUS_REJECTED, 'Rejected'),
    ]

    id          = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    employee    = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name='overtime_entries',
    )
    date        = models.DateField()
    ot_start    = models.TimeField()
    ot_end      = models.TimeField()
    ot_minutes  = models.PositiveIntegerField(default=0)
    ot_type     = models.CharField(max_length=15, choices=OT_TYPE_CHOICES, default=OT_TYPE_REGULAR)
    ot_amount   = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    reason      = models.TextField(blank=True, default='')
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='approved_overtime',
    )
    status      = models.CharField(max_length=10, choices=STATUS_CHOICES, default=STATUS_PENDING)
    created_by  = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, related_name='created_overtime',
    )
    created_at  = models.DateTimeField(auto_now_add=True)
    updated_at  = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'attendance_overtime'
        ordering = ['-date', '-created_at']
        indexes  = [
            models.Index(fields=['employee', 'date'], name='ot_emp_date_idx'),
            models.Index(fields=['status'],           name='ot_status_idx'),
            models.Index(fields=['date'],             name='ot_date_idx'),
        ]

    def __str__(self) -> str:
        return f'{self.employee_id} OT {self.date} {self.ot_start}–{self.ot_end}'

    @property
    def ot_hours_display(self) -> str:
        h = self.ot_minutes // 60
        m = self.ot_minutes % 60
        if h and m:
            return f'{h}h {m:02d}m'
        return f'{h}h' if h else f'{m}m'


# ══════════════════════════════════════════════════════════════════════════════
#  Attendance Import Log  (bulk upload audit trail)
# ══════════════════════════════════════════════════════════════════════════════

class AttendanceImportLog(models.Model):
    STATUS_PROCESSING = 'processing'
    STATUS_COMPLETED  = 'completed'
    STATUS_FAILED     = 'failed'
    STATUS_CHOICES    = [
        (STATUS_PROCESSING, 'Processing'),
        (STATUS_COMPLETED,  'Completed'),
        (STATUS_FAILED,     'Failed'),
    ]

    id           = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    imported_by  = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, related_name='attendance_imports',
    )
    file_name    = models.CharField(max_length=255)
    total_rows   = models.PositiveIntegerField(default=0)
    success_rows = models.PositiveIntegerField(default=0)
    failed_rows  = models.PositiveIntegerField(default=0)
    skipped_rows = models.PositiveIntegerField(default=0)
    status       = models.CharField(max_length=15, choices=STATUS_CHOICES, default=STATUS_PROCESSING)
    errors       = models.JSONField(default=list, blank=True)
    task_id      = models.CharField(max_length=255, blank=True, default='')
    created_at   = models.DateTimeField(auto_now_add=True)
    updated_at   = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'attendance_import_logs'
        ordering = ['-created_at']

    def __str__(self) -> str:
        return f'Import {self.file_name} ({self.status})'


# ══════════════════════════════════════════════════════════════════════════════
#  Missing Punch Notification Log  (de-duplicate clock-out reminder alerts)
# ══════════════════════════════════════════════════════════════════════════════

class MissingPunchNotification(models.Model):
    """
    Records that a missing clock-out notification was sent to an employee for a date.

    Used by the Celery un-punch detection task to ensure each employee receives
    at most one notification per day regardless of how many times the task runs.
    The unique_together constraint provides the deduplication guarantee.
    """

    id         = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    employee   = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='missing_punch_notifications',
    )
    date       = models.DateField(help_text='The working date for which the notification was sent.')
    channel    = models.CharField(
        max_length=20,
        default='email',
        help_text='Delivery channel: email, in_app, push, sms.',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table        = 'attendance_missing_punch_notifications'
        unique_together = [('employee', 'date', 'channel')]
        indexes         = [
            models.Index(fields=['employee', 'date'], name='mpn_emp_date_idx'),
            models.Index(fields=['date'],             name='mpn_date_idx'),
        ]

    def __str__(self) -> str:
        return f'MissingPunchNotification {self.employee_id} {self.date} [{self.channel}]'


# ══════════════════════════════════════════════════════════════════════════════
#  Attendance Audit Log  (immutable event history per attendance record)
# ══════════════════════════════════════════════════════════════════════════════

class AttendanceAuditLog(models.Model):
    """
    Immutable audit trail for every significant attendance event.

    Never deleted.  created_at is the canonical timestamp; updated_at is kept
    to satisfy the project model convention but will never change in practice.
    """

    EVENT_CLOCK_IN             = 'CLOCK_IN'
    EVENT_CLOCK_OUT            = 'CLOCK_OUT'
    EVENT_PROCESSED            = 'PROCESSED'
    EVENT_RECALCULATED         = 'RECALCULATED'
    EVENT_CORRECTION_SUBMITTED = 'CORRECTION_SUBMITTED'
    EVENT_CORRECTION_APPROVED  = 'CORRECTION_APPROVED'
    EVENT_CORRECTION_REJECTED  = 'CORRECTION_REJECTED'
    EVENT_MANUALLY_EDITED      = 'MANUALLY_EDITED'
    EVENT_IMPORTED             = 'IMPORTED'
    EVENT_REPROCESSED          = 'REPROCESSED'
    EVENT_INVALID_DISCARDED    = 'INVALID_DISCARDED'
    EVENT_INVALID_CONVERTED    = 'INVALID_CONVERTED'

    EVENT_CHOICES = [
        (EVENT_CLOCK_IN,             'Clock In'),
        (EVENT_CLOCK_OUT,            'Clock Out'),
        (EVENT_PROCESSED,            'Attendance Processed'),
        (EVENT_RECALCULATED,         'Attendance Recalculated'),
        (EVENT_CORRECTION_SUBMITTED, 'Correction Submitted'),
        (EVENT_CORRECTION_APPROVED,  'Correction Approved'),
        (EVENT_CORRECTION_REJECTED,  'Correction Rejected'),
        (EVENT_MANUALLY_EDITED,      'Manually Edited'),
        (EVENT_IMPORTED,             'Imported'),
        (EVENT_REPROCESSED,          'Reprocessed'),
        (EVENT_INVALID_DISCARDED,    'Invalid Punch Discarded'),
        (EVENT_INVALID_CONVERTED,    'Invalid Punch Converted'),
    ]

    id           = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    record       = models.ForeignKey(
        'AttendanceRecord',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='audit_logs',
        help_text='The attendance record this event belongs to.',
    )
    employee     = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='attendance_audit_logs',
    )
    date         = models.DateField(help_text='Calendar date of the attendance event (denormalised).')
    event        = models.CharField(max_length=30, choices=EVENT_CHOICES)
    old_value    = models.CharField(max_length=200, blank=True, default='')
    new_value    = models.CharField(max_length=200, blank=True, default='')
    action       = models.CharField(max_length=300, blank=True, default='')
    performed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='attendance_audit_actions',
    )
    remarks      = models.TextField(blank=True, default='')
    created_at   = models.DateTimeField(auto_now_add=True)
    updated_at   = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'attendance_audit_logs'
        ordering = ['created_at']
        indexes  = [
            models.Index(fields=['record', 'created_at'],   name='audit_rec_time_idx'),
            models.Index(fields=['employee', 'date'],       name='audit_emp_date_idx'),
            models.Index(fields=['event'],                  name='audit_event_idx'),
        ]

    def __str__(self) -> str:
        return f'Audit {self.event} | {self.employee_id} | {self.date}'


# ══════════════════════════════════════════════════════════════════════════════
#  Invalid Punch Tracking  (HR action state for detected invalid punches)
# ══════════════════════════════════════════════════════════════════════════════

class InvalidPunch(models.Model):
    """
    Persisted tracking record for an invalid punch detected by get_invalid_punches().

    Created lazily when HR takes the first action (assign/discard/convert) on a punch.
    The `punch` FK is the primary identifier — use AttendancePunch.id in URL paths.
    """

    STATUS_OPEN      = 'open'
    STATUS_ASSIGNED  = 'assigned'
    STATUS_DISCARDED = 'discarded'
    STATUS_CONVERTED = 'converted'
    STATUS_CHOICES   = [
        (STATUS_OPEN,      'Open'),
        (STATUS_ASSIGNED,  'Assigned'),
        (STATUS_DISCARDED, 'Discarded'),
        (STATUS_CONVERTED, 'Converted'),
    ]

    id              = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    punch           = models.OneToOneField(
        AttendancePunch,
        on_delete=models.CASCADE,
        related_name='invalid_record',
    )
    issue_type      = models.CharField(max_length=20, blank=True, default='')
    issue           = models.CharField(max_length=200, blank=True, default='')
    status          = models.CharField(max_length=15, choices=STATUS_CHOICES, default=STATUS_OPEN)

    # Assign tracking
    assigned_to     = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='assigned_invalid_punches',
    )
    assigned_by     = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='assigned_invalid_punch_actions',
    )
    assigned_at     = models.DateTimeField(null=True, blank=True)

    # Discard tracking
    discarded_by    = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='discarded_invalid_punches',
    )
    discarded_at    = models.DateTimeField(null=True, blank=True)
    remarks         = models.TextField(blank=True, default='')

    # Convert tracking
    converted_punch = models.ForeignKey(
        AttendancePunch,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='converted_from_invalid',
    )

    resolved_at     = models.DateTimeField(null=True, blank=True)
    created_at      = models.DateTimeField(auto_now_add=True)
    updated_at      = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'attendance_invalid_punch_actions'
        indexes  = [
            models.Index(fields=['punch'],  name='invp_punch_idx'),
            models.Index(fields=['status'], name='invp_status_idx'),
        ]

    def __str__(self) -> str:
        return f'InvalidPunch {self.punch_id} [{self.status}]'


# ─── Face Registration ─────────────────────────────────────────────────────────

# Identifies the embedding-generating model whose vector space stored
# embeddings belong to — distinct from whatever model detects/locates the
# face or runs the landmark-based liveness check, which can change
# independently without affecting stored-embedding compatibility.
FACE_RECOGNITION_MODEL_VERSION = 'face-api.js-faceRecognitionNet-v1'

# Identifies which wording of the biometric consent notice the employee (or,
# for an HR-witnessed capture, HR on the employee's behalf) agreed to before
# this capture happened. Bump this whenever the consent copy shown in
# frontend/lib/faceApi/consentText.ts changes, so existing rows keep
# recording exactly what was actually agreed to at the time, rather than
# silently being reinterpreted under newer wording. Keep this value in sync
# with that file's own FACE_CONSENT_TEXT_VERSION — there's no shared source
# of truth across the Python/TS boundary, so this is maintained by convention.
FACE_CONSENT_TEXT_VERSION = 'v1'


class FaceRegistrationRequest(models.Model):
    STATUS_PENDING  = 'pending'
    STATUS_APPROVED = 'approved'
    STATUS_REJECTED = 'rejected'
    STATUS_CHOICES  = [
        (STATUS_PENDING,  'Pending'),
        (STATUS_APPROVED, 'Approved'),
        (STATUS_REJECTED, 'Rejected'),
    ]

    id                      = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    employee                = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='face_registration_requests',
    )
    branch                  = models.ForeignKey(
        'branch.Branch',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='face_registration_requests',
    )

    face_embedding          = models.JSONField()
    embedding_model_version = models.CharField(max_length=50, default=FACE_RECOGNITION_MODEL_VERSION)

    # Multi-frame registration capture quality (see frontend lib/faceApi/
    # multiFrameCapture.ts) — both null for any registration that didn't go
    # through the multi-frame + quality-gate pipeline: legacy rows captured
    # before this existed, and any future single-shot capture path that
    # opts out of it. capture_frame_count is how many individual frames
    # passed the per-frame quality gate (lighting/angle/distance/detector
    # confidence) and were actually averaged into face_embedding — never the
    # number of attempts, which can be higher when frames get rejected and
    # retried. capture_variance is the mean pairwise Euclidean distance
    # between those frames' individual descriptors before averaging — a
    # LOWER value means the frames agreed with each other more closely
    # (a tighter, more trustworthy reference), not a measure of match
    # quality against anyone else. This is what lets a later audit tell a
    # stricter-pipeline registration apart from an old single-frame one
    # without needing a separate flag.
    capture_frame_count     = models.PositiveSmallIntegerField(null=True, blank=True)
    capture_variance        = models.FloatField(null=True, blank=True)

    liveness_passed         = models.BooleanField(default=False)
    liveness_score          = models.FloatField(null=True, blank=True)

    # Biometric consent — stamped server-side (never from client-supplied
    # data) at the moment this row is created, whether that's a self-service
    # submission (employee ticked the consent checkbox in FaceRegistrationModal)
    # or an HR-witnessed capture (HR confirms the employee consented in person,
    # HRFaceCaptureModal). Nullable only for rows created before this field
    # existed — every new row must set both together, see
    # FaceRegistrationSubmitSerializer/FaceRegistrationHRRegisterSerializer's
    # consent_acknowledged validation.
    consent_given_at        = models.DateTimeField(null=True, blank=True)
    consent_text_version    = models.CharField(max_length=20, blank=True, default='')

    status                  = models.CharField(
        max_length=20, choices=STATUS_CHOICES, default=STATUS_PENDING, db_index=True,
    )
    approved_by             = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='face_registrations_approved',
    )
    approved_at             = models.DateTimeField(null=True, blank=True)
    notes                   = models.TextField(blank=True, default='')

    # Whether THIS is the row punch-time matching compares against for its
    # employee — orthogonal to status. status records the approval decision
    # and never changes once made (an old registration really was approved,
    # that stays true forever, for audit purposes); is_active records which
    # single approved row is the current reference, and does change as newer
    # registrations replace older ones. Before this field, _resolve_active_
    # registration (services_face_matching.py) picked the "current" reference
    # by ordering approved rows by -approved_at with nothing preventing more
    # than one row from being approved at once — correctness depended
    # entirely on approval timestamps happening to stay monotonic with
    # intent. The partial unique constraint below is what actually enforces
    # "at most one active reference per employee", not this field alone.
    is_active               = models.BooleanField(default=False)

    created_at              = models.DateTimeField(auto_now_add=True)
    updated_at              = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'attendance_face_registration_request'
        ordering = ['-created_at']
        constraints = [
            models.UniqueConstraint(
                fields=['employee'],
                condition=models.Q(is_active=True),
                name='uniq_active_face_registration_per_employee',
            ),
        ]

    def __str__(self) -> str:
        return f'{self.employee.full_name} — face registration ({self.status})'


# ─── Face Verification Attempt (punch-time audit + anti-spoofing) ─────────────

class FaceVerificationAttempt(models.Model):
    """
    Immutable audit row for every face-match attempt at punch time (web or
    voice clock-in/out) — distinct from FaceRegistrationRequest, which is a
    one-time enrollment record, not a per-punch attempt log.

    Backs two independent defenses in services_face_matching.py, both scoped
    to punch-time verification only (registration submissions are a single
    HR-reviewed event and are out of scope for either):

      1. Attempt cap — MAX_FAILED_ATTEMPTS failed rows for the same employee
         within ATTEMPT_CAP_WINDOW_SECONDS blocks further tries. Deliberately
         separate from any conversational retry count (e.g. the voice clock-in
         flow's own "3 tries then suggest manual clock-in" — see
         apps.voice_commands.conversation_clock_in_face): that counter resets
         every time a NEW voice command starts a fresh conversation, so on its
         own it could never stop someone from just starting over repeatedly.
         This table's window is keyed on the employee alone, across both
         source channels, so switching channels can't reset it either.

      2. Replay detection — a byte-identical embedding (compared via
         embedding_fingerprint, a SHA-256 digest, so the raw vector itself
         is never persisted a second time outside FaceRegistrationRequest)
         submitted again within REPLAY_WINDOW_SECONDS from a DIFFERENT
         capture_session_id is rejected as a replayed capture rather than a
         fresh live one. capture_session_id is a client-generated UUID minted
         once per camera session (useFaceLivenessCapture.start()) — multiple
         internal retries within the SAME open camera are one session and
         never flagged; a genuinely separate capture (new modal open, new
         device, a recorded-and-resent payload) gets a new id.

    Never deleted — kept for HR/security audit the same way AttendanceAuditLog
    is (see that model's own docstring for the same reasoning).
    """

    id                    = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    employee              = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='face_verification_attempts',
    )
    source                = models.CharField(
        max_length=10,
        choices=[('web', 'Web'), ('voice', 'Voice Command')],
        help_text='Which clock-in channel produced this attempt.',
    )
    capture_session_id    = models.CharField(
        max_length=64, blank=True, default='',
        help_text='Client-generated UUID for the camera session this capture came from.',
    )
    embedding_fingerprint = models.CharField(
        max_length=64,
        help_text='SHA-256 hex digest of the submitted embedding — never the raw vector.',
    )
    liveness_passed       = models.BooleanField(default=False)
    liveness_score        = models.FloatField(null=True, blank=True)
    is_match               = models.BooleanField(default=False)
    distance               = models.FloatField(
        null=True, blank=True,
        help_text='Euclidean distance to the approved registration. Null when '
                   'rejected before a distance could be computed (e.g. blocked by the cap).',
    )
    REJECTION_MISMATCH   = 'mismatch'
    REJECTION_REPLAY     = 'replay_detected'
    REJECTION_CAP        = 'attempt_cap_exceeded'
    REJECTION_INSECURE   = 'insecure_transport'
    # Distance was within FACE_MATCH_MAX_DISTANCE but close enough to the
    # boundary (see services_face_matching.FACE_MATCH_LOW_CONFIDENCE_MARGIN)
    # that it's rejected outright, is_match=False on this row, same as
    # REJECTION_MISMATCH — kept as its own reason (not folded into
    # REJECTION_MISMATCH) so this specific failure mode stays distinguishable
    # in the audit trail. Originally an escalating "pending confirmation"
    # state that accepted the punch once a second capture corroborated it;
    # removed after a 2026-08-13 retest showed the same impostor reproducing
    # a borderline distance on 4 of 5 captures — not independent coincidences,
    # so a second draw didn't meaningfully lower the odds. No amount of
    # retrying turns this rejection into an accept anymore.
    REJECTION_LOW_CONFIDENCE_PENDING = 'low_confidence_pending'
    # The client's own multi-frame liveness/motion check reported failure —
    # rejected before the distance match runs at all, same trust level as
    # REJECTION_REPLAY/REJECTION_CAP. See services_face_matching's own note:
    # this stops an honest client from proceeding after reporting its own
    # failure, it is not a defense against a client that always lies and
    # reports True — that would need server-side frame analysis, which this
    # endpoint deliberately never receives.
    REJECTION_LIVENESS_FAILED = 'liveness_failed'
    REJECTION_CHOICES    = [
        ('',                              'Matched'),
        (REJECTION_MISMATCH,              'Face Mismatch'),
        (REJECTION_REPLAY,                'Replay Detected'),
        (REJECTION_CAP,                   'Attempt Cap Exceeded'),
        (REJECTION_INSECURE,              'Insecure Transport'),
        (REJECTION_LOW_CONFIDENCE_PENDING, 'Low-Confidence Match Rejected'),
        (REJECTION_LIVENESS_FAILED,       'Liveness Check Failed'),
    ]
    rejection_reason     = models.CharField(max_length=30, choices=REJECTION_CHOICES, blank=True, default='')

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'attendance_face_verification_attempt'
        ordering = ['-created_at']
        indexes  = [
            models.Index(fields=['employee', 'created_at'], name='fva_emp_time_idx'),
            models.Index(fields=['employee', 'is_match', 'created_at'], name='fva_emp_match_time_idx'),
            models.Index(fields=['embedding_fingerprint', 'created_at'], name='fva_fingerprint_time_idx'),
        ]

    def __str__(self) -> str:
        outcome = 'matched' if self.is_match else (self.rejection_reason or 'mismatch')
        return f'{self.employee_id} — {self.source} face attempt ({outcome})'
