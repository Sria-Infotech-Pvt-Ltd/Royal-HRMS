from __future__ import annotations

from django.conf import settings
from django.db import models


class Announcement(models.Model):
    CATEGORY_GENERAL     = 'general'
    CATEGORY_POLICY      = 'policy'
    CATEGORY_EVENT       = 'event'
    CATEGORY_CELEBRATION = 'celebration'
    CATEGORY_CHOICES = [
        (CATEGORY_GENERAL,     'General'),
        (CATEGORY_POLICY,      'Policy'),
        (CATEGORY_EVENT,       'Event'),
        (CATEGORY_CELEBRATION, 'Celebration'),
    ]

    VISIBILITY_ALL        = 'all'
    VISIBILITY_DEPARTMENT = 'department'
    VISIBILITY_BRANCH     = 'branch'
    VISIBILITY_CHOICES = [
        (VISIBILITY_ALL,        'All Employees'),
        (VISIBILITY_DEPARTMENT, 'By Department'),
        (VISIBILITY_BRANCH,     'By Branch'),
    ]

    title             = models.CharField(max_length=300)
    body              = models.TextField()
    category          = models.CharField(max_length=20, choices=CATEGORY_CHOICES)
    visibility        = models.CharField(max_length=20, choices=VISIBILITY_CHOICES, default=VISIBILITY_ALL)
    target_department = models.ForeignKey(
                            'accounts.Department',
                            on_delete=models.SET_NULL,
                            null=True, blank=True,
                            related_name='announcements',
                        )
    target_branch     = models.ForeignKey(
                            'branch.Branch',
                            on_delete=models.SET_NULL,
                            null=True, blank=True,
                            related_name='announcements',
                        )
    is_pinned         = models.BooleanField(default=False)
    send_email        = models.BooleanField(default=False)
    posted_by         = models.ForeignKey(
                            settings.AUTH_USER_MODEL,
                            on_delete=models.SET_NULL,
                            null=True, blank=True,
                            related_name='announcements',
                        )
    views_count       = models.PositiveIntegerField(default=0)
    created_at        = models.DateTimeField(auto_now_add=True)
    updated_at        = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'hrms_announcements'
        ordering = ['-is_pinned', '-created_at']
        indexes = [
            # Phase 4: every list request sorts by this exact pair
            # (views.py's explicit .order_by('-is_pinned','-created_at')) —
            # neither column is indexed today, so the whole table is sorted
            # on every request as it grows.
            models.Index(fields=['is_pinned', 'created_at'], name='ann_pinned_created_idx'),
        ]

    def __str__(self) -> str:
        return self.title


class AnnouncementReaction(models.Model):
    announcement = models.ForeignKey(
                       Announcement,
                       on_delete=models.CASCADE,
                       related_name='reactions',
                   )
    user         = models.ForeignKey(
                       settings.AUTH_USER_MODEL,
                       on_delete=models.CASCADE,
                       related_name='announcement_reactions',
                   )
    created_at   = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table        = 'hrms_announcement_reactions'
        unique_together = ('announcement', 'user')

    def __str__(self) -> str:
        return f'{self.user_id} → {self.announcement_id}'
