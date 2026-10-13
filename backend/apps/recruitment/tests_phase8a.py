"""Phase 8A Task A/E — recruitment migration, scorecards, offer-to-hire conversion, v2 gate."""
import datetime
from decimal import Decimal

from django.test import TestCase

from apps.accounts.factories import make_role, make_user
from apps.accounts.models import HireAction, Position
from apps.recruitment.models import Candidate, Offer, PipelineStage, Scorecard, ScorecardTemplate
from apps.recruitment.services_recruitment import (
    migrate_candidate_to_application, submit_scorecard, unmigrated_legacy_openings,
    validate_scorecard_weights, visible_scorecards_for_round, convert_offer_to_hire_action,
)
from apps.recruitment.services_v2_flags import V2GateError, enable_recruitment_v2, recruitment_migration_gaps

_seq = [0]


def _unique(prefix):
    _seq[0] += 1
    return f'{prefix}{_seq[0]:04d}'


def _make_employee():
    role = make_role(_unique('role'))
    return make_user(f'{_unique("user")}@example.com', role=role, password='TestPass123!')


def _make_candidate(status='pending'):
    added_by = _make_employee()
    return Candidate.objects.create(
        name=_unique('Candidate'), email=f'{_unique("cand")}@example.com', position_applied='Engineer',
        status=status, added_by=added_by,
    )


class CandidateMigrationTests(TestCase):
    def test_migrate_creates_application_with_mapped_stage(self):
        candidate = _make_candidate(status='screening')
        application = migrate_candidate_to_application(candidate)
        self.assertEqual(application.current_stage.code, 'screening')
        self.assertEqual(application.candidate_profile.name, candidate.name)

    def test_migrate_is_idempotent(self):
        candidate = _make_candidate()
        first = migrate_candidate_to_application(candidate)
        second = migrate_candidate_to_application(candidate)
        self.assertEqual(first.id, second.id)

    def test_unmigrated_legacy_openings_reports_distinct_position_branch(self):
        _make_candidate()
        report = unmigrated_legacy_openings()
        self.assertIn(('Engineer', None), report)
        self.assertGreaterEqual(report[('Engineer', None)], 1)


class ScorecardTests(TestCase):
    def test_validate_weights_rejects_non_100_total(self):
        template = ScorecardTemplate.objects.create(
            code=_unique('SCT'), name='x', criteria=[{'criterion': 'Communication', 'weight': 50}],
        )
        with self.assertRaises(ValueError):
            validate_scorecard_weights(template)

    def test_validate_weights_accepts_100_total(self):
        template = ScorecardTemplate.objects.create(
            code=_unique('SCT'), name='x',
            criteria=[{'criterion': 'Communication', 'weight': 50}, {'criterion': 'Technical', 'weight': 50}],
        )
        validate_scorecard_weights(template)  # must not raise

    def test_submit_scorecard_requires_all_criteria_scored(self):
        template = ScorecardTemplate.objects.create(
            code=_unique('SCT'), name='x',
            criteria=[{'criterion': 'Communication', 'weight': 50}, {'criterion': 'Technical', 'weight': 50}],
        )
        candidate = _make_candidate()
        application = migrate_candidate_to_application(candidate)
        interviewer = _make_employee()
        from apps.recruitment.models import InterviewRound
        round_ = InterviewRound.objects.create(application=application, round_type='Tech', scheduled_start=datetime.datetime(2026, 4, 1, 10, 0))
        scorecard = Scorecard.objects.create(interview_round=round_, template=template, interviewer=interviewer, scores={'Communication': 8})
        with self.assertRaises(ValueError):
            submit_scorecard(scorecard)

        scorecard.scores = {'Communication': 8, 'Technical': 7}
        scorecard.save()
        submit_scorecard(scorecard)
        self.assertIsNotNone(scorecard.submitted_at)

    def test_blind_scoring_hides_others_until_all_submitted(self):
        template = ScorecardTemplate.objects.create(code=_unique('SCT'), name='x', criteria=[{'criterion': 'C', 'weight': 100}])
        candidate = _make_candidate()
        application = migrate_candidate_to_application(candidate)
        interviewer_a = _make_employee()
        interviewer_b = _make_employee()
        from apps.recruitment.models import InterviewRound
        round_ = InterviewRound.objects.create(application=application, round_type='Tech', scheduled_start=datetime.datetime(2026, 4, 1, 10, 0))
        scorecard_a = Scorecard.objects.create(interview_round=round_, template=template, interviewer=interviewer_a, scores={'C': 8})
        Scorecard.objects.create(interview_round=round_, template=template, interviewer=interviewer_b, scores={})

        submit_scorecard(scorecard_a)
        visible_to_a = visible_scorecards_for_round(round_, interviewer_a)
        self.assertEqual(len(visible_to_a), 1)  # B hasn't submitted yet — A sees only their own

        scorecard_b = round_.scorecards.get(interviewer=interviewer_b)
        scorecard_b.scores = {'C': 5}
        scorecard_b.save()
        submit_scorecard(scorecard_b)
        visible_to_a_now = visible_scorecards_for_round(round_, interviewer_a)
        self.assertEqual(len(visible_to_a_now), 2)  # both submitted — now visible


class OfferConversionTests(TestCase):
    def test_accepted_offer_converts_to_draft_hire_action(self):
        from apps.accounts.models import OrgUnit
        org_unit = OrgUnit.objects.create(name=_unique('Unit'))
        position = Position.objects.create(title=_unique('Role'), org_unit=org_unit)
        candidate = _make_candidate()
        application = migrate_candidate_to_application(candidate)
        creator = _make_employee()
        offer = Offer.objects.create(
            application=application, annual_ctc=Decimal('1200000'), joining_date=datetime.date(2026, 6, 1),
            position=position, status=Offer.STATUS_ACCEPTED, created_by=creator,
        )
        hire_action = convert_offer_to_hire_action(offer, creator)
        self.assertEqual(hire_action.position_id, position.id)
        self.assertEqual(hire_action.effective_from, datetime.date(2026, 6, 1))
        self.assertEqual(hire_action.status, HireAction.STATUS_DRAFT)

    def test_non_accepted_offer_cannot_convert(self):
        from apps.accounts.models import OrgUnit
        org_unit = OrgUnit.objects.create(name=_unique('Unit'))
        position = Position.objects.create(title=_unique('Role'), org_unit=org_unit)
        candidate = _make_candidate()
        application = migrate_candidate_to_application(candidate)
        creator = _make_employee()
        offer = Offer.objects.create(
            application=application, annual_ctc=Decimal('1200000'), joining_date=datetime.date(2026, 6, 1),
            position=position, status=Offer.STATUS_DRAFT, created_by=creator,
        )
        with self.assertRaises(ValueError):
            convert_offer_to_hire_action(offer, creator)


class RecruitmentV2GateTests(TestCase):
    def test_gate_blocks_with_unmigrated_candidates(self):
        _make_candidate()
        self.assertTrue(len(recruitment_migration_gaps()) > 0)
        with self.assertRaises(V2GateError):
            enable_recruitment_v2()

    def test_gate_passes_once_all_migrated(self):
        candidate = _make_candidate()
        migrate_candidate_to_application(candidate)
        entitlement = enable_recruitment_v2()
        self.assertTrue(entitlement.is_enabled)
