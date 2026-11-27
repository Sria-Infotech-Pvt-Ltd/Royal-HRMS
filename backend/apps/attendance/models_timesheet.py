"""
Weekly project timesheets (Monday to Sunday): the employee enters hours per assigned project per day, the assigned
approver approves or sends it back, and an approved sheet is locked.

Four tables:
  Timesheet        one per employee per week, with the approval state and totals snapshotted at submit time
  TimesheetLine    one project row in the grid (or the single Internal / non-project row); the project's id, code and name
                   are COPIED here, so a line keeps its project even if the assignment is later edited or ended
  TimesheetEntry   one cell: hours (0-24, quarter-hour steps) and an optional note for one line on one day
  TimesheetEvent   append-only history of every submit / return / approve / unlock, with a snapshot of the sheet at that
                   moment, so an earlier version is never lost even if HR reopens an approved sheet

`WeeklyTimesheetSubmission` (models.py) is the old "I reviewed my hours" tick box. It is left untouched and is not migrated.
"""
from __future__ import annotations

import uuid
from decimal import Decimal

from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.db.models import Q

STATUS_DRAFT = 'draft'
STATUS_SUBMITTED = 'submitted'
STATUS_RETURNED = 'returned'
STATUS_APPROVED = 'approved'
TIMESHEET_STATUS_CHOICES = [
    (STATUS_DRAFT, 'Draft'),
    (STATUS_SUBMITTED, 'Submitted'),
    (STATUS_RETURNED, 'Returned'),
    (STATUS_APPROVED, 'Approved'),
]

# A sheet the employee may still edit; submitted and approved sheets are read-only.
EDITABLE_STATUSES = (STATUS_DRAFT, STATUS_RETURNED)

EVENT_SUBMITTED = 'submitted'
EVENT_RESUBMITTED = 'resubmitted'
EVENT_RETURNED = 'returned'
EVENT_APPROVED = 'approved'
EVENT_UNLOCKED = 'unlocked'
TIMESHEET_EVENT_CHOICES = [
    (EVENT_SUBMITTED, 'Submitted'),
    (EVENT_RESUBMITTED, 'Resubmitted'),
    (EVENT_RETURNED, 'Returned'),
    (EVENT_APPROVED, 'Approved'),
    (EVENT_UNLOCKED, 'Unlocked'),
]

MAX_DAILY_HOURS = Decimal('24')
HOUR_STEP = Decimal('0.25')


class Timesheet(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    employee = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='timesheets')
    week_start = models.DateField(help_text='The Monday of the week.')
    status = models.CharField(max_length=10, choices=TIMESHEET_STATUS_CHOICES, default=STATUS_DRAFT, db_index=True)

    approver = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='timesheets_to_approve',
        help_text='Resolved when the sheet is submitted (see apps.accounts.services_approval).',
    )
    submitted_at = models.DateTimeField(null=True, blank=True)
    decided_at = models.DateTimeField(null=True, blank=True)
    decided_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='timesheets_decided',
    )
    return_reason = models.TextField(blank=True, default='')
    submit_count = models.PositiveSmallIntegerField(default=0)
    is_late = models.BooleanField(default=False, help_text='Submitted after the Friday due date of its week.')

    # Snapshots taken at submit time: reports and the approver's list read these, not a live recount.
    total_hours = models.DecimalField(max_digits=6, decimal_places=2, default=Decimal('0'))
    billable_hours = models.DecimalField(max_digits=6, decimal_places=2, default=Decimal('0'))
    attendance_minutes = models.PositiveIntegerField(default=0)
    branch_name = models.CharField(max_length=100, blank=True, default='')

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'attendance_timesheets'
        ordering = ['-week_start', '-created_at']
        constraints = [
            models.UniqueConstraint(fields=['employee', 'week_start'], name='uniq_timesheet_employee_week'),
            # ISO weekday 1 = Monday. Guards every writer, not only the service.
            models.CheckConstraint(condition=Q(week_start__iso_week_day=1), name='timesheet_week_starts_on_monday'),
        ]
        indexes = [
            models.Index(fields=['approver', 'status'], name='timesheet_approver_status_idx'),
            models.Index(fields=['week_start', 'status'], name='timesheet_week_status_idx'),
        ]

    def __str__(self) -> str:
        return f'{self.employee_id} - week of {self.week_start} ({self.status})'


class TimesheetLine(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    timesheet = models.ForeignKey(Timesheet, on_delete=models.CASCADE, related_name='lines')
    # The project assignment's assignment_id; blank for the Internal / non-project row. No foreign key: assignments are
    # keyed by employee_code (see models_project_assignment.py), and the line keeps its own copy of the project name.
    assignment_id = models.BigIntegerField(null=True, blank=True)
    project_id = models.BigIntegerField(null=True, blank=True)
    project_code = models.CharField(max_length=50, blank=True, default='')
    project_name = models.CharField(max_length=255, blank=True, default='')
    is_internal = models.BooleanField(default=False, help_text='The one Internal / non-project work row.')
    is_billable = models.BooleanField(default=False)
    sort_order = models.PositiveSmallIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'attendance_timesheet_lines'
        ordering = ['sort_order', 'created_at']
        constraints = [
            models.UniqueConstraint(fields=['timesheet'], condition=Q(is_internal=True), name='uniq_timesheet_internal_line'),
            models.UniqueConstraint(
                fields=['timesheet', 'assignment_id'], condition=Q(assignment_id__isnull=False), name='uniq_timesheet_line_assignment',
            ),
            models.CheckConstraint(
                condition=Q(is_internal=False) | Q(assignment_id__isnull=True), name='timesheet_internal_line_has_no_assignment',
            ),
        ]

    def __str__(self) -> str:
        return f'{"Internal" if self.is_internal else self.project_name} ({self.timesheet_id})'


class TimesheetEntry(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    line = models.ForeignKey(TimesheetLine, on_delete=models.CASCADE, related_name='entries')
    entry_date = models.DateField()
    # Quarter-hour steps are enforced by the service (and the serializer); the 0-24 range is also a database check.
    hours = models.DecimalField(
        max_digits=4, decimal_places=2, validators=[MinValueValidator(Decimal('0')), MaxValueValidator(MAX_DAILY_HOURS)],
    )
    note = models.CharField(max_length=500, blank=True, default='')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'attendance_timesheet_entries'
        ordering = ['entry_date']
        constraints = [
            models.UniqueConstraint(fields=['line', 'entry_date'], name='uniq_timesheet_entry_line_date'),
            models.CheckConstraint(condition=Q(hours__gte=0) & Q(hours__lte=24), name='timesheet_entry_hours_0_to_24'),
        ]

    def __str__(self) -> str:
        return f'{self.line_id} {self.entry_date}: {self.hours}h'


class TimesheetEvent(models.Model):
    """Append-only. A row is written once and never changed or deleted by the application."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    timesheet = models.ForeignKey(Timesheet, on_delete=models.CASCADE, related_name='events')
    event_type = models.CharField(max_length=12, choices=TIMESHEET_EVENT_CHOICES)
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='+')
    from_status = models.CharField(max_length=10, blank=True, default='')
    to_status = models.CharField(max_length=10)
    reason = models.TextField(blank=True, default='')
    # The sheet as it was at this moment: totals plus every line and day, so an earlier version can always be read back.
    snapshot = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'attendance_timesheet_events'
        ordering = ['created_at']
        indexes = [models.Index(fields=['timesheet', 'created_at'], name='timesheet_event_ts_created_idx')]

    def __str__(self) -> str:
        return f'{self.event_type} {self.timesheet_id}'

    def save(self, *args, **kwargs):
        # History is never rewritten: only the first save (the insert) is allowed.
        if not self._state.adding:
            raise ValueError('A timesheet event is append-only and cannot be changed.')
        super().save(*args, **kwargs)
