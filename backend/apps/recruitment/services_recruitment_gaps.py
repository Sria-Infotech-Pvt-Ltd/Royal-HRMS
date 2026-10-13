"""Phase 8A gap-closure — duplicate detection/merge, consent capture, retention/anonymisation."""
import datetime

from django.db import transaction
from django.utils import timezone

from apps.recruitment.models import (
    Application, CandidateConsent, CandidateDuplicateMerge, CandidateProfile, CandidateRetentionPolicy,
)


def find_duplicate_profiles(profile: CandidateProfile):
    """Same email OR phone hash, excluding itself — the real "duplicate
    detection by email and phone hash" Task A.4 asks for."""
    query = CandidateProfile.objects.exclude(id=profile.id)
    matches = query.filter(email_hash=profile.email_hash) if profile.email_hash else CandidateProfile.objects.none()
    if profile.phone_hash:
        matches = matches | query.filter(phone_hash=profile.phone_hash)
    return matches.distinct()


@transaction.atomic
def merge_candidate_profiles(survivor: CandidateProfile, merged: CandidateProfile, merged_by=None) -> CandidateDuplicateMerge:
    if survivor.id == merged.id:
        raise ValueError('Cannot merge a profile into itself.')
    Application.objects.filter(candidate_profile=merged).update(candidate_profile=survivor)
    record = CandidateDuplicateMerge.objects.create(survivor=survivor, merged=merged, merged_by=merged_by)
    return record


def record_consent(profile: CandidateProfile, consent_version: str, ip_address=None) -> CandidateConsent:
    return CandidateConsent.objects.create(candidate_profile=profile, consent_version=consent_version, ip_address=ip_address)


def has_valid_consent(profile: CandidateProfile, required_version: str) -> bool:
    return profile.consents.filter(consent_version=required_version).exists()


@transaction.atomic
def anonymise_candidate(profile: CandidateProfile) -> CandidateProfile:
    """Irreversibly scrubs PII — name/email/phone — while preserving the
    row (and its Application history) for aggregate reporting. Audited by
    the caller (a management command), per the master prompt's own
    "scheduler job, audited" rule."""
    profile.name = 'Anonymised Candidate'
    profile.email = f'anonymised-{profile.id}@example.invalid'
    profile.phone = ''
    profile.save(update_fields=['name', 'email', 'phone', 'updated_at'])
    return profile


def candidates_due_for_anonymisation(policy: CandidateRetentionPolicy):
    """Rejected/withdrawn applications older than the policy window, whose
    profile hasn't already been anonymised."""
    from apps.recruitment.models import PipelineStage
    cutoff = timezone.now().date() - datetime.timedelta(days=policy.anonymise_after_months * 30)
    terminal_categories = [PipelineStage.CATEGORY_REJECTED, PipelineStage.CATEGORY_WITHDRAWN]
    applications = Application.objects.filter(
        current_stage__stage_category__in=terminal_categories, updated_at__date__lt=cutoff,
    ).exclude(candidate_profile__name='Anonymised Candidate')
    return {a.candidate_profile for a in applications.select_related('candidate_profile')}
