"""Request validation for the timesheet endpoints. The hours themselves are validated by the service (services_timesheet_validation),
which reports every problem at once; these serializers only check the small query and decision inputs."""
from __future__ import annotations

from rest_framework import serializers

from apps.attendance.models_timesheet import TIMESHEET_STATUS_CHOICES
from apps.attendance.services_timesheet_decisions import MAX_REASON_LENGTH

_STATUSES = {value for value, _ in TIMESHEET_STATUS_CHOICES}


class WeekQuerySerializer(serializers.Serializer):
    """?week=YYYY-MM-DD: any date in the week (reading) or its Monday (writing, checked by the service)."""

    week = serializers.DateField(required=False)


class TeamListQuerySerializer(serializers.Serializer):
    """?status=submitted or ?status=approved,returned (any of draft excluded) and ?week=YYYY-MM-DD."""

    status = serializers.CharField(required=False, allow_blank=True, default='')
    week = serializers.DateField(required=False)

    def validate_status(self, value: str) -> str:
        wanted = [item.strip() for item in value.split(',') if item.strip()]
        unknown = [item for item in wanted if item not in _STATUSES]
        if unknown:
            raise serializers.ValidationError(f'Unknown status: {", ".join(unknown)}.')
        return ','.join(wanted)


class ReasonSerializer(serializers.Serializer):
    reason = serializers.CharField(max_length=MAX_REASON_LENGTH, allow_blank=False, trim_whitespace=True)
