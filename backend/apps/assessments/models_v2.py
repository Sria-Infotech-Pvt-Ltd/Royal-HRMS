"""
Phase 8A Task D — learning and assessments: a real question bank (child
rows, not fixed option_a-d columns), courses/sessions/enrolments, and a
mandatory-training policy.

Scoped down, stated plainly:
- Only 3 of the master prompt's 9 question types are modeled with real
  scoring logic this pass (single_choice, multiple_choice, true_false) —
  short/long text, numeric, ordering, matching, and video-watch are listed
  in TYPE_CHOICES for forward-compatibility but have no scoring function
  in services_learning.py yet.
- No manual-grading queue, no proctoring-flag capture, no pools/
  randomisation engine — Question/QuestionOption exist and the EXISTING
  `AssessmentItem` rows migrate into them exactly (Task D.1's own
  requirement), but the assignment/attempt engine itself
  (CandidateAssignment/CandidateResponse) is COMPLETELY UNTOUCHED; nothing
  reads Question/QuestionOption for real scoring yet.
- Certificates: `Enrolment.certificate_issued_at` exists as a field, but
  no actual certificate file is generated (Phase 9 placeholder, same as
  the master prompt's own framing) and no EmployeeCertification row is
  created automatically.
"""
import uuid

from django.db import models


class Question(models.Model):
    TYPE_SINGLE_CHOICE   = 'single_choice'
    TYPE_MULTIPLE_CHOICE = 'multiple_choice'
    TYPE_TRUE_FALSE      = 'true_false'
    TYPE_SHORT_TEXT      = 'short_text'
    TYPE_LONG_TEXT       = 'long_text'
    TYPE_NUMERIC         = 'numeric'
    TYPE_ORDERING        = 'ordering'
    TYPE_MATCHING        = 'matching'
    TYPE_VIDEO_WATCH     = 'video_watch'
    TYPE_CHOICES = [
        (TYPE_SINGLE_CHOICE, 'Single choice'), (TYPE_MULTIPLE_CHOICE, 'Multiple choice'),
        (TYPE_TRUE_FALSE, 'True/False'), (TYPE_SHORT_TEXT, 'Short text (manual grading)'),
        (TYPE_LONG_TEXT, 'Long text (manual grading)'), (TYPE_NUMERIC, 'Numeric'),
        (TYPE_ORDERING, 'Ordering'), (TYPE_MATCHING, 'Matching'), (TYPE_VIDEO_WATCH, 'Video watch'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    question_type = models.CharField(max_length=20, choices=TYPE_CHOICES, default=TYPE_SINGLE_CHOICE)
    text = models.TextField()
    difficulty = models.CharField(max_length=20, blank=True)
    tags = models.JSONField(default=list, blank=True)
    version = models.PositiveSmallIntegerField(default=1)
    # Editing a used question creates a new version row (supersedes_id
    # links forward) rather than mutating history — services_learning.py's
    # new_question_version() enforces this; the model itself allows either.
    supersedes = models.ForeignKey('self', on_delete=models.SET_NULL, null=True, blank=True, related_name='superseded_by')
    legacy_item = models.OneToOneField(
        'assessments.AssessmentItem', on_delete=models.SET_NULL, null=True, blank=True, related_name='question_v2',
    )
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'assessments_questions_v2'
        ordering = ['-created_at']

    def __str__(self):
        return self.text[:60]


class QuestionOption(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    question = models.ForeignKey(Question, on_delete=models.CASCADE, related_name='options')
    text = models.CharField(max_length=500)
    is_correct = models.BooleanField(default=False)
    order = models.PositiveSmallIntegerField(default=0)

    class Meta:
        db_table = 'assessments_question_options_v2'
        ordering = ['question', 'order']

    def __str__(self):
        return self.text


class Course(models.Model):
    TYPE_ELEARNING = 'e_learning'
    TYPE_CLASSROOM = 'classroom'
    TYPE_VIRTUAL   = 'virtual'
    TYPE_BLENDED   = 'blended'
    TYPE_CHOICES = [
        (TYPE_ELEARNING, 'E-learning link'), (TYPE_CLASSROOM, 'Classroom'),
        (TYPE_VIRTUAL, 'Virtual'), (TYPE_BLENDED, 'Blended'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    code = models.CharField(max_length=40, unique=True)
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    course_type = models.CharField(max_length=20, choices=TYPE_CHOICES, default=TYPE_ELEARNING)
    duration_mins = models.PositiveIntegerField(default=0)
    linked_assessment = models.ForeignKey('assessments.Assessment', on_delete=models.SET_NULL, null=True, blank=True, related_name='courses')
    certificate_on_completion = models.BooleanField(default=False)
    validity_months = models.PositiveSmallIntegerField(null=True, blank=True, help_text='Null = never expires.')
    is_active = models.BooleanField(default=True)

    class Meta:
        db_table = 'assessments_courses_v2'
        ordering = ['code']

    def __str__(self):
        return self.title


class CourseSession(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    course = models.ForeignKey(Course, on_delete=models.CASCADE, related_name='sessions')
    start_at = models.DateTimeField()
    end_at = models.DateTimeField(null=True, blank=True)
    trainer = models.ForeignKey('accounts.User', on_delete=models.SET_NULL, null=True, blank=True, related_name='course_sessions_trained')
    location_or_link = models.CharField(max_length=500, blank=True)
    capacity = models.PositiveSmallIntegerField(null=True, blank=True)

    class Meta:
        db_table = 'assessments_course_sessions_v2'
        ordering = ['start_at']

    def __str__(self):
        return f'{self.course.code} @ {self.start_at}'

    @property
    def seats_taken(self) -> int:
        return self.enrolments.exclude(status=Enrolment.STATUS_CANCELLED).count()


class Enrolment(models.Model):
    STATUS_PENDING_APPROVAL = 'pending_approval'
    STATUS_ENROLLED  = 'enrolled'
    STATUS_WAITLISTED = 'waitlisted'
    STATUS_ATTENDED  = 'attended'
    STATUS_COMPLETED = 'completed'
    STATUS_CANCELLED = 'cancelled'
    STATUS_CHOICES = [
        (STATUS_PENDING_APPROVAL, 'Pending approval'), (STATUS_ENROLLED, 'Enrolled'),
        (STATUS_WAITLISTED, 'Waitlisted'), (STATUS_ATTENDED, 'Attended'),
        (STATUS_COMPLETED, 'Completed'), (STATUS_CANCELLED, 'Cancelled'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    employee = models.ForeignKey('accounts.User', on_delete=models.CASCADE, related_name='enrolments')
    session = models.ForeignKey(CourseSession, on_delete=models.CASCADE, related_name='enrolments')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_PENDING_APPROVAL)
    is_mandatory = models.BooleanField(default=False)
    due_date = models.DateField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    certificate_issued_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = 'assessments_enrolments_v2'
        unique_together = [('employee', 'session')]
        ordering = ['-id']

    def __str__(self):
        return f'{self.employee_id} -> {self.session_id} ({self.status})'


class MandatoryTrainingPolicy(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    course = models.ForeignKey(Course, on_delete=models.CASCADE, related_name='mandatory_policies')
    due_days_after_joining = models.PositiveSmallIntegerField(null=True, blank=True)
    recurs_every_months = models.PositiveSmallIntegerField(null=True, blank=True, help_text='Null = one-time, not recurring.')
    is_active = models.BooleanField(default=False, help_text='Seeded policies default OFF.')

    class Meta:
        db_table = 'assessments_mandatory_training_policies_v2'

    def __str__(self):
        return f'Mandatory: {self.course.code}'


class LearningV2Entitlement(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    is_enabled = models.BooleanField(default=False)
    enabled_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = 'learning_v2_entitlement_v2'

    def __str__(self):
        return f'learning.v2: {"ON" if self.is_enabled else "off"}'
