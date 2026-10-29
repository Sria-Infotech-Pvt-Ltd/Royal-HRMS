import uuid

from django.conf import settings
from django.db import models


class OnboardingEvent(models.Model):
    """One line of a new hire's onboarding history (invite sent, failed, resent, link opened, first login, ...).

    Kept apart from AuditLog because the Onboarding panel needs a per-employee timeline with a stable set of event types
    and a human-readable failure reason, not a generic who-did-what feed.
    """
    INITIATED = 'initiated'
    EMAIL_SENT = 'email_sent'
    EMAIL_FAILED = 'email_failed'
    EMAIL_RESENT = 'email_resent'
    EMAIL_CORRECTED = 'email_corrected'
    LINK_OPENED = 'link_opened'
    FIRST_LOGIN = 'first_login'
    PASSWORD_SET = 'password_set'
    ACTIVATED = 'activated'
    EVENT_CHOICES = [
        (INITIATED, 'Onboarding initiated'),
        (EMAIL_SENT, 'Onboarding email sent'),
        (EMAIL_FAILED, 'Onboarding email failed'),
        (EMAIL_RESENT, 'Onboarding email resent'),
        (EMAIL_CORRECTED, 'Email address corrected'),
        (LINK_OPENED, 'Invite link opened'),
        (FIRST_LOGIN, 'First login'),
        (PASSWORD_SET, 'Password set'),
        (ACTIVATED, 'Status changed to Active'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    employee = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='onboarding_events')
    event = models.CharField(max_length=20, choices=EVENT_CHOICES)
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='onboarding_events_caused',
    )
    detail = models.CharField(max_length=500, blank=True, default='')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'employee_onboarding_events'
        ordering = ['created_at']
        indexes = [models.Index(fields=['employee', 'event', 'created_at'], name='onb_event_emp_evt_idx')]

    def __str__(self):
        return f'{self.event} for {self.employee_id}'
