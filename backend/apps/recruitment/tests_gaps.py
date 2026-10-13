"""Phase 8A gap-closure tests — duplicate detection/merge, consent, retention, public careers endpoint."""
import datetime

from django.test import TestCase

from apps.accounts.factories import make_role, make_user
from apps.recruitment.models import CandidateProfile, CandidateRetentionPolicy, JobOpening, PipelineStage
from apps.recruitment.services_recruitment import (
    migrate_candidate_to_application, public_opening_data, seed_legacy_pipeline_template,
)
from apps.recruitment.services_recruitment_gaps import (
    anonymise_candidate, candidates_due_for_anonymisation, find_duplicate_profiles,
    has_valid_consent, merge_candidate_profiles, record_consent,
)

_seq = [0]


def _unique(prefix):
    _seq[0] += 1
    return f'{prefix}{_seq[0]:04d}'


def _make_employee():
    role = make_role(_unique('role'))
    return make_user(f'{_unique("user")}@example.com', role=role, password='TestPass123!')


class DuplicateDetectionTests(TestCase):
    def test_same_email_hash_is_flagged_duplicate(self):
        profile_a = CandidateProfile.objects.create(name='A', email='same@example.com')
        profile_b = CandidateProfile.objects.create(name='B', email='same@example.com')
        duplicates = find_duplicate_profiles(profile_a)
        self.assertIn(profile_b, duplicates)

    def test_different_email_and_phone_not_flagged(self):
        profile_a = CandidateProfile.objects.create(name='A', email='a@example.com', phone='1111111111')
        CandidateProfile.objects.create(name='B', email='b@example.com', phone='2222222222')
        duplicates = find_duplicate_profiles(profile_a)
        self.assertEqual(duplicates.count(), 0)

    def test_merge_reassigns_applications(self):
        survivor = CandidateProfile.objects.create(name='Survivor', email='survivor@example.com')
        merged = CandidateProfile.objects.create(name='Merged', email='merged@example.com')
        template = seed_legacy_pipeline_template()
        stage = PipelineStage.objects.get(template=template, code='applied')
        from apps.recruitment.models import Application
        application = Application.objects.create(candidate_profile=merged, current_stage=stage)

        merge_candidate_profiles(survivor, merged)
        application.refresh_from_db()
        self.assertEqual(application.candidate_profile_id, survivor.id)


class ConsentTests(TestCase):
    def test_consent_recorded_and_validated(self):
        profile = CandidateProfile.objects.create(name='A', email='a@example.com')
        self.assertFalse(has_valid_consent(profile, 'v1'))
        record_consent(profile, 'v1', ip_address='127.0.0.1')
        self.assertTrue(has_valid_consent(profile, 'v1'))
        self.assertFalse(has_valid_consent(profile, 'v2'))


class RetentionAnonymisationTests(TestCase):
    def test_anonymise_scrubs_pii(self):
        profile = CandidateProfile.objects.create(name='Real Name', email='real@example.com', phone='9999999999')
        anonymise_candidate(profile)
        profile.refresh_from_db()
        self.assertNotEqual(profile.name, 'Real Name')
        self.assertNotIn('real@example.com', profile.email)
        self.assertEqual(profile.phone, '')

    def test_due_for_anonymisation_finds_old_rejected_applications(self):
        from apps.hrms.models import ModuleV2Entitlement  # noqa: F401 -- ensures hrms app loaded for cross-app FK
        profile = CandidateProfile.objects.create(name='Old Rejected', email='old@example.com')
        template = seed_legacy_pipeline_template()
        rejected_stage = PipelineStage.objects.get(template=template, code='rejected')
        from apps.recruitment.models import Application
        application = Application.objects.create(candidate_profile=profile, current_stage=rejected_stage)
        old_date = datetime.datetime.now() - datetime.timedelta(days=800)
        Application.objects.filter(id=application.id).update(updated_at=old_date)

        policy = CandidateRetentionPolicy.objects.create(anonymise_after_months=24)
        due = candidates_due_for_anonymisation(policy)
        self.assertIn(profile, due)


class PublicCareersEndpointTests(TestCase):
    def test_unpublished_opening_returns_none(self):
        template = seed_legacy_pipeline_template()
        from apps.recruitment.models import JobRequisition
        from apps.accounts.models import OrgUnit, Position
        org_unit = OrgUnit.objects.create(name=_unique('Unit'))
        position = Position.objects.create(title=_unique('Role'), org_unit=org_unit)
        requisition = JobRequisition.objects.create(position=position)
        opening = JobOpening.objects.create(
            requisition=requisition, title='Engineer', pipeline_template=template, status=JobOpening.STATUS_DRAFT,
        )
        self.assertIsNone(public_opening_data(opening))

    def test_published_opening_returns_safe_fields_only(self):
        template = seed_legacy_pipeline_template()
        from apps.recruitment.models import JobRequisition
        from apps.accounts.models import OrgUnit, Position
        org_unit = OrgUnit.objects.create(name=_unique('Unit'))
        position = Position.objects.create(title=_unique('Role'), org_unit=org_unit)
        requisition = JobRequisition.objects.create(position=position)
        opening = JobOpening.objects.create(
            requisition=requisition, title='Engineer', description='x', pipeline_template=template,
            status=JobOpening.STATUS_PUBLISHED, is_internal_only=False,
        )
        data = public_opening_data(opening)
        self.assertEqual(data['title'], 'Engineer')
        self.assertNotIn('requisition', data)

    def test_internal_only_opening_not_public(self):
        template = seed_legacy_pipeline_template()
        from apps.recruitment.models import JobRequisition
        from apps.accounts.models import OrgUnit, Position
        org_unit = OrgUnit.objects.create(name=_unique('Unit'))
        position = Position.objects.create(title=_unique('Role'), org_unit=org_unit)
        requisition = JobRequisition.objects.create(position=position)
        opening = JobOpening.objects.create(
            requisition=requisition, title='Engineer', pipeline_template=template,
            status=JobOpening.STATUS_PUBLISHED, is_internal_only=True,
        )
        self.assertIsNone(public_opening_data(opening))
