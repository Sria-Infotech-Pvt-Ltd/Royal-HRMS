"""
Phase 8A Task C — performance: review templates, a real rating-scale
master (replacing the hardcoded 1-5 `RATING_CHOICES` as DATA, not a code
change to the existing field), competencies, calibration, and PIP.

Scoped down, stated plainly:
- No 360 peer-nomination workflow, no continuous-feedback/praise notes,
  no goal cascading/alignment links, no outcome->Salary-Revision/Promotion
  automation (Task C.10) — each is real additional scope; this pass builds
  the template/scale/competency/calibration/PIP DATA LAYER the master
  prompt's Task C opens with, not every downstream workflow.
- `ReviewCycle`/`Goal`/`PerformanceReview` and their fixed fields are
  COMPLETELY UNTOUCHED — RatingScale/ReviewTemplate are new, parallel data
  nothing reads yet; the existing hardcoded RATING_CHOICES keeps being
  used by those real fields exactly as before.
"""
import uuid

from django.db import models


class RatingScale(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    code = models.CharField(max_length=40, unique=True)
    name = models.CharField(max_length=100)
    # [{"value": 1, "label": "Needs Improvement"}, ..., {"value": 5, "label": "Outstanding"}]
    points = models.JSONField(default=list)
    allow_not_applicable = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)

    class Meta:
        db_table = 'performance_rating_scales_v2'
        ordering = ['code']

    def __str__(self):
        return self.code


class Competency(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    code = models.CharField(max_length=40, unique=True)
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        db_table = 'performance_competencies_v2'
        ordering = ['code']

    def __str__(self):
        return self.code


class ReviewTemplate(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    code = models.CharField(max_length=40, unique=True)
    name = models.CharField(max_length=100)
    rating_scale = models.ForeignKey(RatingScale, on_delete=models.PROTECT, related_name='review_templates')
    # [{"key": "goals", "label": "Goals", "weight": 60}, {"key": "competencies", ...}] — must sum to 100,
    # validated in services_performance.validate_section_weights(), not by a DB constraint.
    sections = models.JSONField(default=list)
    is_active = models.BooleanField(default=True)

    class Meta:
        db_table = 'performance_review_templates_v2'
        ordering = ['code']

    def __str__(self):
        return self.code


class CalibrationSession(models.Model):
    STATUS_OPEN   = 'open'
    STATUS_LOCKED = 'locked'
    STATUS_CHOICES = [(STATUS_OPEN, 'Open'), (STATUS_LOCKED, 'Locked')]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    cycle = models.ForeignKey('performance.ReviewCycle', on_delete=models.CASCADE, related_name='calibration_sessions')
    name = models.CharField(max_length=100)
    # {"5": 10, "4": 20, "3": 40, "2": 20, "1": 10} — target % per rating point, a soft guideline.
    distribution_guideline = models.JSONField(default=dict, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_OPEN)
    locked_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = 'performance_calibration_sessions_v2'
        ordering = ['-locked_at']

    def __str__(self):
        return f'{self.cycle_id} — {self.name}'


class CalibrationAdjustment(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    session = models.ForeignKey(CalibrationSession, on_delete=models.CASCADE, related_name='adjustments')
    review = models.ForeignKey('performance.PerformanceReview', on_delete=models.CASCADE, related_name='calibration_adjustments')
    original_rating = models.CharField(max_length=1)
    adjusted_rating = models.CharField(max_length=1)
    reason = models.TextField()
    adjusted_by = models.ForeignKey('accounts.User', on_delete=models.SET_NULL, null=True, blank=True, related_name='calibration_adjustments_made')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'performance_calibration_adjustments_v2'
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.review_id}: {self.original_rating} -> {self.adjusted_rating}'


class PerformanceImprovementPlan(models.Model):
    STATUS_ACTIVE    = 'active'
    STATUS_COMPLETED = 'completed'
    STATUS_EXTENDED  = 'extended'
    STATUS_EXIT      = 'exit'
    STATUS_CHOICES = [
        (STATUS_ACTIVE, 'Active'), (STATUS_COMPLETED, 'Completed'),
        (STATUS_EXTENDED, 'Extended'), (STATUS_EXIT, 'Exit'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    employee = models.ForeignKey('accounts.User', on_delete=models.CASCADE, related_name='performance_improvement_plans')
    objectives = models.TextField()
    start_date = models.DateField()
    end_date = models.DateField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_ACTIVE)
    outcome_note = models.TextField(blank=True)
    approved_by = models.ForeignKey('accounts.User', on_delete=models.SET_NULL, null=True, blank=True, related_name='pips_approved')
    # Field security: PIP data is sensitive — this model carries no
    # built-in masking of its own (Phase 4's field-security system operates
    # on dynamic EntityDefinition fields, not plain Django model fields —
    # confirmed earlier this session); restricting who can read a PIP row
    # is the view/permission layer's job, not enforced here.
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'performance_pips_v2'
        ordering = ['-start_date']

    def __str__(self):
        return f'{self.employee_id} PIP ({self.status})'


class PerformanceV2Entitlement(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    is_enabled = models.BooleanField(default=False)
    enabled_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = 'performance_v2_entitlement_v2'

    def __str__(self):
        return f'performance.v2: {"ON" if self.is_enabled else "off"}'
