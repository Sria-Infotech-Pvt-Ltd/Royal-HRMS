"""
Assessment evaluation shared by the assessment portal (CandidateAssignment)
and Training & Learning (TrainingAssessmentAttempt) — one set of rules for
correct answers, section weighting and pass marks.
"""
from __future__ import annotations

from collections import defaultdict

VALID_OPTIONS = ('a', 'b', 'c', 'd')


def normalise_option(selected) -> str:
    return (selected or '').strip().lower() if isinstance(selected, str) else ''


def is_correct_answer(item, selected) -> bool:
    return normalise_option(selected) == item.correct_option


def section_weighted_score(sections, quiz_items, correct_ids) -> tuple[int, int]:
    """(achieved, max) when the assessment has sections: each section is worth
    its `score`, earned in proportion to its correct quiz items; quiz items
    outside any section are worth 1 each.

    sections:    AssessmentSection rows
    quiz_items:  [{'id': ..., 'section_id': ...}] for every quiz item
    correct_ids: ids of the quiz items answered correctly
    """
    section_map = {s.id: s for s in sections}
    section_items: dict = defaultdict(list)
    unsectioned = []

    for item in quiz_items:
        sid = item['section_id']
        if sid and sid in section_map:
            section_items[sid].append(item['id'])
        else:
            unsectioned.append(item['id'])

    achieved = 0
    max_total = 0
    for section_id, item_ids in section_items.items():
        section = section_map[section_id]
        correct   = sum(1 for iid in item_ids if iid in correct_ids)
        achieved  += round((correct / len(item_ids)) * section.score)
        max_total += section.score

    for iid in unsectioned:
        max_total += 1
        if iid in correct_ids:
            achieved += 1

    return achieved, max_total


def score_percentage(score: int, max_score: int) -> int:
    return round((score / max_score) * 100) if max_score else 100


def is_pass(score: int, max_score: int, pass_percentage: int) -> bool:
    return score_percentage(score, max_score) >= pass_percentage if max_score else True


def score_answers(assessment, answers: dict) -> dict:
    """Grade a full set of answers {item_id(str): 'a'..'d'} for `assessment`'s quiz items."""
    from apps.assessments.models import AssessmentItem
    items = list(assessment.items.filter(item_type=AssessmentItem.TYPE_QUIZ))
    correct_ids = frozenset(i.id for i in items if is_correct_answer(i, answers.get(str(i.id))))
    sections = list(assessment.sections.all())
    if sections:
        score, max_score = section_weighted_score(
            sections, [{'id': i.id, 'section_id': i.section_id} for i in items], correct_ids)
    else:
        score, max_score = len(correct_ids), len(items)
    return {
        'score': score, 'max_score': max_score, 'correct_count': len(correct_ids), 'question_count': len(items),
        'percentage': score_percentage(score, max_score),
        'passed': is_pass(score, max_score, assessment.pass_percentage),
    }
