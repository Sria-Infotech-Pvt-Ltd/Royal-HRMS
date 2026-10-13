"""Phase 8A gap-closure pass — continuous feedback, 360 peer nomination/feedback, goal cascading, outcome->action linkage."""
import uuid

from django.db import models


class FeedbackNote(models.Model):
    VISIBILITY_PRIVATE_TO_MANAGER = 'private_manager'
    VISIBILITY_SHARED             = 'shared'
    VISIBILITY_CHOICES = [(VISIBILITY_PRIVATE_TO_MANAGER, 'Private to manager'), (VISIBILITY_SHARED, 'Shared with employee')]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    employee = models.ForeignKey('accounts.User', on_delete=models.CASCADE, related_name='feedback_notes_received')
    author = models.ForeignKey('accounts.User', on_delete=models.SET_NULL, null=True, blank=True, related_name='feedback_notes_given')
    note_type = models.CharField(max_length=20, choices=[('praise', 'Praise'), ('feedback', 'Feedback'), ('one_on_one', 'One-on-one note')], default='feedback')
    body = models.TextField()
    visibility = models.CharField(max_length=20, choices=VISIBILITY_CHOICES, default=VISIBILITY_PRIVATE_TO_MANAGER)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'performance_feedback_notes_v2'
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.note_type} for {self.employee_id}'


class PeerNomination(models.Model):
    STATUS_PENDING  = 'pending'
    STATUS_APPROVED = 'approved'
    STATUS_REJECTED = 'rejected'
    STATUS_CHOICES = [(STATUS_PENDING, 'Pending'), (STATUS_APPROVED, 'Approved'), (STATUS_REJECTED, 'Rejected')]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    cycle = models.ForeignKey('performance.ReviewCycle', on_delete=models.CASCADE, related_name='peer_nominations')
    employee = models.ForeignKey('accounts.User', on_delete=models.CASCADE, related_name='peer_nominations_for')
    nominated_peer = models.ForeignKey('accounts.User', on_delete=models.CASCADE, related_name='peer_nominations_as_peer')
    nominated_by = models.ForeignKey('accounts.User', on_delete=models.SET_NULL, null=True, blank=True, related_name='peer_nominations_made')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_PENDING)

    class Meta:
        db_table = 'performance_peer_nominations_v2'
        unique_together = [('cycle', 'employee', 'nominated_peer')]

    def __str__(self):
        return f'{self.employee_id} <- {self.nominated_peer_id}'


class PeerFeedback(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    nomination = models.OneToOneField(PeerNomination, on_delete=models.CASCADE, related_name='feedback')
    responses = models.JSONField(default=dict, help_text='{"question_key": "answer text"}')
    submitted_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = 'performance_peer_feedback_v2'

    def __str__(self):
        return f'Feedback for {self.nomination_id}'


class GoalAlignment(models.Model):
    """Cascading link: `goal` is aligned to `parent_goal` (org -> org unit -> individual)."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    goal = models.OneToOneField('performance.Goal', on_delete=models.CASCADE, related_name='alignment')
    parent_goal = models.ForeignKey('performance.Goal', on_delete=models.SET_NULL, null=True, blank=True, related_name='child_alignments')

    class Meta:
        db_table = 'performance_goal_alignments_v2'

    def __str__(self):
        return f'{self.goal_id} -> {self.parent_goal_id}'


class PerformanceOutcomeAction(models.Model):
    """Links a published PerformanceReview's final rating to the real 7A
    compensation revision / PromotionRecord it produced — created ONLY
    after the configured approval, per the master prompt's own "nothing is
    paid automatically without the configured approvals" rule (enforced in
    services_performance_outcomes.apply_outcome(), not just documented)."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    review = models.OneToOneField('performance.PerformanceReview', on_delete=models.CASCADE, related_name='outcome_action')
    compensation_version = models.ForeignKey('payroll.EmployeeCompensation', on_delete=models.SET_NULL, null=True, blank=True, related_name='performance_outcomes')
    promotion_record = models.ForeignKey('accounts.PromotionRecord', on_delete=models.SET_NULL, null=True, blank=True, related_name='performance_outcomes')
    bonus_amount = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    approved_by = models.ForeignKey('accounts.User', on_delete=models.SET_NULL, null=True, blank=True, related_name='performance_outcomes_approved')
    approved_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = 'performance_outcome_actions_v2'

    def __str__(self):
        return f'Outcome for {self.review_id}'
