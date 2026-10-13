"""Phase 8A gap-closure tests — continuous feedback, 360 anonymity threshold, goal alignment/weights, outcome->action approval gate."""
import datetime
from decimal import Decimal

from django.test import TestCase

from apps.accounts.factories import make_role, make_user
from apps.performance.models import FeedbackNote, Goal, PerformanceReview, ReviewCycle
from apps.performance.services_performance_gaps import (
    apply_outcome, give_feedback, nominate_peer, set_goal_alignment,
    submit_peer_feedback, validate_goal_weights_total_100, visible_360_feedback,
)

_seq = [0]


def _unique(prefix):
    _seq[0] += 1
    return f'{prefix}{_seq[0]:04d}'


def _make_employee():
    role = make_role(_unique('role'))
    return make_user(f'{_unique("user")}@example.com', role=role, password='TestPass123!')


def _make_cycle():
    return ReviewCycle.objects.create(
        name=_unique('Cycle'), period_start=datetime.date(2026, 1, 1), period_end=datetime.date(2026, 3, 31),
        self_review_due=datetime.date(2026, 2, 1), manager_review_due=datetime.date(2026, 2, 15),
    )


class ContinuousFeedbackTests(TestCase):
    def test_give_feedback_creates_note(self):
        employee = _make_employee()
        author = _make_employee()
        note = give_feedback(employee, author, 'Great work on the release.', note_type='praise', visibility=FeedbackNote.VISIBILITY_SHARED)
        self.assertEqual(note.employee_id, employee.id)
        self.assertEqual(note.visibility, FeedbackNote.VISIBILITY_SHARED)


class PeerFeedback360Tests(TestCase):
    def test_feedback_hidden_below_min_responders(self):
        cycle = _make_cycle()
        employee = _make_employee()
        peers = [_make_employee() for _ in range(3)]
        nominator = _make_employee()

        nominations = [nominate_peer(cycle, employee, peer, nominator) for peer in peers]
        submit_peer_feedback(nominations[0], {'q1': 'Good collaborator.'})

        visible = visible_360_feedback(employee, cycle, min_responders=3)
        self.assertEqual(visible, [])

    def test_feedback_visible_once_threshold_met(self):
        cycle = _make_cycle()
        employee = _make_employee()
        peers = [_make_employee() for _ in range(3)]
        nominator = _make_employee()

        nominations = [nominate_peer(cycle, employee, peer, nominator) for peer in peers]
        for nomination in nominations:
            submit_peer_feedback(nomination, {'q1': 'Good collaborator.'})

        visible = visible_360_feedback(employee, cycle, min_responders=3)
        self.assertEqual(len(visible), 3)

    def test_nomination_blocked_past_max_count(self):
        cycle = _make_cycle()
        employee = _make_employee()
        nominator = _make_employee()
        for _ in range(2):
            nominate_peer(cycle, employee, _make_employee(), nominator, max_count=2)
        with self.assertRaises(ValueError):
            nominate_peer(cycle, employee, _make_employee(), nominator, max_count=2)


class GoalCascadingTests(TestCase):
    def test_alignment_links_to_parent_goal(self):
        cycle = _make_cycle()
        employee = _make_employee()
        manager = _make_employee()
        org_goal = Goal.objects.create(employee=manager, cycle=cycle, title='Org goal')
        individual_goal = Goal.objects.create(employee=employee, cycle=cycle, title='Individual goal')

        alignment = set_goal_alignment(individual_goal, org_goal)
        self.assertEqual(alignment.parent_goal_id, org_goal.id)

    def test_cannot_align_goal_to_itself(self):
        cycle = _make_cycle()
        employee = _make_employee()
        goal = Goal.objects.create(employee=employee, cycle=cycle, title='Goal')
        with self.assertRaises(ValueError):
            set_goal_alignment(goal, goal)

    def test_weight_validation_requires_100_total(self):
        cycle = _make_cycle()
        employee = _make_employee()
        Goal.objects.create(employee=employee, cycle=cycle, title='A', weight_percent=60)
        Goal.objects.create(employee=employee, cycle=cycle, title='B', weight_percent=30)
        with self.assertRaises(ValueError):
            validate_goal_weights_total_100(employee, cycle)

        Goal.objects.create(employee=employee, cycle=cycle, title='C', weight_percent=10)
        validate_goal_weights_total_100(employee, cycle)  # now sums to 100, must not raise


class OutcomeActionTests(TestCase):
    def test_outcome_requires_approver(self):
        cycle = _make_cycle()
        employee = _make_employee()
        manager = _make_employee()
        review = PerformanceReview.objects.create(employee=employee, cycle=cycle, manager=manager)
        with self.assertRaises(ValueError):
            apply_outcome(review, approved_by=None, bonus_amount=Decimal('5000'))

    def test_outcome_creates_real_compensation_revision(self):
        cycle = _make_cycle()
        employee = _make_employee()
        manager = _make_employee()
        review = PerformanceReview.objects.create(employee=employee, cycle=cycle, manager=manager)

        outcome = apply_outcome(review, approved_by=manager, new_annual_ctc=Decimal('1500000'))
        self.assertIsNotNone(outcome.compensation_version)
        self.assertEqual(outcome.compensation_version.annual_ctc, Decimal('1500000'))

    def test_outcome_cannot_be_applied_twice(self):
        cycle = _make_cycle()
        employee = _make_employee()
        manager = _make_employee()
        review = PerformanceReview.objects.create(employee=employee, cycle=cycle, manager=manager)
        apply_outcome(review, approved_by=manager, bonus_amount=Decimal('1000'))
        with self.assertRaises(ValueError):
            apply_outcome(review, approved_by=manager, bonus_amount=Decimal('2000'))
