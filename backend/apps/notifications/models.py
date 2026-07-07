import uuid

from django.db import models


NOTIFICATION_TYPE_CHOICES = [
    ('leave_applied',          'Leave Applied'),
    ('leave_manager_approved', 'Leave Approved by Manager'),
    ('leave_manager_rejected', 'Leave Rejected by Manager'),
    ('leave_hr_approved',      'Leave Approved by HR'),
    ('leave_hr_rejected',      'Leave Rejected by HR'),
    ('leave_cancelled',        'Leave Cancelled'),
    ('attendance',             'Attendance'),
    ('regularization',         'Regularization'),
    ('permission',             'Permission'),
    ('holiday',                'Holiday'),
    ('announcement',           'Announcement'),
]

MODULE_CHOICES = [
    ('leave',          'Leave'),
    ('attendance',     'Attendance'),
    ('regularization', 'Regularization'),
    ('permission',     'Permission'),
    ('holiday',        'Holiday'),
    ('announcement',   'Announcement'),
]


class Notification(models.Model):
    id                = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user              = models.ForeignKey(
        'accounts.User', on_delete=models.CASCADE, related_name='notifications',
    )
    title             = models.CharField(max_length=255)
    message           = models.TextField()
    notification_type = models.CharField(max_length=50, choices=NOTIFICATION_TYPE_CHOICES, db_index=True)
    module            = models.CharField(max_length=50, choices=MODULE_CHOICES, db_index=True)
    reference_id      = models.CharField(max_length=100, blank=True, default='')
    is_read           = models.BooleanField(default=False, db_index=True)
    created_by        = models.ForeignKey(
        'accounts.User', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='created_notifications',
    )
    created_at        = models.DateTimeField(auto_now_add=True)
    updated_at        = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'notifications'
        ordering = ['-created_at']

    def __str__(self) -> str:
        return f'{self.title} → {self.user_id}'
