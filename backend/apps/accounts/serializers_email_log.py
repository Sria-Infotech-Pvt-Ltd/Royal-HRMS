"""
Serializers for the system-wide EmailLog — see apps.accounts.views_email_log.
Deliberately its own file, not serializers.py (already far past the 300-line
convention) — mirrors the split pattern used for serializers_profile_photo.py.
"""
from __future__ import annotations

from rest_framework import serializers

from apps.accounts.models import EmailLog


class EmailLogSerializer(serializers.ModelSerializer):
    triggered_by_name  = serializers.SerializerMethodField()
    smtp_settings_name = serializers.SerializerMethodField()

    class Meta:
        model  = EmailLog
        fields = [
            'id', 'recipient_email', 'subject', 'status', 'module',
            'template_name', 'triggered_by_name', 'smtp_settings_name',
            'is_resend', 'resend_of', 'had_attachments', 'attachment_filenames',
            'has_sensitive_context', 'error_message', 'created_at',
        ]

    def get_triggered_by_name(self, obj) -> str:
        if obj.triggered_by:
            return obj.triggered_by.full_name or obj.triggered_by.email
        return 'System'

    def get_smtp_settings_name(self, obj) -> str:
        return obj.smtp_settings.name if obj.smtp_settings else ''


class EmailLogDetailSerializer(EmailLogSerializer):
    class Meta(EmailLogSerializer.Meta):
        fields = EmailLogSerializer.Meta.fields + ['body_html', 'context']
