"""
Training & Learning (module key 'training').

TrainingCourse        what HR builds: details, materials, optional linked assessment,
                      optional automatic assignment to new joiners
TrainingMaterial      ordered content: uploaded video, document, or external video link
TrainingAssignment    one course for one employee (unique) — the training history row
TrainingMaterialProgress   per material per assignment: opened / watched / completed
TrainingAssessmentAttempt  each attempt at the course's linked assessment. The questions,
                      answers, sections, pass mark, attempt limit and scoring all come from
                      apps.assessments (no second MCQ engine); attempts are kept here so a
                      training test never touches the onboarding assessment gate
                      (CandidateAssignment / User.assessment_status).
"""
import uuid

from django.conf import settings
from django.db import models
from django.utils import timezone

from core.storage import AuthenticatedRawMediaCloudinaryStorage

from apps.training.storage import (
    AuthenticatedVideoCloudinaryStorage, training_document_upload_path, training_thumbnail_upload_path,
    training_video_upload_path,
)


class TrainingCourse(models.Model):
    id          = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    title       = models.CharField(max_length=200)
    description = models.TextField(blank=True, default='')
    category    = models.CharField(max_length=100, blank=True, default='')
    owner       = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
                                    related_name='training_courses_owned')
    trainer_name = models.CharField(max_length=150, blank=True, default='')   # external trainer, when no owner
    thumbnail   = models.FileField(upload_to=training_thumbnail_upload_path,
                                   storage=AuthenticatedRawMediaCloudinaryStorage(), null=True, blank=True)
    duration_minutes = models.PositiveIntegerField(null=True, blank=True)
    is_mandatory = models.BooleanField(default=False)
    is_active    = models.BooleanField(default=True, db_index=True)
    start_date   = models.DateField(null=True, blank=True)
    deadline     = models.DateField(null=True, blank=True)       # default due date for new assignments
    assessment   = models.ForeignKey('assessments.Assessment', on_delete=models.SET_NULL, null=True, blank=True,
                                     related_name='training_courses')
    # Videos don't block the assessment: employees may go straight to it and complete the
    # course by passing it (requires a linked assessment). Documents marked required still count.
    videos_optional = models.BooleanField(default=False)

    # Automatic assignment to employees whose onboarding completes from now on.
    auto_assign_new_joiners  = models.BooleanField(default=False)
    new_joiner_deadline_days = models.PositiveSmallIntegerField(default=30)
    new_joiner_branches      = models.JSONField(default=list, blank=True)      # empty = every branch
    new_joiner_departments   = models.JSONField(default=list, blank=True)      # empty = every department

    archived_at = models.DateTimeField(null=True, blank=True)
    created_by  = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
                                    related_name='training_courses_created')
    created_at  = models.DateTimeField(auto_now_add=True)
    updated_at  = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'training_courses'
        ordering = ['-created_at']

    def __str__(self) -> str:
        return self.title


class TrainingMaterial(models.Model):
    TYPE_VIDEO          = 'video'            # uploaded, private
    TYPE_DOCUMENT       = 'document'         # uploaded PDF / PowerPoint / Word
    TYPE_EXTERNAL_VIDEO = 'external_video'   # public link (YouTube, Vimeo, direct .mp4/.webm)
    TYPE_CHOICES = [(TYPE_VIDEO, 'Video'), (TYPE_DOCUMENT, 'Document'), (TYPE_EXTERNAL_VIDEO, 'External video')]

    PROVIDER_YOUTUBE = 'youtube'
    PROVIDER_VIMEO   = 'vimeo'
    PROVIDER_DIRECT  = 'direct'
    PROVIDER_CHOICES = [(PROVIDER_YOUTUBE, 'YouTube'), (PROVIDER_VIMEO, 'Vimeo'), (PROVIDER_DIRECT, 'Direct video file')]

    id            = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    course        = models.ForeignKey(TrainingCourse, on_delete=models.CASCADE, related_name='materials')
    title         = models.CharField(max_length=200)
    description   = models.TextField(blank=True, default='')
    material_type = models.CharField(max_length=20, choices=TYPE_CHOICES)
    order         = models.PositiveIntegerField(default=0, db_index=True)
    is_required   = models.BooleanField(default=True)

    document_file = models.FileField(upload_to=training_document_upload_path, max_length=255,
                                     storage=AuthenticatedRawMediaCloudinaryStorage(), null=True, blank=True)
    video_file    = models.FileField(upload_to=training_video_upload_path, max_length=255,
                                     storage=AuthenticatedVideoCloudinaryStorage(), null=True, blank=True)
    file_format   = models.CharField(max_length=10, blank=True, default='')    # pdf, pptx, docx, mp4, webm
    file_size     = models.PositiveBigIntegerField(default=0)
    original_name = models.CharField(max_length=255, blank=True, default='')

    external_url  = models.URLField(max_length=1000, blank=True, default='')
    provider      = models.CharField(max_length=10, choices=PROVIDER_CHOICES, blank=True, default='')
    embed_id      = models.CharField(max_length=100, blank=True, default='')

    duration_seconds = models.PositiveIntegerField(null=True, blank=True)    # videos; set by HR or first playback
    # Documents: the employee confirms reading, no sooner than this after opening it.
    min_view_seconds = models.PositiveIntegerField(default=0)
    # Videos whose playback can't be tracked (e.g. Vimeo): HR allows "I have watched this".
    allow_manual_completion = models.BooleanField(default=False)

    is_archived = models.BooleanField(default=False)   # removed from the course, history kept
    created_at  = models.DateTimeField(auto_now_add=True)
    updated_at  = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'training_materials'
        ordering = ['order', 'created_at']

    def __str__(self) -> str:
        return self.title

    @property
    def is_tracked(self) -> bool:
        """Playback progress is reported reliably (uploaded, YouTube, direct files)."""
        if self.material_type == self.TYPE_VIDEO:
            return True
        return self.material_type == self.TYPE_EXTERNAL_VIDEO and self.provider in (
            self.PROVIDER_YOUTUBE, self.PROVIDER_DIRECT)


class TrainingAssignment(models.Model):
    STATUS_ASSIGNED    = 'assigned'
    STATUS_IN_PROGRESS = 'in_progress'
    STATUS_COMPLETED   = 'completed'
    STATUS_FAILED      = 'failed'          # assessment attempts used up without passing
    STATUS_CHOICES = [(STATUS_ASSIGNED, 'Assigned'), (STATUS_IN_PROGRESS, 'In Progress'),
                      (STATUS_COMPLETED, 'Completed'), (STATUS_FAILED, 'Failed Assessment')]
    # "Overdue" is not stored: assigned / in progress with the due date passed.

    SOURCE_INDIVIDUAL = 'individual'
    SOURCE_DEPARTMENT = 'department'
    SOURCE_BRANCH     = 'branch'
    SOURCE_ALL        = 'all'
    SOURCE_ONBOARDING = 'onboarding'
    SOURCE_CHOICES = [(SOURCE_INDIVIDUAL, 'Selected employees'), (SOURCE_DEPARTMENT, 'Department'),
                      (SOURCE_BRANCH, 'Branch'), (SOURCE_ALL, 'All employees'), (SOURCE_ONBOARDING, 'New joiner')]

    id          = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    course      = models.ForeignKey(TrainingCourse, on_delete=models.CASCADE, related_name='assignments')
    employee    = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
                                    related_name='training_assignments')
    assigned_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
                                    related_name='training_assignments_made')
    source      = models.CharField(max_length=12, choices=SOURCE_CHOICES, default=SOURCE_INDIVIDUAL)
    due_date    = models.DateField(null=True, blank=True)
    status      = models.CharField(max_length=12, choices=STATUS_CHOICES, default=STATUS_ASSIGNED, db_index=True)
    started_at   = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    attempts_used      = models.PositiveSmallIntegerField(default=0)
    best_score_percent = models.PositiveSmallIntegerField(null=True, blank=True)
    assessment_passed  = models.BooleanField(null=True, blank=True)
    deadline_reminder_sent_at = models.DateTimeField(null=True, blank=True)
    overdue_notified_at       = models.DateTimeField(null=True, blank=True)
    created_at  = models.DateTimeField(auto_now_add=True)
    updated_at  = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'training_assignments'
        ordering = ['-created_at']
        constraints = [models.UniqueConstraint(fields=['course', 'employee'], name='uniq_training_course_employee')]
        indexes = [models.Index(fields=['employee', 'status'], name='training_assign_emp_status')]

    @property
    def is_overdue(self) -> bool:
        return (self.status in (self.STATUS_ASSIGNED, self.STATUS_IN_PROGRESS) and self.due_date is not None
                and self.due_date < timezone.localdate())

    @property
    def display_status(self) -> str:
        return 'overdue' if self.is_overdue else self.status


class TrainingMaterialProgress(models.Model):
    METHOD_TRACKED   = 'tracked'      # playback reached the required share of the video
    METHOD_READ      = 'read'         # document opened and confirmed after the minimum time
    METHOD_CONFIRMED = 'confirmed'    # untracked video, employee confirmed (HR allowed it)
    METHOD_CHOICES = [(METHOD_TRACKED, 'Watched'), (METHOD_READ, 'Read'), (METHOD_CONFIRMED, 'Confirmed')]

    id         = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    assignment = models.ForeignKey(TrainingAssignment, on_delete=models.CASCADE, related_name='material_progress')
    material   = models.ForeignKey(TrainingMaterial, on_delete=models.CASCADE, related_name='progress')
    opened_at  = models.DateTimeField(null=True, blank=True)
    last_position_seconds = models.FloatField(default=0)
    watched_seconds       = models.FloatField(default=0)
    duration_seconds      = models.FloatField(null=True, blank=True)
    last_heartbeat_at     = models.DateTimeField(null=True, blank=True)
    completed_at      = models.DateTimeField(null=True, blank=True)
    completion_method = models.CharField(max_length=10, choices=METHOD_CHOICES, blank=True, default='')
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'training_material_progress'
        constraints = [models.UniqueConstraint(fields=['assignment', 'material'], name='uniq_training_progress')]


class TrainingAssessmentAttempt(models.Model):
    id             = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    assignment     = models.ForeignKey(TrainingAssignment, on_delete=models.CASCADE, related_name='attempts')
    assessment     = models.ForeignKey('assessments.Assessment', on_delete=models.SET_NULL, null=True, blank=True,
                                       related_name='training_attempts')
    attempt_number = models.PositiveSmallIntegerField()
    answers        = models.JSONField(default=dict, blank=True)
    score          = models.PositiveSmallIntegerField(default=0)
    max_score      = models.PositiveSmallIntegerField(default=0)
    percentage     = models.PositiveSmallIntegerField(default=0)
    pass_percentage = models.PositiveSmallIntegerField(default=0)
    passed         = models.BooleanField(null=True, blank=True)        # null until submitted
    started_at     = models.DateTimeField(default=timezone.now)
    submitted_at   = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = 'training_assessment_attempts'
        ordering = ['-started_at']
        constraints = [models.UniqueConstraint(fields=['assignment', 'attempt_number'],
                                               name='uniq_training_attempt_number')]
