"""
Phase 8A gap-closure pass — duplicate detection/merge, public careers
endpoint data, candidate consent/retention, continuous feedback is in
performance (see models_v2b there); this file covers recruitment-side
closures only.
"""
import uuid

from django.db import models


class CandidateDuplicateMerge(models.Model):
    """Audit record of a merge — `survivor` keeps its id, `merged`'s
    applications are reassigned to `survivor` by services_recruitment_gaps
    .merge_candidate_profiles(), then `merged` is marked inactive (never
    deleted — keeps every historical FK intact)."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    survivor = models.ForeignKey('recruitment.CandidateProfile', on_delete=models.CASCADE, related_name='absorbed_merges')
    merged = models.ForeignKey('recruitment.CandidateProfile', on_delete=models.CASCADE, related_name='merge_record')
    merged_by = models.ForeignKey('accounts.User', on_delete=models.SET_NULL, null=True, blank=True, related_name='candidate_merges_performed')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'recruitment_candidate_duplicate_merges_v2'

    def __str__(self):
        return f'{self.merged_id} -> {self.survivor_id}'


class CandidateConsent(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    candidate_profile = models.ForeignKey('recruitment.CandidateProfile', on_delete=models.CASCADE, related_name='consents')
    consent_version = models.CharField(max_length=20)
    consented_at = models.DateTimeField(auto_now_add=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)

    class Meta:
        db_table = 'recruitment_candidate_consents_v2'
        ordering = ['-consented_at']

    def __str__(self):
        return f'{self.candidate_profile_id} v{self.consent_version}'


class CandidateRetentionPolicy(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    legal_entity = models.ForeignKey('platform_core.LegalEntity', on_delete=models.CASCADE, null=True, blank=True, related_name='candidate_retention_policies')
    anonymise_after_months = models.PositiveSmallIntegerField(default=24)
    is_active = models.BooleanField(default=False, help_text='Default OFF — an admin opts in explicitly before the scheduler job anonymises anyone.')

    class Meta:
        db_table = 'recruitment_candidate_retention_policies_v2'

    def __str__(self):
        return f'Retention: {self.anonymise_after_months} months'
