import uuid

from django.conf import settings
from django.db import models


# ─── Review Cycle ───────────────────────────────────────────────────────────────

CYCLE_DRAFT  = 'draft'
CYCLE_ACTIVE = 'active'
CYCLE_CLOSED = 'closed'
CYCLE_STATUS_CHOICES = [
    (CYCLE_DRAFT,  'Draft'),
    (CYCLE_ACTIVE, 'Active'),
    (CYCLE_CLOSED, 'Closed'),
]


class ReviewCycle(models.Model):
    """One performance-review period (e.g. "Q3 2026"). Only one cycle should
    be 'active' at a time in practice (enforced at the view layer, not the
    DB, the same way this codebase leaves single-active-record invariants
    like PayrollSettings to application logic rather than a DB constraint)."""
    id                 = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name               = models.CharField(max_length=100)
    period_start       = models.DateField()
    period_end         = models.DateField()
    self_review_due    = models.DateField()
    manager_review_due = models.DateField()
    status             = models.CharField(max_length=10, choices=CYCLE_STATUS_CHOICES, default=CYCLE_DRAFT)
    created_by         = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='review_cycles_created',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'performance_review_cycles'
        ordering = ['-period_start']

    def __str__(self) -> str:
        return self.name


# ─── Goal ────────────────────────────────────────────────────────────────────

GOAL_ON_TRACK  = 'on_track'
GOAL_AT_RISK   = 'at_risk'
GOAL_COMPLETED = 'completed'
GOAL_STATUS_CHOICES = [
    (GOAL_ON_TRACK,  'On Track'),
    (GOAL_AT_RISK,   'At Risk'),
    (GOAL_COMPLETED, 'Completed'),
]

# Shared 1-5 self/manager rating scale — defined once here (rather than
# separately under Goal and PerformanceReview) since both use the exact
# same choice list.
RATING_CHOICES = [
    (str(n), str(n)) for n in range(1, 6)
]


class Goal(models.Model):
    """A single goal an employee (or their manager, on their behalf) sets
    for one review cycle. Plain CRUD — no approval workflow, matching the
    mockup's own read-only-until-cycle-opens framing rather than inventing
    an approval chain nothing in the spec actually describes.

    The self-review fields below (self_rating, outcome_measure,
    evidence_reference, self_comments) capture the employee's per-goal
    outcome write-up shown in the "My appraisal" mockup — one sub-card per
    goal — separate from the cycle-wide reflection fields that still live
    on PerformanceReview (key_strengths, development_areas, etc.)."""
    id          = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    employee    = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='goals')
    cycle       = models.ForeignKey(ReviewCycle, on_delete=models.CASCADE, related_name='goals')
    title       = models.CharField(max_length=200)
    description = models.TextField(blank=True, default='')
    target_metric = models.CharField(max_length=200, blank=True, default='')
    due_date    = models.DateField(null=True, blank=True)
    status      = models.CharField(max_length=20, choices=GOAL_STATUS_CHOICES, default=GOAL_ON_TRACK)

    # Weighting is set by HR/admin when the goal is agreed at cycle-open —
    # nullable since not every goal need carry a weight.
    weight_percent = models.PositiveSmallIntegerField(null=True, blank=True)

    # ── Employee's self-review outcome for this goal ──
    self_rating        = models.CharField(max_length=1, choices=RATING_CHOICES, blank=True, default='')
    outcome_measure     = models.CharField(max_length=200, blank=True, default='')
    evidence_reference = models.TextField(blank=True, default='')
    self_comments       = models.TextField(blank=True, default='')

    created_by  = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='goals_created',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'performance_goals'
        ordering = ['due_date', 'created_at']

    def __str__(self) -> str:
        return f'{self.employee.full_name} — {self.title}'


# ─── Performance Review ─────────────────────────────────────────────────────────

REVIEW_NOT_STARTED    = 'not_started'
REVIEW_RETURNED       = 'returned'
REVIEW_SELF_REVIEW    = 'self_review'
REVIEW_HR_CALIBRATION = 'hr_calibration'
REVIEW_PUBLISHED      = 'published'
REVIEW_COMPLETED      = 'completed'
REVIEW_STATUS_CHOICES = [
    (REVIEW_NOT_STARTED,    'Not Started'),
    (REVIEW_RETURNED,       'Returned for Changes'),
    (REVIEW_SELF_REVIEW,    'Awaiting Manager Review'),
    (REVIEW_HR_CALIBRATION, 'Awaiting HR Calibration'),
    (REVIEW_PUBLISHED,      'Published'),
    (REVIEW_COMPLETED,      'Completed'),
]


class PerformanceReview(models.Model):
    """One row per (employee, cycle) — self-review fields and manager-review
    fields both live on this one row rather than a generic multi-stage table
    like SeparationApprovalStage, since there are exactly four real steps
    here (self, manager, HR calibration, publish/acknowledge); `status` is
    derived from the four *_at milestone fields the same way
    SeparationRequest.status is derived from its stages, recomputed on
    every submit rather than stored independently of them."""
    id       = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    employee = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='performance_reviews')
    cycle    = models.ForeignKey(ReviewCycle, on_delete=models.CASCADE, related_name='reviews')

    # ── Self-review (same field list as the mockup's own appraisal form) ──
    metric_reference  = models.TextField(blank=True, default='')
    what_changed      = models.TextField(blank=True, default='')
    key_strengths     = models.TextField(blank=True, default='')
    development_areas = models.TextField(blank=True, default='')
    support_needed    = models.TextField(blank=True, default='')
    next_cycle_goal   = models.TextField(blank=True, default='')
    self_rating       = models.CharField(max_length=1, choices=RATING_CHOICES, blank=True, default='')
    self_submitted_at = models.DateTimeField(null=True, blank=True)

    # ── Manager review ──
    manager = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='performance_reviews_to_manage',
    )
    manager_rating       = models.CharField(max_length=1, choices=RATING_CHOICES, blank=True, default='')
    manager_notes        = models.TextField(blank=True, default='')
    manager_submitted_at = models.DateTimeField(null=True, blank=True)
    # Development plan + next check-in the manager agrees with the employee —
    # part of the manager assessment, hidden from the employee until publish.
    manager_development_plan = models.TextField(blank=True, default='')
    manager_next_checkin     = models.DateField(null=True, blank=True)

    # A manager can send a submitted self-review back for changes. Returning
    # clears self_submitted_at (the employee may edit and resubmit) and keeps
    # the reason + time so the employee sees why and the history records it.
    returned_at   = models.DateTimeField(null=True, blank=True)
    return_reason = models.TextField(blank=True, default='')

    # ── HR calibration and publish/acknowledge (stages 3 and 4) ──
    hr_calibrated_at = models.DateTimeField(null=True, blank=True)
    # The rating HR finally confirms (may differ from the manager's) and why.
    final_rating     = models.CharField(max_length=1, choices=RATING_CHOICES, blank=True, default='')
    calibration_note = models.TextField(blank=True, default='')
    published_at     = models.DateTimeField(null=True, blank=True)
    acknowledged_at  = models.DateTimeField(null=True, blank=True)
    # Optional response the employee leaves when acknowledging (acknowledging
    # means "read", not "agree").
    acknowledgement_comment = models.TextField(blank=True, default='')

    status     = models.CharField(max_length=20, choices=REVIEW_STATUS_CHOICES, default=REVIEW_NOT_STARTED, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table        = 'performance_reviews'
        unique_together = [('employee', 'cycle')]
        ordering        = ['-created_at']

    def __str__(self) -> str:
        return f'{self.employee.full_name} — {self.cycle.name} ({self.status})'

    def recompute_status(self) -> None:
        """Mirrors SeparationRequest's own derive-on-every-action convention
        — call after changing any of the four milestone fields, before
        saving. `hr_calibrated_at` is an audit timestamp for when HR signed
        off, but doesn't get its own status — the review stays
        'hr_calibration' (awaiting the publish step) until `published_at`
        is actually set."""
        if self.acknowledged_at:
            self.status = REVIEW_COMPLETED
        elif self.published_at:
            self.status = REVIEW_PUBLISHED
        elif self.manager_submitted_at:
            self.status = REVIEW_HR_CALIBRATION
        elif self.self_submitted_at:
            self.status = REVIEW_SELF_REVIEW
        elif self.returned_at:
            self.status = REVIEW_RETURNED
        else:
            self.status = REVIEW_NOT_STARTED


# ─── Continuous feedback requests ────────────────────────────────────────────

class FeedbackRequest(models.Model):
    """One person asking another for focused feedback (manager, peer or direct
    report). Separate from the formal appraisal: no ratings, no HR step."""
    STATUS_PENDING  = 'pending'
    STATUS_PROVIDED = 'provided'
    STATUS_DECLINED = 'declined'
    STATUS_CHOICES = [
        (STATUS_PENDING,  'Awaiting response'),
        (STATUS_PROVIDED, 'Feedback received'),
        (STATUS_DECLINED, 'Declined'),
    ]

    id          = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    requester   = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='feedback_requests_made')
    recipient   = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='feedback_requests_received')
    cycle_label = models.CharField(max_length=60, default='Continuous feedback')
    topic       = models.TextField()
    status      = models.CharField(max_length=10, choices=STATUS_CHOICES, default=STATUS_PENDING, db_index=True)
    response    = models.TextField(blank=True, default='')
    responded_at = models.DateTimeField(null=True, blank=True)
    created_at  = models.DateTimeField(auto_now_add=True)
    updated_at  = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'performance_feedback_requests'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['recipient', 'status'], name='fbreq_recipient_status_idx'),
            models.Index(fields=['requester', 'created_at'], name='fbreq_requester_created_idx'),
        ]

    def __str__(self) -> str:
        return f'{self.requester_id} -> {self.recipient_id} ({self.status})'
