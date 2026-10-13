"""Phase 8A gap-closure pass — question pools, manual grading queue, proctoring flags."""
import uuid

from django.db import models


class QuestionPool(models.Model):
    """'Pick N random from tag X' — services_learning_gaps.draw_from_pool()
    is the randomiser (seeded RNG accepted as a parameter for test
    determinism, per the master prompt's own testing requirement)."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    code = models.CharField(max_length=40, unique=True)
    tag = models.CharField(max_length=60)
    pick_count = models.PositiveSmallIntegerField(default=1)

    class Meta:
        db_table = 'assessments_question_pools_v2'

    def __str__(self):
        return f'{self.code} (pick {self.pick_count} from tag={self.tag})'


class ManualGradingTask(models.Model):
    STATUS_PENDING = 'pending'
    STATUS_GRADED  = 'graded'
    STATUS_CHOICES = [(STATUS_PENDING, 'Pending'), (STATUS_GRADED, 'Graded')]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    response = models.OneToOneField('assessments.CandidateResponse', on_delete=models.CASCADE, related_name='manual_grading_task')
    free_text_answer = models.TextField(blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_PENDING)
    score_awarded = models.PositiveSmallIntegerField(null=True, blank=True)
    grader_comment = models.TextField(blank=True)
    graded_by = models.ForeignKey('accounts.User', on_delete=models.SET_NULL, null=True, blank=True, related_name='manual_grading_tasks_graded')
    graded_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = 'assessments_manual_grading_tasks_v2'
        ordering = ['status', '-id']

    def __str__(self):
        return f'Grading for {self.response_id} ({self.status})'


class ProctoringFlag(models.Model):
    """Client-reported data only, per the master prompt's own "data only"
    scope — no real proctoring enforcement, just a record a reviewer can
    look at."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    assignment = models.ForeignKey('assessments.CandidateAssignment', on_delete=models.CASCADE, related_name='proctoring_flags')
    flag_type = models.CharField(max_length=40, choices=[('tab_switch', 'Tab switch'), ('fullscreen_exit', 'Fullscreen exit'), ('copy_paste', 'Copy/paste detected')])
    count = models.PositiveSmallIntegerField(default=1)
    reported_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'assessments_proctoring_flags_v2'

    def __str__(self):
        return f'{self.assignment_id}: {self.flag_type} x{self.count}'
