"""
Project/task assignments synced from the Project Budget & Tracking tool ("Project Budgeting"), shown in an employee's
Work Status. Project Budgeting is the source of truth: these rows are read-only in AIRA HRMS.

Employees only — freelancers/vendors/external resources are deliberately not stored. Rows are keyed on Project
Budgeting's own `assignment_id` (unique, never reused) and linked to an employee by `employee_code` (our employee_id),
not a ForeignKey: a push can arrive for an employee we don't have yet, and the row should simply start showing once
that employee exists rather than be rejected.

History is never deleted. An assignment that disappears from the source is marked "removed" (and closed), and every
change to a row is recorded as a ProjectAssignmentEvent, so HR can see what changed, when, and what triggered it.
"""
from __future__ import annotations

import uuid

from django.db import models

END_DATE_SOURCE_BUDGETING = ''
END_DATE_SOURCE_AUTO_CLOSED = 'auto_closed'


class ProjectAssignment(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    assignment_id = models.BigIntegerField(unique=True, help_text="Project Budget tool's assignment id.")
    employee_code = models.CharField(max_length=20, db_index=True, help_text='Matches User.employee_id.')
    project_id = models.BigIntegerField()
    # Project Budgeting doesn't send a separate project code today; blank until/unless it does.
    project_code = models.CharField(max_length=50, blank=True)
    project_name = models.CharField(max_length=255)
    # Plain strings, not choices: Project Budgeting may add new status values without notice.
    project_status = models.CharField(max_length=50, blank=True)
    project_status_display = models.CharField(max_length=30, blank=True)
    project_start_date = models.DateField(null=True, blank=True)
    project_end_date = models.DateField(null=True, blank=True)
    assignment_start_date = models.DateField(null=True, blank=True)
    assignment_end_date = models.DateField(null=True, blank=True)
    # '' = the end date (or lack of one) came from Project Budgeting; 'auto_closed' = we set it because the employee
    # moved to a new project (see services_project_assignments.auto_close_previous).
    end_date_source = models.CharField(max_length=20, blank=True, default=END_DATE_SOURCE_BUDGETING)
    assignment_status = models.CharField(max_length=20, blank=True, db_index=True)
    assignment_status_display = models.CharField(max_length=30, blank=True)
    # Blank means the whole project, not one milestone.
    milestone_name = models.CharField(max_length=255, blank=True)
    # Not sent by Project Budgeting today — stored if it ever is.
    role = models.CharField(max_length=100, blank=True)
    allocation_percent = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    source_updated_at = models.DateTimeField(null=True, blank=True)
    last_synced_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'hrms_project_assignments'
        ordering = ['-assignment_start_date', '-assignment_id']

    def __str__(self):
        return f'{self.employee_code} → {self.project_name} ({self.assignment_status})'


class ProjectAssignmentEvent(models.Model):
    """Append-only change history of one assignment: who/what changed it and which fields moved."""
    EVENT_CREATED = 'created'
    EVENT_UPDATED = 'updated'
    EVENT_ENDED = 'ended'
    EVENT_AUTO_CLOSED = 'auto_closed'
    EVENT_REMOVED = 'removed_in_source'
    EVENT_RESTORED = 'restored'

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    assignment = models.ForeignKey(ProjectAssignment, on_delete=models.CASCADE, related_name='events')
    event_type = models.CharField(max_length=20)
    # {"field": [old, new]} — dates/decimals stringified so it stays JSON.
    changes = models.JSONField(default=dict, blank=True)
    # How it arrived: webhook | pull | reconcile.
    source = models.CharField(max_length=20)
    # Which external system key made the call (ExternalAPIKey.name), or a job name for scheduled syncs.
    triggered_by = models.CharField(max_length=100, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'hrms_project_assignment_events'
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.assignment_id}:{self.event_type}'


class ProjectSyncLog(models.Model):
    """One row per sync attempt for an employee (or per whole-list reconcile, employee_code blank)."""
    STATUS_SUCCESS = 'success'
    STATUS_FAILED = 'failed'
    STATUS_UNMATCHED = 'unmatched'

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    source = models.CharField(max_length=20)
    triggered_by = models.CharField(max_length=100, blank=True)
    employee_code = models.CharField(max_length=20, blank=True, db_index=True)
    status = models.CharField(max_length=20, db_index=True)
    saved = models.PositiveIntegerField(default=0)
    changed = models.PositiveIntegerField(default=0)
    removed = models.PositiveIntegerField(default=0)
    message = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'hrms_project_sync_logs'
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.source}:{self.employee_code or "all"}:{self.status}'
