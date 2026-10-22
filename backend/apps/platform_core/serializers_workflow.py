from rest_framework import serializers

from apps.platform_core.models import (
    Delegation, EventType, JobRun, JobType, MessageTemplate, NotificationDelivery, NotificationRule,
    ScheduledJob, UserNotificationPreference, WorkflowApproverOverride, WorkflowDefinition, WorkflowHistory,
    WorkflowInstance, WorkflowStep, WorkflowTask,
)


class WorkflowStepSerializer(serializers.ModelSerializer):
    class Meta:
        model = WorkflowStep
        fields = [
            'id', 'definition', 'code', 'label', 'order', 'step_type', 'resolver', 'resolver_params',
            'quorum', 'quorum_n', 'skip_if_approver_is_requester', 'skip_if_same_as_previous_step',
            'skip_condition', 'auto_approve_condition', 'no_approver_action', 'no_approver_fallback_position',
            'branch_condition', 'branch_next_step_code_if_true', 'branch_next_step_code_if_false',
            'require_remarks', 'editable_field_codes', 'sla_due_in_hours', 'sla_business_hours_only',
            'sla_reminder_hours', 'sla_escalation_after_hours', 'sla_escalation_resolver',
            'sla_escalation_resolver_params', 'sla_timeout_action',
        ]


class WorkflowDefinitionSerializer(serializers.ModelSerializer):
    steps = WorkflowStepSerializer(many=True, read_only=True)

    class Meta:
        model = WorkflowDefinition
        fields = [
            'id', 'code', 'name', 'entity', 'trigger', 'trigger_fields', 'entry_condition', 'priority',
            'legal_entity', 'status', 'version', 'effective_from', 'status_field_code', 'status_mapping', 'steps',
        ]
        read_only_fields = ['status', 'version']


class WorkflowApproverOverrideSerializer(serializers.ModelSerializer):
    class Meta:
        model = WorkflowApproverOverride
        fields = ['id', 'employee', 'definition', 'step_code', 'user', 'effective_from', 'effective_to']


class DelegationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Delegation
        fields = ['id', 'from_user', 'to_user', 'scope_entities', 'start', 'end', 'reason', 'apply_to_already_open_tasks']


class WorkflowTaskSerializer(serializers.ModelSerializer):
    step_label = serializers.CharField(source='step.label', read_only=True)
    entity_code = serializers.CharField(source='instance.definition.entity.code', read_only=True)

    class Meta:
        model = WorkflowTask
        fields = [
            'id', 'instance', 'step', 'step_label', 'entity_code', 'assignee', 'original_assignee',
            'status', 'due_at', 'escalation_level', 'acted_at', 'action', 'remarks',
        ]


class WorkflowHistorySerializer(serializers.ModelSerializer):
    class Meta:
        model = WorkflowHistory
        fields = ['id', 'instance', 'task', 'action', 'actor', 'remarks', 'occurred_at']


class WorkflowInstanceSerializer(serializers.ModelSerializer):
    history = WorkflowHistorySerializer(many=True, read_only=True)
    tasks = WorkflowTaskSerializer(many=True, read_only=True)

    class Meta:
        model = WorkflowInstance
        fields = [
            'id', 'definition', 'definition_version', 'content_type', 'object_id', 'requester',
            'status', 'current_step_codes', 'legal_entity', 'started_at', 'completed_at', 'history', 'tasks',
        ]


class EventTypeSerializer(serializers.ModelSerializer):
    class Meta:
        model = EventType
        fields = ['id', 'code', 'entity', 'module', 'description', 'payload_schema', 'is_system']


class MessageTemplateSerializer(serializers.ModelSerializer):
    class Meta:
        model = MessageTemplate
        fields = ['id', 'code', 'event_type', 'channel', 'language', 'subject', 'body', 'allowed_sensitive_vars', 'status', 'version', 'is_system']


class NotificationRuleSerializer(serializers.ModelSerializer):
    class Meta:
        model = NotificationRule
        fields = [
            'id', 'event_type', 'code', 'condition', 'channels', 'recipient_type', 'recipient_params',
            'delay_minutes', 'digest', 'digest_time', 'quiet_hours_start', 'quiet_hours_end',
            'is_mandatory', 'legal_entity', 'is_active',
        ]


class NotificationDeliverySerializer(serializers.ModelSerializer):
    class Meta:
        model = NotificationDelivery
        fields = ['id', 'rule', 'recipient', 'channel', 'status', 'attempts', 'provider_response_code', 'error', 'sent_at', 'created_at']


class UserNotificationPreferenceSerializer(serializers.ModelSerializer):
    class Meta:
        model = UserNotificationPreference
        fields = ['id', 'user', 'event_category_or_type', 'channel', 'enabled']


class JobTypeSerializer(serializers.ModelSerializer):
    class Meta:
        model = JobType
        fields = ['id', 'code', 'name', 'description', 'task_path', 'parameter_schema', 'safe_to_run_concurrently', 'default_schedule', 'is_system']


class ScheduledJobSerializer(serializers.ModelSerializer):
    class Meta:
        model = ScheduledJob
        fields = [
            'id', 'job_type', 'name', 'schedule_type', 'cron_expression', 'interval_seconds', 'timezone',
            'parameters', 'legal_entity', 'enabled', 'last_run_at', 'next_run_at', 'is_running',
        ]
        read_only_fields = ['last_run_at', 'is_running']


class JobRunSerializer(serializers.ModelSerializer):
    class Meta:
        model = JobRun
        fields = ['id', 'scheduled_job', 'started_at', 'ended_at', 'status', 'triggered_by', 'triggered_by_user', 'result_counts', 'error_summary']
