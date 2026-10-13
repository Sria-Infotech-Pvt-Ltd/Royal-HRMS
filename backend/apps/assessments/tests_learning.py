"""Phase 8A Task D — AssessmentItem->Question migration (exact), scoring, mandatory training due dates, v2 gate."""
import datetime

from django.test import TestCase

from apps.accounts.factories import make_role, make_user
from apps.assessments.models import (
    Assessment, AssessmentItem, Course, CourseSession, Enrolment, MandatoryTrainingPolicy,
)
from apps.assessments.services_learning import (
    migrate_assessment_item_to_question, resolve_mandatory_training_due_date,
    score_multiple_choice, score_single_choice,
)
from apps.recruitment.services_v2_flags import enable_learning_v2

_seq = [0]


def _unique(prefix):
    _seq[0] += 1
    return f'{prefix}{_seq[0]:04d}'


def _make_employee():
    role = make_role(_unique('role'))
    return make_user(f'{_unique("user")}@example.com', role=role, password='TestPass123!', date_of_joining=datetime.date(2026, 1, 1))


class QuestionMigrationTests(TestCase):
    def test_migrates_options_and_correct_answer_exactly(self):
        assessment = Assessment.objects.create(title=_unique('Assessment'))
        item = AssessmentItem.objects.create(
            assessment=assessment, item_type='quiz', question='2 + 2 = ?',
            option_a='3', option_b='4', option_c='5', option_d='6', correct_option='b',
        )
        question = migrate_assessment_item_to_question(item)
        self.assertEqual(question.text, '2 + 2 = ?')
        options = {o.text: o.is_correct for o in question.options.all()}
        self.assertEqual(options, {'3': False, '4': True, '5': False, '6': False})

    def test_video_items_are_not_migrated(self):
        assessment = Assessment.objects.create(title=_unique('Assessment'))
        item = AssessmentItem.objects.create(assessment=assessment, item_type='video', video_url='https://example.com/v.mp4')
        self.assertIsNone(migrate_assessment_item_to_question(item))

    def test_migration_is_idempotent(self):
        assessment = Assessment.objects.create(title=_unique('Assessment'))
        item = AssessmentItem.objects.create(
            assessment=assessment, item_type='quiz', question='Q?', option_a='A', option_b='B', correct_option='a',
        )
        first = migrate_assessment_item_to_question(item)
        second = migrate_assessment_item_to_question(item)
        self.assertEqual(first.id, second.id)


class ScoringTests(TestCase):
    def test_single_choice_correct_and_incorrect(self):
        assessment = Assessment.objects.create(title=_unique('Assessment'))
        item = AssessmentItem.objects.create(
            assessment=assessment, item_type='quiz', question='Q?', option_a='A', option_b='B', correct_option='b',
        )
        question = migrate_assessment_item_to_question(item)
        correct_option = question.options.get(is_correct=True)
        wrong_option = question.options.get(is_correct=False)
        self.assertTrue(score_single_choice(question, correct_option.id))
        self.assertFalse(score_single_choice(question, wrong_option.id))

    def test_multiple_choice_requires_exact_set_match(self):
        from apps.assessments.models import Question, QuestionOption
        question = Question.objects.create(question_type=Question.TYPE_MULTIPLE_CHOICE, text='Pick all even numbers')
        opt2 = QuestionOption.objects.create(question=question, text='2', is_correct=True, order=0)
        opt3 = QuestionOption.objects.create(question=question, text='3', is_correct=False, order=1)
        opt4 = QuestionOption.objects.create(question=question, text='4', is_correct=True, order=2)

        self.assertTrue(score_multiple_choice(question, {opt2.id, opt4.id}))
        self.assertFalse(score_multiple_choice(question, {opt2.id}))  # missing opt4
        self.assertFalse(score_multiple_choice(question, {opt2.id, opt3.id, opt4.id}))  # extra wrong one


class MandatoryTrainingTests(TestCase):
    def test_due_date_resolved_from_joining_date(self):
        course = Course.objects.create(code=_unique('CRS'), title='Security Awareness')
        policy = MandatoryTrainingPolicy.objects.create(course=course, due_days_after_joining=30)
        employee = _make_employee()
        due_date = resolve_mandatory_training_due_date(policy, employee)
        self.assertEqual(due_date, datetime.date(2026, 1, 31))

    def test_compliance_report_separates_compliant_and_overdue(self):
        course = Course.objects.create(code=_unique('CRS'), title='Security Awareness')
        session = CourseSession.objects.create(course=course, start_at=datetime.datetime(2026, 1, 1, 9, 0))
        employee_done = _make_employee()
        employee_overdue = _make_employee()
        Enrolment.objects.create(employee=employee_done, session=session, is_mandatory=True, status=Enrolment.STATUS_COMPLETED)
        Enrolment.objects.create(employee=employee_overdue, session=session, is_mandatory=True, due_date=datetime.date(2020, 1, 1))

        from apps.assessments.services_learning import compliance_report
        policy = MandatoryTrainingPolicy.objects.create(course=course, due_days_after_joining=30)
        report = compliance_report(policy)
        self.assertIn(employee_done.id, report['compliant'])
        self.assertIn(employee_overdue.id, report['overdue'])


class LearningV2GateTests(TestCase):
    def test_gate_enables(self):
        entitlement = enable_learning_v2()
        self.assertTrue(entitlement.is_enabled)
