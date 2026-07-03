import uuid
import logging

from django.conf import settings
from django.db import models

logger = logging.getLogger(__name__)


class Assessment(models.Model):
    id          = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    title       = models.CharField(max_length=200)
    description = models.TextField(blank=True, default='')
    is_active   = models.BooleanField(default=True, db_index=True)
    is_default  = models.BooleanField(default=False)
    created_by  = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='created_assessments',
    )
    created_at  = models.DateTimeField(auto_now_add=True)
    updated_at  = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'assessments_assessment'
        ordering = ['-created_at']

    def __str__(self) -> str:
        return self.title


class AssessmentItem(models.Model):
    TYPE_VIDEO   = 'video'
    TYPE_QUIZ    = 'quiz'
    TYPE_CHOICES = [
        (TYPE_VIDEO, 'Video'),
        (TYPE_QUIZ,  'Quiz / MCQ'),
    ]

    id          = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    assessment  = models.ForeignKey(
        Assessment,
        on_delete=models.CASCADE,
        related_name='items',
    )
    item_type      = models.CharField(max_length=10, choices=TYPE_CHOICES)
    title          = models.CharField(max_length=200)
    order          = models.PositiveIntegerField(default=0, db_index=True)

    # Video fields
    video_url     = models.URLField(blank=True, default='')
    duration_secs = models.PositiveIntegerField(null=True, blank=True)

    # Quiz fields
    question       = models.TextField(blank=True, default='')
    option_a       = models.CharField(max_length=500, blank=True, default='')
    option_b       = models.CharField(max_length=500, blank=True, default='')
    option_c       = models.CharField(max_length=500, blank=True, default='')
    option_d       = models.CharField(max_length=500, blank=True, default='')
    correct_option = models.CharField(max_length=1, blank=True, default='')
    pass_score     = models.PositiveSmallIntegerField(default=1)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'assessments_item'
        ordering = ['order']

    def __str__(self) -> str:
        return f'[{self.get_item_type_display()}] {self.title}'


class CandidateAssignment(models.Model):
    STATUS_PENDING     = 'pending'
    STATUS_IN_PROGRESS = 'in_progress'
    STATUS_COMPLETE    = 'complete'
    STATUS_CHOICES     = [
        (STATUS_PENDING,     'Pending'),
        (STATUS_IN_PROGRESS, 'In Progress'),
        (STATUS_COMPLETE,    'Complete'),
    ]

    id          = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    candidate   = models.ForeignKey(
        'recruitment.Candidate',
        on_delete=models.CASCADE,
        related_name='assessment_assignments',
    )
    assessment  = models.ForeignKey(
        Assessment,
        on_delete=models.CASCADE,
        related_name='assignments',
    )
    assigned_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='assessment_assignments_made',
    )
    status        = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_PENDING, db_index=True)
    score         = models.PositiveSmallIntegerField(default=0)
    max_score     = models.PositiveSmallIntegerField(default=0)
    attempt_count = models.PositiveSmallIntegerField(default=1)
    completed_at  = models.DateTimeField(null=True, blank=True)
    created_at    = models.DateTimeField(auto_now_add=True)
    updated_at    = models.DateTimeField(auto_now=True)

    class Meta:
        db_table        = 'assessments_candidate_assignment'
        unique_together = ('candidate', 'assessment')
        ordering        = ['-created_at']

    def __str__(self) -> str:
        return f'{self.candidate.name} — {self.assessment.title}'


class CandidateResponse(models.Model):
    id              = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    assignment      = models.ForeignKey(
        CandidateAssignment,
        on_delete=models.CASCADE,
        related_name='responses',
    )
    item            = models.ForeignKey(
        AssessmentItem,
        on_delete=models.CASCADE,
        related_name='responses',
    )
    is_watched      = models.BooleanField(default=False)
    selected_option = models.CharField(max_length=1, blank=True, default='')
    is_correct      = models.BooleanField(null=True, blank=True)
    score_awarded   = models.PositiveSmallIntegerField(default=0)
    responded_at    = models.DateTimeField(null=True, blank=True)
    created_at      = models.DateTimeField(auto_now_add=True)
    updated_at      = models.DateTimeField(auto_now=True)

    class Meta:
        db_table        = 'assessments_candidate_response'
        unique_together = ('assignment', 'item')

    def __str__(self) -> str:
        return f'{self.assignment.candidate.name} — {self.item.title}'
