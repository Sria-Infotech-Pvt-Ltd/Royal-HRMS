"""
Phase 3B Task F — generalised messaging. `MessageTemplate` generalises
`notifications`/`accounts`' existing `EmailTemplate` WITHOUT replacing it
— `EmailTemplate` keeps working untouched (Rule: do not remove it).
"""
from __future__ import annotations

from django.conf import settings
from django.core.serializers.json import DjangoJSONEncoder
from django.db import models

from .events import EventType
from .phase1 import LegalEntity, TimestampedModel


class MessageTemplate(TimestampedModel):
    CHANNEL_EMAIL = 'email'
    CHANNEL_IN_APP = 'in_app'
    CHANNEL_WEBHOOK = 'webhook'
    CHANNEL_SMS = 'sms'
    CHANNEL_WHATSAPP = 'whatsapp'
    CHANNEL_PUSH = 'push'
    CHANNEL_CHOICES = [
        (CHANNEL_EMAIL, 'Email'), (CHANNEL_IN_APP, 'In-app'), (CHANNEL_WEBHOOK, 'Webhook'),
        (CHANNEL_SMS, 'SMS (not implemented)'), (CHANNEL_WHATSAPP, 'WhatsApp (not implemented)'),
        (CHANNEL_PUSH, 'Push (not implemented)'),
    ]
    STATUS_DRAFT = 'draft'
    STATUS_PUBLISHED = 'published'
    STATUS_CHOICES = [(STATUS_DRAFT, 'Draft'), (STATUS_PUBLISHED, 'Published')]

    code = models.CharField(max_length=100)
    event_type = models.ForeignKey(EventType, on_delete=models.CASCADE, related_name='message_templates')
    channel = models.CharField(max_length=20, choices=CHANNEL_CHOICES, default=CHANNEL_IN_APP)
    language = models.CharField(max_length=10, default='en')

    # Plain {{token}} substitution only — see services_notifications.py's
    # render() docstring for why this is NOT Jinja2/Django templates.
    subject = models.CharField(max_length=255, blank=True)
    body = models.TextField(blank=True)

    allowed_sensitive_vars = models.JSONField(default=list, blank=True, help_text='Variable names this template is explicitly allowed to render despite being marked sensitive in the event payload_schema.')

    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_DRAFT)
    version = models.PositiveIntegerField(default=1)
    is_system = models.BooleanField(default=False)

    class Meta:
        db_table = 'platform_message_templates'
        ordering = ['event_type', 'channel', 'language']
        constraints = [
            models.UniqueConstraint(fields=['event_type', 'channel', 'language'], name='uniq_template_per_event_channel_lang'),
        ]

    def __str__(self):
        return f'{self.event_type_id}:{self.channel}:{self.language}'


class NotificationRule(TimestampedModel):
    event_type = models.ForeignKey(EventType, on_delete=models.CASCADE, related_name='notification_rules')
    code = models.CharField(max_length=100, unique=True)
    condition = models.JSONField(default=dict, blank=True)
    channels = models.JSONField(default=list, blank=True, help_text='["email", "in_app"]')

    RECIPIENT_EMPLOYEE = 'record_employee'
    RECIPIENT_REQUESTER = 'requester'
    RECIPIENT_RESOLVER = 'resolver'
    RECIPIENT_LOOKUP_LIST = 'lookup_distribution_list'
    RECIPIENT_FIXED_EMAILS = 'fixed_emails'
    RECIPIENT_CHOICES = [
        (RECIPIENT_EMPLOYEE, "The record's employee"), (RECIPIENT_REQUESTER, 'The requester'),
        (RECIPIENT_RESOLVER, 'An approver-style resolver'), (RECIPIENT_LOOKUP_LIST, 'A lookup-defined distribution list'),
        (RECIPIENT_FIXED_EMAILS, 'Fixed emails (admin only)'),
    ]
    recipient_type = models.CharField(max_length=30, choices=RECIPIENT_CHOICES, default=RECIPIENT_EMPLOYEE)
    recipient_params = models.JSONField(default=dict, blank=True, encoder=DjangoJSONEncoder)

    delay_minutes = models.PositiveIntegerField(default=0)
    DIGEST_IMMEDIATE = 'immediate'
    DIGEST_DAILY = 'daily'
    DIGEST_CHOICES = [(DIGEST_IMMEDIATE, 'Immediate'), (DIGEST_DAILY, 'Daily digest')]
    digest = models.CharField(max_length=20, choices=DIGEST_CHOICES, default=DIGEST_IMMEDIATE)
    digest_time = models.TimeField(null=True, blank=True)
    quiet_hours_start = models.TimeField(null=True, blank=True)
    quiet_hours_end = models.TimeField(null=True, blank=True)

    is_mandatory = models.BooleanField(default=False)
    legal_entity = models.ForeignKey(LegalEntity, on_delete=models.SET_NULL, null=True, blank=True, related_name='+')
    is_active = models.BooleanField(default=True)

    class Meta:
        db_table = 'platform_notification_rules'
        ordering = ['event_type', 'code']

    def __str__(self):
        return self.code


class NotificationDelivery(models.Model):
    STATUS_PENDING = 'pending'
    STATUS_SENT = 'sent'
    STATUS_FAILED = 'failed'
    STATUS_SKIPPED_MUTED = 'skipped_muted'
    STATUS_SKIPPED_QUIET_HOURS = 'skipped_quiet_hours'
    STATUS_CHOICES = [
        (STATUS_PENDING, 'Pending'), (STATUS_SENT, 'Sent'), (STATUS_FAILED, 'Failed'),
        (STATUS_SKIPPED_MUTED, 'Skipped (muted)'), (STATUS_SKIPPED_QUIET_HOURS, 'Skipped (quiet hours)'),
    ]

    rule = models.ForeignKey(NotificationRule, on_delete=models.CASCADE, related_name='deliveries')
    recipient = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='+')
    channel = models.CharField(max_length=20)
    # Dedup key: (rule, event id, recipient, channel) — Task F.3.
    dedup_key = models.CharField(max_length=200, db_index=True)

    status = models.CharField(max_length=30, choices=STATUS_CHOICES, default=STATUS_PENDING)
    attempts = models.PositiveSmallIntegerField(default=0)
    provider_response_code = models.CharField(max_length=20, blank=True)
    error = models.TextField(blank=True, help_text='Never the message body itself if it contains sensitive data.')
    sent_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'platform_notification_deliveries'
        ordering = ['-created_at']
        constraints = [
            models.UniqueConstraint(fields=['dedup_key'], name='uniq_notification_delivery_dedup_key'),
        ]

    def __str__(self):
        return f'{self.rule_id} -> {self.recipient_id} ({self.channel}, {self.status})'


class UserNotificationPreference(models.Model):
    """Task F.4 — replaces the hardcoded NotificationSettings booleans.
    `event_category` is the EventType's `module` (coarse opt-out, e.g.
    mute all of "hrms") OR a specific EventType code (fine-grained) —
    whichever the user/admin configured; `is_mandatory` rules on
    NotificationRule always ignore this table entirely."""
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='notification_preferences')
    event_category_or_type = models.CharField(max_length=100, help_text='An EventType.module value, or a specific EventType.code.')
    channel = models.CharField(max_length=20)
    enabled = models.BooleanField(default=True)

    class Meta:
        db_table = 'platform_user_notification_preferences'
        constraints = [
            models.UniqueConstraint(fields=['user', 'event_category_or_type', 'channel'], name='uniq_user_notification_preference'),
        ]

    def __str__(self):
        return f'{self.user_id}:{self.event_category_or_type}:{self.channel} = {self.enabled}'
