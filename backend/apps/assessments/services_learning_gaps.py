"""Phase 8A gap-closure — scoring for the remaining question types, manual grading queue, pool randomisation (seeded RNG), proctoring flag capture."""
import random

from django.db import transaction

from apps.assessments.models import ManualGradingTask, ProctoringFlag, Question, QuestionPool


def score_numeric(question: Question, submitted_value, tolerance=0) -> bool:
    correct_option = question.options.filter(is_correct=True).first()
    if correct_option is None:
        return False
    try:
        correct_value = float(correct_option.text)
        submitted = float(submitted_value)
    except (TypeError, ValueError):
        return False
    return abs(submitted - correct_value) <= tolerance


def score_ordering(question: Question, submitted_order: list) -> bool:
    """submitted_order is a list of option ids in the order the candidate
    placed them; correct order is QuestionOption.order ascending."""
    correct_order = list(question.options.order_by('order').values_list('id', flat=True))
    submitted_ids = [str(i) for i in submitted_order]
    return [str(i) for i in correct_order] == submitted_ids


def score_matching(question: Question, submitted_pairs: dict) -> bool:
    """submitted_pairs: {left_option_id: right_option_id}. Correct pairing
    is encoded as options sharing the same `order` value (left/right pairs
    given the same order number) — reuses the existing options table
    rather than inventing a second child model for matching pairs."""
    options_by_order = {}
    for option in question.options.all():
        options_by_order.setdefault(option.order, []).append(str(option.id))
    correct_pairs = {pair[0]: pair[1] for pair in options_by_order.values() if len(pair) == 2}
    submitted = {str(k): str(v) for k, v in submitted_pairs.items()}
    return correct_pairs == submitted


def requires_manual_grading(question: Question) -> bool:
    return question.question_type in (Question.TYPE_SHORT_TEXT, Question.TYPE_LONG_TEXT)


def queue_for_manual_grading(response) -> ManualGradingTask:
    task, _ = ManualGradingTask.objects.get_or_create(response=response, defaults={'free_text_answer': response.selected_option or ''})
    return task


def grade_manually(task: ManualGradingTask, score_awarded: int, grader_comment: str, graded_by) -> ManualGradingTask:
    from django.utils import timezone
    task.score_awarded = score_awarded
    task.grader_comment = grader_comment
    task.graded_by = graded_by
    task.graded_at = timezone.now()
    task.status = ManualGradingTask.STATUS_GRADED
    task.save(update_fields=['score_awarded', 'grader_comment', 'graded_by', 'graded_at', 'status'])
    return task


def draw_from_pool(pool: QuestionPool, *, rng: random.Random | None = None) -> list:
    """Picks `pool.pick_count` random questions tagged `pool.tag`. Accepts
    an explicit `rng` (seeded) so tests can assert deterministic output,
    per the master prompt's own testing requirement — defaults to a fresh
    `random.Random()` (non-deterministic) when not supplied."""
    rng = rng or random.Random()
    candidates = list(Question.objects.filter(tags__contains=[pool.tag], is_active=True))
    if len(candidates) < pool.pick_count:
        raise ValueError(f'Pool {pool.code}: only {len(candidates)} active question(s) tagged {pool.tag!r}, need {pool.pick_count}.')
    return rng.sample(candidates, pool.pick_count)


def report_proctoring_flag(assignment, flag_type: str) -> ProctoringFlag:
    flag, created = ProctoringFlag.objects.get_or_create(assignment=assignment, flag_type=flag_type, defaults={'count': 1})
    if not created:
        flag.count += 1
        flag.save(update_fields=['count'])
    return flag
