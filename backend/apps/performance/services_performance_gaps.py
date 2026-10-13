"""Phase 8A gap-closure — continuous feedback, 360 peer nomination/feedback (with anonymity threshold), goal cascading, outcome->action automation."""
from decimal import Decimal

from django.db import transaction
from django.utils import timezone

from apps.performance.models import (
    FeedbackNote, Goal, GoalAlignment, PeerFeedback, PeerNomination, PerformanceOutcomeAction,
)


def give_feedback(employee, author, body: str, note_type: str = 'feedback', visibility: str = FeedbackNote.VISIBILITY_PRIVATE_TO_MANAGER) -> FeedbackNote:
    return FeedbackNote.objects.create(employee=employee, author=author, note_type=note_type, body=body, visibility=visibility)


def nominate_peer(cycle, employee, nominated_peer, nominated_by, *, min_count: int = 3, max_count: int = 6) -> PeerNomination:
    existing_count = PeerNomination.objects.filter(cycle=cycle, employee=employee).count()
    if existing_count >= max_count:
        raise ValueError(f'{employee}: already has {existing_count} nominations, max is {max_count}.')
    nomination = PeerNomination.objects.create(cycle=cycle, employee=employee, nominated_peer=nominated_peer, nominated_by=nominated_by)
    PeerFeedback.objects.create(nomination=nomination)
    return nomination


def submit_peer_feedback(nomination: PeerNomination, responses: dict) -> PeerFeedback:
    feedback = nomination.feedback
    feedback.responses = responses
    feedback.submitted_at = timezone.now()
    feedback.save(update_fields=['responses', 'submitted_at'])
    nomination.status = PeerNomination.STATUS_APPROVED
    nomination.save(update_fields=['status'])
    return feedback


def visible_360_feedback(employee, cycle, *, min_responders: int = 3) -> list:
    """Anonymity rule: feedback is only visible once at least
    `min_responders` peers have submitted — otherwise a single response
    could be de-anonymised by elimination."""
    submitted = PeerFeedback.objects.filter(
        nomination__cycle=cycle, nomination__employee=employee, submitted_at__isnull=False,
    )
    if submitted.count() < min_responders:
        return []
    return list(submitted)


@transaction.atomic
def set_goal_alignment(goal: Goal, parent_goal: Goal | None) -> GoalAlignment:
    if parent_goal is not None and parent_goal.id == goal.id:
        raise ValueError('A goal cannot be aligned to itself.')
    alignment, _ = GoalAlignment.objects.update_or_create(goal=goal, defaults={'parent_goal': parent_goal})
    return alignment


def validate_goal_weights_total_100(employee, cycle) -> None:
    total = sum((g.weight_percent or 0) for g in Goal.objects.filter(employee=employee, cycle=cycle))
    if total != 100:
        raise ValueError(f'{employee}: goal weights for this cycle sum to {total}, must be exactly 100.')


@transaction.atomic
def apply_outcome(review, *, approved_by, bonus_amount: Decimal | None = None,
                   new_annual_ctc: Decimal | None = None, pay_structure=None,
                   promotion_fields: dict | None = None) -> PerformanceOutcomeAction:
    """Per the master prompt's own rule: 'nothing is paid automatically
    without the configured approvals' — enforced here by REQUIRING
    `approved_by`, not just documenting the requirement. Creates the real
    7A EmployeeCompensation revision (via Phase 7A's own
    create_compensation(), never a re-derived calculation) and/or a real
    PromotionRecord, only when the caller actually supplies that input."""
    if approved_by is None:
        raise ValueError('An outcome cannot be applied without an approver.')
    if hasattr(review, 'outcome_action'):
        raise ValueError(f'Review {review.id} already has an outcome action applied.')

    compensation = None
    if new_annual_ctc is not None:
        from apps.payroll.services_compensation import create_compensation
        import datetime
        compensation, _ = create_compensation(
            review.employee, new_annual_ctc, datetime.date.today(),
            pay_structure=pay_structure, reason='increment',
        )

    promotion = None
    if promotion_fields:
        from apps.accounts.models import PromotionRecord
        promotion = PromotionRecord.objects.create(employee=review.employee, promoted_by=approved_by, **promotion_fields)

    return PerformanceOutcomeAction.objects.create(
        review=review, compensation_version=compensation, promotion_record=promotion,
        bonus_amount=bonus_amount, approved_by=approved_by, approved_at=timezone.now(),
    )
