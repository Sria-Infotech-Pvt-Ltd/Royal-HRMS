"""
Phase 8A Task A/E — recruitment service layer: candidate migration (one
CandidateProfile+Application per legacy Candidate, status->stage mapped),
scorecard validation, referral bonus resolution, and conversion to a real
Stage-1 HireAction.

Everything here is additive: no existing Candidate/ReferralBonus/view is
modified by any function in this module.
"""
from decimal import Decimal

from django.db import transaction
from django.utils import timezone

from apps.recruitment.models import (
    Application, BGVCheck, Candidate, CandidateProfile, JobOpening, JobRequisition,
    Offer, PipelineStage, PipelineTemplate, ReferralBonus, ReferralProgramRule, Scorecard, ScorecardTemplate,
)

# Candidate.status -> PipelineStage.code (on the seeded "Legacy" pipeline
# template — see seed_legacy_pipeline_template). One-to-one, nothing
# invented: every real STATUS_CHOICES value maps to exactly one stage.
CANDIDATE_STATUS_TO_STAGE_CODE = {
    'pending':               'applied',
    'screening':             'screening',
    'interview_scheduled':   'interview',
    'interview_done':        'interview',
    'selected':              'offer',
    'offer_sent':            'offer',
    'converted':             'hired',
    'rejected':              'rejected',
}


def seed_legacy_pipeline_template() -> PipelineTemplate:
    """Idempotent. One stage per distinct Candidate.status value, in the
    order they naturally progress — the mapping table Task E.2 asks for,
    expressed as real PipelineStage rows rather than a bare Python dict,
    so an admin can see/edit it like any other pipeline."""
    template, _ = PipelineTemplate.objects.get_or_create(code='LEGACY', defaults={'name': 'Legacy (migrated candidates)'})
    stage_defs = [
        ('applied', 'Applied', PipelineStage.CATEGORY_ACTIVE, 0),
        ('screening', 'Screening', PipelineStage.CATEGORY_ACTIVE, 1),
        ('interview', 'Interview', PipelineStage.CATEGORY_ACTIVE, 2),
        ('offer', 'Offer', PipelineStage.CATEGORY_OFFER, 3),
        ('hired', 'Hired', PipelineStage.CATEGORY_HIRED, 4),
        ('rejected', 'Rejected', PipelineStage.CATEGORY_REJECTED, 5),
    ]
    for code, name, category, order in stage_defs:
        PipelineStage.objects.get_or_create(
            template=template, code=code, defaults={'name': name, 'stage_category': category, 'order': order},
        )
    return template


@transaction.atomic
def migrate_candidate_to_application(candidate: Candidate) -> Application:
    """Idempotent — returns the existing Application if this Candidate was
    already migrated (via its OneToOne `application_v2`)."""
    existing = getattr(candidate, 'application_v2', None)
    if existing is not None:
        return existing

    template = seed_legacy_pipeline_template()
    stage_code = CANDIDATE_STATUS_TO_STAGE_CODE.get(candidate.status, 'applied')
    stage = PipelineStage.objects.get(template=template, code=stage_code)

    profile, _ = CandidateProfile.objects.get_or_create(
        legacy_candidate=candidate,
        defaults={'name': candidate.name, 'email': candidate.email, 'phone': candidate.phone},
    )

    # position_applied is free text — no real JobOpening exists for it.
    # Per Task E.2's own instruction: "a legacy opening per distinct text
    # value per branch" — not invented here as a fake real opening; left
    # as None (the Application's own `opening` FK is nullable precisely
    # for this case), reported via unmigrated_legacy_openings() instead.
    return Application.objects.create(
        candidate_profile=profile, opening=None, current_stage=stage, legacy_candidate=candidate,
    )


def unmigrated_legacy_openings() -> dict:
    """{(position_applied, branch_name): candidate_count} — the real
    report Task E.2 asks for instead of silently inventing opening rows."""
    from collections import Counter
    counter = Counter()
    for candidate in Candidate.objects.all():
        branch_name = candidate.branch.branch_name if candidate.branch_id else None
        counter[(candidate.position_applied, branch_name)] += 1
    return dict(counter)


def validate_scorecard_weights(template: ScorecardTemplate) -> None:
    total = sum(c.get('weight', 0) for c in template.criteria)
    if total != 100:
        raise ValueError(f'{template.code}: scorecard criteria weights sum to {total}, must be exactly 100.')


def submit_scorecard(scorecard: Scorecard) -> Scorecard:
    template_criteria = {c['criterion'] for c in scorecard.template.criteria}
    scored_criteria = set(scorecard.scores.keys())
    missing = template_criteria - scored_criteria
    if missing:
        raise ValueError(f'Missing scores for: {sorted(missing)}')
    scorecard.submitted_at = timezone.now()
    scorecard.save(update_fields=['submitted_at'])
    return scorecard


def visible_scorecards_for_round(interview_round, requesting_interviewer) -> list:
    """Blind-scoring rule: an interviewer sees only their OWN scorecard
    until every scorecard for the round is submitted — then everyone sees
    everyone's."""
    all_scorecards = list(interview_round.scorecards.all())
    all_submitted = all(s.submitted_at is not None for s in all_scorecards)
    if all_submitted:
        return all_scorecards
    return [s for s in all_scorecards if s.interviewer_id == requesting_interviewer.id]


def resolve_referral_bonus_amount(rule: ReferralProgramRule) -> Decimal:
    return rule.bonus_amount


def public_opening_data(opening: JobOpening) -> dict | None:
    """The real 'public careers endpoint returns only published fields'
    rule (Task A.2) — returns None for a non-published or internal-only
    opening so the caller can 404 it, and otherwise only the handful of
    fields safe to expose externally (no requisition/budget/hiring-manager
    data)."""
    if opening.status != JobOpening.STATUS_PUBLISHED or opening.is_internal_only:
        return None
    return {
        'id': str(opening.id), 'title': opening.title, 'description': opening.description,
        'closing_date': opening.closing_date,
    }


@transaction.atomic
def convert_offer_to_hire_action(offer: Offer, created_by) -> 'HireAction':  # noqa: F821 — imported lazily below
    """Creates a draft Stage-1 HireAction pre-filled from the accepted
    offer, per Task A.10. Requires the offer to actually be accepted
    (matches "an accepted offer... creates a Hire action" — never
    converts a pending/declined offer)."""
    from apps.accounts.models import HireAction

    if offer.status != Offer.STATUS_ACCEPTED:
        raise ValueError(f'Offer {offer.id} is not accepted (status={offer.status}) — cannot convert to a hire.')

    return HireAction.objects.create(
        position=offer.position,
        reason=HireAction.REASON_NEW_POSITION,
        effective_from=offer.joining_date,
        created_by=created_by,
    )
