"""Input validation for the admin actions on an employee's project assignments (assign, edit, extend, end)."""
from rest_framework import serializers

from apps.hrms.models import ProjectAssignment

CLIENT_SITE = ProjectAssignment.WORK_MODE_CLIENT_SITE


def _check_dates(start, end) -> None:
    if start and end and end < start:
        raise serializers.ValidationError({'end_date': 'End date cannot be before the start date.'})


def _check_location(work_mode, work_location) -> None:
    if work_mode == CLIENT_SITE and not (work_location or '').strip():
        raise serializers.ValidationError({'work_location': 'Enter the client location (address or site name).'})


class AssignProjectSerializer(serializers.Serializer):
    project_name = serializers.CharField(max_length=255, trim_whitespace=True)
    start_date   = serializers.DateField()
    end_date     = serializers.DateField()
    role         = serializers.CharField(max_length=100, required=False, allow_blank=True, default='')
    work_mode    = serializers.ChoiceField(choices=ProjectAssignment.WORK_MODE_CHOICES)
    work_location = serializers.CharField(max_length=255, required=False, allow_blank=True, default='')
    notes        = serializers.CharField(max_length=2000, required=False, allow_blank=True, default='')

    def validate_project_name(self, value: str) -> str:
        if not value.strip():
            raise serializers.ValidationError('Enter the project name.')
        return value.strip()

    def validate(self, attrs):
        _check_dates(attrs['start_date'], attrs['end_date'])
        _check_location(attrs['work_mode'], attrs.get('work_location'))
        return attrs


class EditAssignmentSerializer(AssignProjectSerializer):
    """Same fields as assigning; all optional so only what changed needs to be sent."""
    project_name = serializers.CharField(max_length=255, trim_whitespace=True, required=False)
    start_date   = serializers.DateField(required=False)
    end_date     = serializers.DateField(required=False)
    role         = serializers.CharField(max_length=100, required=False, allow_blank=True)
    work_mode    = serializers.ChoiceField(choices=ProjectAssignment.WORK_MODE_CHOICES, required=False)
    work_location = serializers.CharField(max_length=255, required=False, allow_blank=True)
    notes        = serializers.CharField(max_length=2000, required=False, allow_blank=True)

    def validate(self, attrs):
        if not attrs:
            raise serializers.ValidationError('Nothing to change.')
        assignment = self.context['assignment']
        _check_dates(attrs.get('start_date', assignment.assignment_start_date),
                     attrs.get('end_date', assignment.assignment_end_date))
        _check_location(attrs.get('work_mode', assignment.work_mode),
                        attrs.get('work_location', assignment.work_location))
        return attrs


class ExtendAssignmentSerializer(serializers.Serializer):
    end_date = serializers.DateField()
    reason   = serializers.CharField(max_length=1000, required=False, allow_blank=True, default='')

    def validate_end_date(self, value):
        if value <= self.context['assignment'].assignment_end_date:
            raise serializers.ValidationError('The new end date must be after the current end date.')
        return value


class EndAssignmentSerializer(serializers.Serializer):
    """End date defaults to today when omitted."""
    end_date = serializers.DateField(required=False)
    reason   = serializers.CharField(max_length=1000, required=False, allow_blank=True, default='')

    def validate_end_date(self, value):
        if value < self.context['assignment'].assignment_start_date:
            raise serializers.ValidationError('End date cannot be before the start date.')
        return value
