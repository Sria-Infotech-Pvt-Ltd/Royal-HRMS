import uuid
import logging

from django.conf import settings
from django.db import models

logger = logging.getLogger(__name__)


class AssessmentSettings(models.Model):
   
    default_pass_percentage = models.PositiveSmallIntegerField(default=70)
    max_attempts            = models.PositiveSmallIntegerField(default=3)
    time_limit_mins         = models.PositiveSmallIntegerField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'assessments_settings'

    def __str__(self) -> str:
        return 'Assessment Settings'

    @classmethod
    def load(cls) -> 'AssessmentSettings':
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj


class Assessment(models.Model):
    id          = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    title       = models.CharField(max_length=200)
    description = models.TextField(blank=True, default='')
    is_active       = models.BooleanField(default=True, db_index=True)
    is_default      = models.BooleanField(default=False)
    pass_percentage = models.PositiveSmallIntegerField(default=70)
    # null = inherit from AssessmentSettings; 0 = unlimited (per-assessment override)
    max_attempts    = models.PositiveSmallIntegerField(null=True, blank=True)
    # null = inherit from AssessmentSettings (which may also be null = no limit)
    time_limit_mins = models.PositiveSmallIntegerField(null=True, blank=True)
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

    def effective_max_attempts(self, global_settings: 'AssessmentSettings') -> int:
        if self.max_attempts is not None:
            return self.max_attempts
        return global_settings.max_attempts

    def effective_time_limit_mins(self, global_settings: 'AssessmentSettings'):
        if self.time_limit_mins is not None:
            return self.time_limit_mins
        return global_settings.time_limit_mins

    def compute_max_score(self) -> int:
       
        sections = list(self.sections.all())
        quiz_items = list(
            self.items.filter(item_type='quiz').values('id', 'section_id')
        )
        if not sections:
            return len(quiz_items)
        section_map = {s.id: s.score for s in sections}
        section_ids_with_quiz = {
            item['section_id'] for item in quiz_items if item['section_id']
        }
        sectioned   = sum(section_map[sid] for sid in section_ids_with_quiz if sid in section_map)
        unsectioned = sum(1 for item in quiz_items if item['section_id'] is None)
        return sectioned + unsectioned


class AssessmentSection(models.Model):
    
    id         = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    assessment = models.ForeignKey(
        Assessment,
        on_delete=models.CASCADE,
        related_name='sections',
    )
    title      = models.CharField(max_length=200)
    order      = models.PositiveIntegerField(default=0, db_index=True)
    score      = models.PositiveSmallIntegerField(default=10)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'assessments_section'
        ordering = ['order']

    def __str__(self) -> str:
        return f'{self.title} — {self.assessment.title}'


class AssessmentItem(models.Model):
    TYPE_VIDEO   = 'video'
    TYPE_QUIZ    = 'quiz'
    TYPE_CHOICES = [
        (TYPE_VIDEO, 'Video'),
        (TYPE_QUIZ,  'Quiz / MCQ'),
    ]

    id         = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    assessment = models.ForeignKey(
        Assessment,
        on_delete=models.CASCADE,
        related_name='items',
    )
    section    = models.ForeignKey(
        AssessmentSection,
        on_delete=models.SET_NULL,
        null=True, blank=True,
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

    id        = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    candidate = models.ForeignKey(
        'recruitment.Candidate',
        on_delete=models.CASCADE,
        related_name='assessment_assignments',
        null=True, blank=True,
    )
    employee  = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='employee_assessment_assignments',
        null=True, blank=True,
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
    started_at    = models.DateTimeField(null=True, blank=True)
    deadline      = models.DateTimeField(null=True, blank=True)
    completed_at  = models.DateTimeField(null=True, blank=True)
    created_at    = models.DateTimeField(auto_now_add=True)
    updated_at    = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'assessments_candidate_assignment'
        ordering = ['-created_at']
        constraints = [
            models.UniqueConstraint(
                fields=['candidate', 'assessment'],
                condition=models.Q(candidate__isnull=False),
                name='unique_candidate_assessment',
            ),
            models.UniqueConstraint(
                fields=['employee', 'assessment'],
                condition=models.Q(employee__isnull=False),
                name='unique_employee_assessment',
            ),
        ]

    def __str__(self) -> str:
        if self.candidate_id:
            name = self.candidate.name if self.candidate else str(self.candidate_id)
        elif self.employee_id:
            name = self.employee.email if self.employee else str(self.employee_id)
        else:
            name = 'Unknown'
        return f'{name} — {self.assessment.title}'


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
        a = self.assignment
        if a.candidate_id:
            name = a.candidate.name if a.candidate else str(a.candidate_id)
        elif a.employee_id:
            name = a.employee.email if a.employee else str(a.employee_id)
        else:
            name = 'Unknown'
        return f'{name} — {self.item.title}'
