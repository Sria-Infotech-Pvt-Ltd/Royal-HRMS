from rest_framework import serializers

from .models import Notification, NotificationSettings


class NotificationSerializer(serializers.ModelSerializer):
    class Meta:
        model  = Notification
        fields = [
            'id', 'title', 'message', 'notification_type',
            'module', 'reference_id', 'is_read', 'created_at',
        ]


class NotificationSettingsSerializer(serializers.ModelSerializer):
    class Meta:
        model  = NotificationSettings
        fields = [
            'is_leave_enabled', 'is_expense_enabled', 'is_separation_enabled',
            'is_payroll_enabled', 'is_approval_enabled', 'is_document_enabled',
            'is_attendance_enabled', 'is_system_enabled', 'updated_at',
        ]
        read_only_fields = ['updated_at']
