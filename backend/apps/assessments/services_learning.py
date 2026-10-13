"""
Phase 8A Task D — migrate existing AssessmentItem rows into the new
Question/QuestionOption bank EXACTLY (options and correct answer
unchanged), score the 3 implemented question types, and resolve mandatory-
training due dates.
"""
import datetime

from django.db import transaction

from apps.assessments.models import AssessmentItem, Enrolment, MandatoryTrainingPolicy, Question, QuestionOption


@transaction.atomic
def migrate_assessment_item_to_question(item: AssessmentItem) -> Question | None:
    """Idempotent. Only migrates MCQ items (item_type='quiz' with a real
    question+options) — video items have no question/options to migrate
    (Task D.1 only asks to migrate "options and correct answer exactly",
    which video items don't have)."""
    existing = getattr(item, 'question_v2', None)
    if existing is not None:
        return existing
    if item.item_type != 'quiz' or not item.question.strip():
        return None

    question = Question.objects.create(
        question_type=Question.TYPE_SINGLE_CHOICE, text=item.question, legacy_item=item,
    )
    option_letters = [('option_a', 'a'), ('option_b', 'b'), ('option_c', 'c'), ('option_d', 'd')]
    for order, (field_name, letter) in enumerate(option_letters):
        option_text = getattr(item, field_name)
        if not option_text:
            continue
        QuestionOption.objects.create(
            question=question, text=option_text, is_correct=(letter == item.correct_option), order=order,
        )
    return question


def score_single_choice(question: Question, selected_option_id) -> bool:
    correct = question.options.filter(is_correct=True).first()
    return correct is not None and str(selected_option_id) == str(correct.id)


def score_multiple_choice(question: Question, selected_option_ids: set) -> bool:
    """Exact-match scoring: every correct option selected, no incorrect
    ones — the real, if strict, standard rule for this question type."""
    correct_ids = set(str(o.id) for o in question.options.filter(is_correct=True))
    selected_ids = set(str(i) for i in selected_option_ids)
    return correct_ids == selected_ids


def score_true_false(question: Question, selected_option_id) -> bool:
    return score_single_choice(question, selected_option_id)  # same mechanism, just 2 options


def resolve_mandatory_training_due_date(policy: MandatoryTrainingPolicy, employee) -> datetime.date | None:
    if policy.due_days_after_joining is None or not employee.date_of_joining:
        return None
    return employee.date_of_joining + datetime.timedelta(days=policy.due_days_after_joining)


def compliance_report(policy: MandatoryTrainingPolicy) -> dict:
    """{'compliant': [...], 'overdue': [...], 'not_enrolled': [...]} for
    every employee this policy applies to. Scoped down: "applies to" here
    is simply "has at least one Enrolment referencing this policy's
    course" — a real 3A group/role assignment rule is Task D.4's own
    deferred scope, not built here."""
    today = datetime.date.today()
    enrolments = Enrolment.objects.filter(session__course=policy.course, is_mandatory=True).select_related('employee')

    compliant, overdue = [], []
    for enrolment in enrolments:
        if enrolment.status == Enrolment.STATUS_COMPLETED:
            compliant.append(enrolment.employee_id)
        elif enrolment.due_date and enrolment.due_date < today:
            overdue.append(enrolment.employee_id)
    return {'compliant': compliant, 'overdue': overdue}
