"""Phase 8A Task C — review template section weights, the standard-review seed, calibration distribution guideline check, PIP lifecycle."""
from django.db import transaction
from django.utils import timezone

from apps.performance.models import CalibrationAdjustment, PerformanceImprovementPlan, RatingScale, ReviewTemplate


def seed_standard_rating_scale() -> RatingScale:
    """Idempotent. Reproduces the existing hardcoded 1-5 RATING_CHOICES as
    real data — PerformanceReview/Goal's own CharField+RATING_CHOICES are
    completely untouched; this is a parallel, not-yet-consumed scale."""
    scale, _ = RatingScale.objects.get_or_create(
        code='STANDARD_1_5',
        defaults={
            'name': 'Standard 1-5',
            'points': [
                {'value': 1, 'label': 'Needs Improvement'}, {'value': 2, 'label': 'Below Expectations'},
                {'value': 3, 'label': 'Meets Expectations'}, {'value': 4, 'label': 'Exceeds Expectations'},
                {'value': 5, 'label': 'Outstanding'},
            ],
        },
    )
    return scale


def seed_standard_review_template() -> ReviewTemplate:
    """Idempotent. Reproduces PerformanceReview's existing 6 fixed text
    fields as a seeded "Standard Review" template (Task C.1's own
    requirement) — PerformanceReview itself is not touched; nothing reads
    this template yet."""
    scale = seed_standard_rating_scale()
    template, _ = ReviewTemplate.objects.get_or_create(
        code='STANDARD_REVIEW',
        defaults={
            'name': 'Standard Review',
            'rating_scale': scale,
            'sections': [
                {'key': 'metric_reference', 'label': 'Metric reference', 'weight': 0},
                {'key': 'what_changed', 'label': 'What changed', 'weight': 0},
                {'key': 'key_strengths', 'label': 'Key strengths', 'weight': 0},
                {'key': 'development_areas', 'label': 'Development areas', 'weight': 0},
                {'key': 'support_needed', 'label': 'Support needed', 'weight': 0},
                {'key': 'next_cycle_goal', 'label': 'Next cycle goal', 'weight': 0},
                {'key': 'overall_rating', 'label': 'Overall rating', 'weight': 100},
            ],
        },
    )
    return template


def validate_section_weights(template: ReviewTemplate) -> None:
    total = sum(s.get('weight', 0) for s in template.sections)
    if total != 100:
        raise ValueError(f'{template.code}: section weights sum to {total}, must be exactly 100.')


def check_calibration_distribution(session, actual_distribution: dict) -> dict:
    """Compares `actual_distribution` ({"5": pct, "4": pct, ...}) against
    `session.distribution_guideline`. Returns {rating: {'target':, 'actual':,
    'over_by':}} for every rating that exceeds its guideline — a WARNING
    the caller surfaces, never a hard block enforced here (the master
    prompt's own "warn or block" choice is left to the caller/policy, not
    hardcoded into this function)."""
    warnings = {}
    for rating, target_pct in session.distribution_guideline.items():
        actual_pct = actual_distribution.get(rating, 0)
        if actual_pct > target_pct:
            warnings[rating] = {'target': target_pct, 'actual': actual_pct, 'over_by': actual_pct - target_pct}
    return warnings


@transaction.atomic
def record_calibration_adjustment(session, review, original_rating, adjusted_rating, reason, adjusted_by) -> CalibrationAdjustment:
    if session.status == session.STATUS_LOCKED:
        raise ValueError(f'Calibration session {session.name} is locked — no further adjustments.')
    if not reason.strip():
        raise ValueError('A reason is required for every calibration adjustment.')
    return CalibrationAdjustment.objects.create(
        session=session, review=review, original_rating=original_rating, adjusted_rating=adjusted_rating,
        reason=reason, adjusted_by=adjusted_by,
    )


def lock_calibration_session(session) -> None:
    session.status = session.STATUS_LOCKED
    session.locked_at = timezone.now()
    session.save(update_fields=['status', 'locked_at'])


@transaction.atomic
def close_pip(pip: PerformanceImprovementPlan, outcome: str, outcome_note: str) -> PerformanceImprovementPlan:
    if outcome not in dict(PerformanceImprovementPlan.STATUS_CHOICES):
        raise ValueError(f'Unknown PIP outcome: {outcome!r}')
    pip.status = outcome
    pip.outcome_note = outcome_note
    pip.save(update_fields=['status', 'outcome_note', 'updated_at'])
    return pip
