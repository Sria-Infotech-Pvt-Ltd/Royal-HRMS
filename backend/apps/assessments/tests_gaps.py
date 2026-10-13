"""Phase 8A gap-closure tests — numeric/ordering/matching scoring, manual grading, pool randomisation (seeded), proctoring flags."""
import random

from django.test import TestCase

from apps.accounts.factories import make_role, make_user
from apps.assessments.models import (
    Assessment, AssessmentItem, CandidateAssignment, CandidateResponse, Question, QuestionOption, QuestionPool,
)
from apps.assessments.services_learning import migrate_assessment_item_to_question
from apps.assessments.services_learning_gaps import (
    draw_from_pool, grade_manually, queue_for_manual_grading, report_proctoring_flag,
    requires_manual_grading, score_matching, score_numeric, score_ordering,
)

_seq = [0]


def _unique(prefix):
    _seq[0] += 1
    return f'{prefix}{_seq[0]:04d}'


def _make_employee():
    role = make_role(_unique('role'))
    return make_user(f'{_unique("user")}@example.com', role=role, password='TestPass123!')


class NumericScoringTests(TestCase):
    def test_within_tolerance_is_correct(self):
        question = Question.objects.create(question_type=Question.TYPE_NUMERIC, text='Value of pi to 2dp?')
        QuestionOption.objects.create(question=question, text='3.14', is_correct=True, order=0)
        self.assertTrue(score_numeric(question, '3.14', tolerance=0))
        self.assertTrue(score_numeric(question, 3.15, tolerance=0.01))
        self.assertFalse(score_numeric(question, 3.20, tolerance=0.01))


class OrderingScoringTests(TestCase):
    def test_correct_order_scores_true(self):
        question = Question.objects.create(question_type=Question.TYPE_ORDERING, text='Order these steps')
        opt1 = QuestionOption.objects.create(question=question, text='First', order=0)
        opt2 = QuestionOption.objects.create(question=question, text='Second', order=1)
        opt3 = QuestionOption.objects.create(question=question, text='Third', order=2)
        self.assertTrue(score_ordering(question, [opt1.id, opt2.id, opt3.id]))
        self.assertFalse(score_ordering(question, [opt2.id, opt1.id, opt3.id]))


class MatchingScoringTests(TestCase):
    def test_correct_pairs_score_true(self):
        question = Question.objects.create(question_type=Question.TYPE_MATCHING, text='Match capitals')
        left1 = QuestionOption.objects.create(question=question, text='India', order=0)
        right1 = QuestionOption.objects.create(question=question, text='Delhi', order=0)
        left2 = QuestionOption.objects.create(question=question, text='France', order=1)
        right2 = QuestionOption.objects.create(question=question, text='Paris', order=1)

        correct = {str(left1.id): str(right1.id), str(left2.id): str(right2.id)}
        wrong = {str(left1.id): str(right2.id), str(left2.id): str(right1.id)}
        self.assertTrue(score_matching(question, correct))
        self.assertFalse(score_matching(question, wrong))


class ManualGradingTests(TestCase):
    def test_short_text_requires_manual_grading(self):
        question = Question.objects.create(question_type=Question.TYPE_SHORT_TEXT, text='Describe X.')
        self.assertTrue(requires_manual_grading(question))

        mcq = Question.objects.create(question_type=Question.TYPE_SINGLE_CHOICE, text='Pick one')
        self.assertFalse(requires_manual_grading(mcq))

    def test_queue_and_grade(self):
        assessment = Assessment.objects.create(title=_unique('Assessment'))
        item = AssessmentItem.objects.create(assessment=assessment, item_type='quiz', question='Explain.')
        employee = _make_employee()
        assignment = CandidateAssignment.objects.create(employee=employee, assessment=assessment)
        response = CandidateResponse.objects.create(assignment=assignment, item=item, selected_option='')

        task = queue_for_manual_grading(response)
        self.assertEqual(task.status, task.STATUS_PENDING)

        grader = _make_employee()
        grade_manually(task, 8, 'Solid answer.', grader)
        task.refresh_from_db()
        self.assertEqual(task.status, task.STATUS_GRADED)
        self.assertEqual(task.score_awarded, 8)


class QuestionPoolTests(TestCase):
    def test_seeded_rng_is_deterministic(self):
        for i in range(5):
            Question.objects.create(question_type=Question.TYPE_SINGLE_CHOICE, text=f'Q{i}', tags=['python'])
        pool = QuestionPool.objects.create(code=_unique('POOL'), tag='python', pick_count=3)

        drawn_a = draw_from_pool(pool, rng=random.Random(42))
        drawn_b = draw_from_pool(pool, rng=random.Random(42))
        self.assertEqual([q.id for q in drawn_a], [q.id for q in drawn_b])

    def test_insufficient_questions_raises(self):
        Question.objects.create(question_type=Question.TYPE_SINGLE_CHOICE, text='Q1', tags=['rare_tag'])
        pool = QuestionPool.objects.create(code=_unique('POOL'), tag='rare_tag', pick_count=5)
        with self.assertRaises(ValueError):
            draw_from_pool(pool, rng=random.Random(1))


class ProctoringTests(TestCase):
    def test_flag_count_increments_on_repeat(self):
        assessment = Assessment.objects.create(title=_unique('Assessment'))
        employee = _make_employee()
        assignment = CandidateAssignment.objects.create(employee=employee, assessment=assessment)
        report_proctoring_flag(assignment, 'tab_switch')
        flag = report_proctoring_flag(assignment, 'tab_switch')
        self.assertEqual(flag.count, 2)
