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
    ('birthday',               'Birthday'),
    ('promotion',              'Promotion'),
]

MODULE_CHOICES = [
    ('leave',          'Leave'),
    ('attendance',     'Attendance'),
    ('regularization', 'Regularization'),
    ('permission',     'Permission'),
    ('holiday',        'Holiday'),
    ('announcement',   'Announcement'),
    ('birthday',       'Birthday'),
    ('promotion',      'Promotion'),
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
        indexes = [
            # Phase 4: (user, is_read) is the single highest-traffic query in
            # this table — the unread-count bell-poll (called every 60s per
            # active user), the notification list, and mark-all-read all
            # filter on exactly this pair. Today `user` (FK auto-index) and
            # `is_read` (standalone) are separate indexes, requiring an
            # intersection instead of one covering index.
            models.Index(fields=['user', 'is_read'], name='notif_user_read_idx'),
            # Phase 4: the paginated notification list is always scoped to
            # one user and ordered by created_at — no index currently backs
            # that combination.
            models.Index(fields=['user', 'created_at'], name='notif_user_created_idx'),
        ]

    def __str__(self) -> str:
        return f'{self.title} → {self.user_id}'
