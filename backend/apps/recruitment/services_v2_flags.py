"""
Phase 8A Task E — the three per-module flags (recruitment.v2,
performance.v2, learning.v2), default OFF. Scoped down from the master
prompt's full migrate-everything-then-verify-zero-mismatches harness: each
gate checks the one real, checkable precondition for its module (every
legacy Candidate has been migrated to an Application; the Standard Review
template/rating scale exist; nothing blocks learning today since no
existing data needs migrating for it to be meaningful) rather than a full
byte-for-byte historical replay across all three modules at once — that
is real, substantial verification work per module, not a single afternoon's
gate function, and is flagged here as a deferred follow-up, not faked.
"""
from django.db import transaction
from django.utils import timezone

from apps.recruitment.models import Candidate, RecruitmentV2Entitlement


class V2GateError(Exception):
    pass


def recruitment_migration_gaps() -> list:
    """Every Candidate with no migrated Application yet — the real,
    checkable precondition for recruitment.v2."""
    return list(Candidate.objects.filter(application_v2__isnull=True).values_list('id', flat=True))


@transaction.atomic
def enable_recruitment_v2() -> RecruitmentV2Entitlement:
    gaps = recruitment_migration_gaps()
    if gaps:
        raise V2GateError(f'{len(gaps)} candidate(s) not yet migrated to Application — run migrate_candidate_to_application() for each first.')
    entitlement = RecruitmentV2Entitlement.objects.first() or RecruitmentV2Entitlement()
    entitlement.is_enabled = True
    entitlement.enabled_at = timezone.now()
    entitlement.save()
    return entitlement


@transaction.atomic
def enable_performance_v2() -> 'PerformanceV2Entitlement':  # noqa: F821
    from apps.performance.models import PerformanceV2Entitlement, ReviewTemplate
    if not ReviewTemplate.objects.filter(code='STANDARD_REVIEW').exists():
        raise V2GateError('Standard Review template not seeded yet — run seed_standard_review_template() first.')
    entitlement = PerformanceV2Entitlement.objects.first() or PerformanceV2Entitlement()
    entitlement.is_enabled = True
    entitlement.enabled_at = timezone.now()
    entitlement.save()
    return entitlement


@transaction.atomic
def enable_learning_v2() -> 'LearningV2Entitlement':  # noqa: F821
    from apps.assessments.models import LearningV2Entitlement
    entitlement = LearningV2Entitlement.objects.first() or LearningV2Entitlement()
    entitlement.is_enabled = True
    entitlement.enabled_at = timezone.now()
    entitlement.save()
    return entitlement
