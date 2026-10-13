"""
Phase 8A Task B — onboarding/offboarding task checklists.

Scoped down: `assignee_resolver` is a plain code string resolved by
services_checklist.ASSIGNEE_RESOLVERS (employee/manager/hr/specific-user),
not a full 3B resolver-plugin system. Dependencies are a simple "this task
blocks that task" FK, not a general DAG validator. No 3B inbox/reminder
wiring — ChecklistTaskInstance is a real, queryable to-do list; surfacing
it in a notifications inbox is a separate, later integration task.
Creation is EVENT-TRIGGERED BY CODE CALLING A FUNCTION (services_checklist
.create_instance_from_template()), not by a signal auto-wired to
HireActionCompleteView/SeparationRequest — stated plainly so it's clear
nothing fires automatically yet from a real hire/separation today.
"""
import uuid

from django.db import models


class ChecklistTemplate(models.Model):
    TYPE_PRE_BOARDING = 'pre_boarding'
    TYPE_ONBOARDING   = 'onboarding'
    TYPE_OFFBOARDING  = 'offboarding'
    TYPE_TRANSFER     = 'internal_transfer'
    TYPE_CUSTOM       = 'custom'
    TYPE_CHOICES = [
        (TYPE_PRE_BOARDING, 'Pre-boarding'), (TYPE_ONBOARDING, 'Onboarding'),
        (TYPE_OFFBOARDING, 'Offboarding'), (TYPE_TRANSFER, 'Internal transfer'), (TYPE_CUSTOM, 'Custom'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    code = models.CharField(max_length=40, unique=True)
    name = models.CharField(max_length=100)
    checklist_type = models.CharField(max_length=20, choices=TYPE_CHOICES, default=TYPE_ONBOARDING)
    is_active = models.BooleanField(default=False, help_text='Seeded templates default OFF — an admin opts in explicitly.')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'hrms_checklist_templates_v2'
        ordering = ['code']

    def __str__(self):
        return self.code


class ChecklistTaskTemplate(models.Model):
    ANCHOR_JOINING_DATE      = 'joining_date'
    ANCHOR_LAST_WORKING_DAY  = 'last_working_day'
    ANCHOR_ACTION_DATE       = 'action_date'
    ANCHOR_CHOICES = [
        (ANCHOR_JOINING_DATE, 'Joining date'), (ANCHOR_LAST_WORKING_DAY, 'Last working day'),
        (ANCHOR_ACTION_DATE, 'Action date'),
    ]
    ASSIGNEE_EMPLOYEE = 'employee'
    ASSIGNEE_MANAGER  = 'manager'
    ASSIGNEE_HR       = 'hr'
    ASSIGNEE_BUDDY    = 'buddy'
    ASSIGNEE_CHOICES = [
        (ASSIGNEE_EMPLOYEE, 'Employee'), (ASSIGNEE_MANAGER, 'Manager'),
        (ASSIGNEE_HR, 'HR'), (ASSIGNEE_BUDDY, 'Buddy'),
    ]
    COMPLETION_MANUAL = 'manual'
    COMPLETION_DOCUMENT_VERIFIED = 'document_verified'
    COMPLETION_CHOICES = [(COMPLETION_MANUAL, 'Manual'), (COMPLETION_DOCUMENT_VERIFIED, 'Document verified')]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    template = models.ForeignKey(ChecklistTemplate, on_delete=models.CASCADE, related_name='task_templates')
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    assignee_resolver = models.CharField(max_length=20, choices=ASSIGNEE_CHOICES, default=ASSIGNEE_EMPLOYEE)
    due_anchor = models.CharField(max_length=20, choices=ANCHOR_CHOICES, default=ANCHOR_JOINING_DATE)
    due_offset_days = models.SmallIntegerField(default=0, help_text='Signed — negative = before the anchor date.')
    is_mandatory = models.BooleanField(default=True)
    depends_on = models.ForeignKey('self', on_delete=models.SET_NULL, null=True, blank=True, related_name='blocks')
    completion_rule = models.CharField(max_length=20, choices=COMPLETION_CHOICES, default=COMPLETION_MANUAL)
    order = models.PositiveSmallIntegerField(default=0)

    class Meta:
        db_table = 'hrms_checklist_task_templates_v2'
        ordering = ['template', 'order']

    def __str__(self):
        return f'{self.template.code} › {self.title}'


class ChecklistInstance(models.Model):
    STATUS_IN_PROGRESS = 'in_progress'
    STATUS_COMPLETED   = 'completed'
    STATUS_CHOICES = [(STATUS_IN_PROGRESS, 'In progress'), (STATUS_COMPLETED, 'Completed')]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    template = models.ForeignKey(ChecklistTemplate, on_delete=models.PROTECT, related_name='instances')
    employee = models.ForeignKey('accounts.User', on_delete=models.CASCADE, related_name='checklist_instances')
    anchor_date = models.DateField(help_text='The real joining_date/last_working_day/action_date this instance\'s due dates were computed from.')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_IN_PROGRESS)
    created_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = 'hrms_checklist_instances_v2'
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.employee_id} — {self.template.code}'


class ChecklistTaskInstance(models.Model):
    STATUS_PENDING   = 'pending'
    STATUS_BLOCKED   = 'blocked'
    STATUS_DONE      = 'done'
    STATUS_CHOICES = [(STATUS_PENDING, 'Pending'), (STATUS_BLOCKED, 'Blocked'), (STATUS_DONE, 'Done')]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    checklist = models.ForeignKey(ChecklistInstance, on_delete=models.CASCADE, related_name='tasks')
    task_template = models.ForeignKey(ChecklistTaskTemplate, on_delete=models.PROTECT, related_name='task_instances')
    assignee = models.ForeignKey('accounts.User', on_delete=models.SET_NULL, null=True, blank=True, related_name='checklist_tasks_assigned')
    due_date = models.DateField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_PENDING)
    completed_at = models.DateTimeField(null=True, blank=True)
    completed_by = models.ForeignKey('accounts.User', on_delete=models.SET_NULL, null=True, blank=True, related_name='checklist_tasks_completed')

    class Meta:
        db_table = 'hrms_checklist_task_instances_v2'
        ordering = ['due_date']

    def __str__(self):
        return f'{self.checklist_id} › {self.task_template.title}'
