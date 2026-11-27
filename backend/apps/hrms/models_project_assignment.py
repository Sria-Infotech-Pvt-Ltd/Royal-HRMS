"""
Project assignments shown in an employee's Work Status. Admins create and manage them in AIRA HRMS (assign, edit,
extend, end); see services_project_assignments.py.

Linked to an employee by `employee_code` (our employee_id), not a ForeignKey, because timesheet lines copy
`assignment_id` / `project_id` and look assignments up by them. `assignment_id` is our own running number, kept above
every id an old timesheet line already uses so a new assignment never matches an old line.

History is never deleted: every change to a row is recorded as a ProjectAssignmentEvent with the admin who made it.
"""
from __future__ import annotations

import uuid

from django.conf import settings
from django.db import models


class ProjectAssignment(models.Model):
    STATUS_ACTIVE = 'active'
    STATUS_COMPLETED = 'completed'
    STATUS_CHOICES = [(STATUS_ACTIVE, 'Active'), (STATUS_COMPLETED, 'Completed')]

    WORK_MODE_OFFICE = 'office'
    WORK_MODE_HOME = 'home'
    WORK_MODE_CLIENT_SITE = 'client_site'
    WORK_MODE_HYBRID = 'hybrid'
    WORK_MODE_CHOICES = [
        (WORK_MODE_OFFICE, 'Work From Office (WFO)'),
        (WORK_MODE_HOME, 'Work From Home (WFH)'),
        (WORK_MODE_CLIENT_SITE, 'Client Location (On-site)'),
        (WORK_MODE_HYBRID, 'Hybrid (Office + Home)'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    assignment_id = models.BigIntegerField(unique=True, help_text='Running number; timesheet lines refer to it.')
    employee_code = models.CharField(max_length=20, db_index=True, help_text='Matches User.employee_id.')
    # The same project name (ignoring case) always gets the same project_id, so timesheet reports group by project.
    project_id = models.BigIntegerField()
    project_code = models.CharField(max_length=50, blank=True)
    project_name = models.CharField(max_length=255)
    assignment_start_date = models.DateField()
    assignment_end_date = models.DateField()
    assignment_status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_ACTIVE, db_index=True)
    assignment_status_display = models.CharField(max_length=30, blank=True, default='Active')
    role = models.CharField(max_length=100, blank=True)
    # Where the employee works on this project. work_location names the place: the client's address or site for
    # client_site (required there), optionally the office/branch otherwise.
    work_mode = models.CharField(max_length=20, choices=WORK_MODE_CHOICES, default=WORK_MODE_OFFICE)
    work_location = models.CharField(max_length=255, blank=True)
    notes = models.TextField(blank=True)
    assigned_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='+',
    )
    # Set by the daily job once the "ending soon" reminder has gone out for the current end date; cleared on extend.
    ending_soon_notified_on = models.DateField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'hrms_project_assignments'
        ordering = ['-assignment_start_date', '-assignment_id']

    def __str__(self):
        return f'{self.employee_code} → {self.project_name} ({self.assignment_status})'


class ProjectAssignmentEvent(models.Model):
    """Append-only change history of one assignment: who changed it and which fields moved."""
    EVENT_CREATED = 'created'
    EVENT_UPDATED = 'updated'
    EVENT_EXTENDED = 'extended'
    EVENT_ENDED = 'ended'
    EVENT_COMPLETED = 'completed'

    SOURCE_MANUAL = 'manual'
    SOURCE_SYSTEM = 'system'

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    assignment = models.ForeignKey(ProjectAssignment, on_delete=models.CASCADE, related_name='events')
    event_type = models.CharField(max_length=20)
    # {"field": [old, new]}, with dates stringified so it stays JSON.
    changes = models.JSONField(default=dict, blank=True)
    # manual (an admin did it) | system (the daily job completed it).
    source = models.CharField(max_length=20)
    # The admin's name, or the job name for system events.
    triggered_by = models.CharField(max_length=100, blank=True)
    reason = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'hrms_project_assignment_events'
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.assignment_id}:{self.event_type}'
