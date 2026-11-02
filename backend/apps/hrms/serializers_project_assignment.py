from decimal import Decimal

from rest_framework import serializers

WEBHOOK_EVENT_PROJECTS_CHANGED = 'employee.projects_changed'
MAX_ASSIGNMENTS_PER_PUSH = 500


class ProjectAssignmentRowSerializer(serializers.Serializer):
    """One assignment row, shaped like the budgeting tool's project-assignments API. Unknown fields are ignored —
    they've said new fields may be added without notice."""
    assignment_id             = serializers.IntegerField()
    project_id                = serializers.IntegerField()
    project_name              = serializers.CharField(max_length=255)
    project_status            = serializers.CharField(max_length=50, required=False, allow_blank=True, default='')
    project_status_display    = serializers.CharField(max_length=30, required=False, allow_blank=True, default='')
    project_start_date        = serializers.DateField(required=False, allow_null=True, default=None)
    project_end_date          = serializers.DateField(required=False, allow_null=True, default=None)
    # Required: every assignment must have a start date (Work Status history is built on it).
    assignment_start_date     = serializers.DateField()
    assignment_end_date       = serializers.DateField(required=False, allow_null=True, default=None)
    assignment_status         = serializers.CharField(max_length=20, required=False, allow_blank=True, default='')
    assignment_status_display = serializers.CharField(max_length=30, required=False, allow_blank=True, default='')
    milestone_name            = serializers.CharField(max_length=255, required=False, allow_blank=True, allow_null=True, default='')
    updated_at                = serializers.DateTimeField(required=False, allow_null=True, default=None)
    # Not sent by Project Budgeting today; accepted so they show up the day it starts sending them.
    project_code              = serializers.CharField(max_length=50, required=False, allow_blank=True, allow_null=True, default='')
    role                      = serializers.CharField(max_length=100, required=False, allow_blank=True, allow_null=True, default='')
    allocation_percent        = serializers.DecimalField(max_digits=5, decimal_places=2, min_value=Decimal(0), max_value=Decimal(100), required=False, allow_null=True, default=None)

    def validate(self, attrs):
        start, end = attrs['assignment_start_date'], attrs.get('assignment_end_date')
        if end and end < start:
            raise serializers.ValidationError('assignment_end_date cannot be before assignment_start_date.')
        return attrs


class ProjectsChangedWebhookSerializer(serializers.Serializer):
    """Body of the employee.projects_changed push: the employee's COMPLETE current list, not a diff, so an empty list
    means "no projects". The list may arrive as `projects` or `results` (same row shape as their pull API)."""
    event       = serializers.CharField(required=False, allow_blank=True, default=WEBHOOK_EVENT_PROJECTS_CHANGED)
    employee_id = serializers.CharField(max_length=20)
    projects    = serializers.ListField(child=ProjectAssignmentRowSerializer(), required=False, max_length=MAX_ASSIGNMENTS_PER_PUSH)
    results     = serializers.ListField(child=ProjectAssignmentRowSerializer(), required=False, max_length=MAX_ASSIGNMENTS_PER_PUSH)

    def validate(self, attrs):
        if 'projects' not in attrs and 'results' not in attrs:
            raise serializers.ValidationError('Send the employee\'s project list as "projects".')
        attrs['rows'] = attrs.get('projects', attrs.get('results'))
        return attrs
