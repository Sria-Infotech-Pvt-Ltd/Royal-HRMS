"""
Training & Learning rules.

Who sees whose training (employee_scope_q):
  * settings.edit / superuser                 → everyone in the company
  * training.view_all_progress (HR, branch admin) → their own branch (blank branch = company-wide)
  * a team manager with training.view          → their direct reports
  * anyone else                               → nobody (only their own, via the My Learning APIs)
Assigning (training.assign) is limited to the same scope.

Completion: every required, non-removed material is complete AND, when the
course links an assessment, the employee has passed it. Opening a page or a
file never completes anything:
  * videos with reliable playback events (uploaded, YouTube, direct .mp4/.webm):
    watched time — capped by real elapsed time, so seeking ahead doesn't count —
    reaches WATCH_REQUIRED_SHARE of the video;
  * documents: opened, then confirmed no sooner than the material's minimum time;
  * other videos (e.g. Vimeo): only when HR allows a "I have watched it" confirmation.
"""
from __future__ import annotations

import datetime
import logging
import math

from django.db import IntegrityError, transaction
from django.db.models import Max, Q
from django.utils import timezone

from core.permissions import has_perm

from apps.training.models import (
    TrainingAssessmentAttempt, TrainingAssignment, TrainingCourse, TrainingMaterial, TrainingMaterialProgress,
)

logger = logging.getLogger(__name__)

WATCH_REQUIRED_SHARE = 0.9
# Watched time grows at most at real-time speed (plus this small tolerance for network
# timing), updates closer together than MIN_HEARTBEAT_GAP_SECONDS are ignored, and the total
# never exceeds the real time since the video was first opened plus WATCH_TIME_SLACK_SECONDS.
WATCH_RATE_TOLERANCE = 1.05
MIN_HEARTBEAT_GAP_SECONDS = 2
WATCH_TIME_SLACK_SECONDS = 10
ATTEMPT_GRACE_SECONDS = 60           # submitting just after the time limit still counts
# After passing, an employee may retake the assessment to improve the score, using the
# attempts left under the assessment's limit — and never more than this many retakes
# (the cap that applies when the assessment allows unlimited attempts). The course stays
# completed and the best score is kept.
MAX_RETAKES_AFTER_PASS = 2


class TrainingError(Exception):
    def __init__(self, message: str, field: str = '', status: int = 400):
        super().__init__(message)
        self.field = field
        self.status = status


# ── Scope ─────────────────────────────────────────────────────────────────────

def _branch(user) -> str:
    return (getattr(user, 'branch', '') or '').strip()


def employee_scope_q(user) -> Q | None:
    """Q over User for the employees whose training `user` may see; None = nobody."""
    if getattr(user, 'is_superuser', False) or has_perm(user, 'settings.edit'):
        return Q()
    if has_perm(user, 'training.view_all_progress'):
        branch = _branch(user)
        return Q(branch__iexact=branch) if branch else Q()
    role = getattr(user, 'role', None)
    if role is not None and getattr(role, 'can_manage_team', False) and has_perm(user, 'training.view'):
        return Q(reporting_manager=user)
    return None


def assignment_scope_q(user) -> Q | None:
    """Same scope as employee_scope_q, over TrainingAssignment."""
    q = employee_scope_q(user)
    return None if q is None else _prefix(q, 'employee__')


def _prefix(q: Q, prefix: str) -> Q:
    out = Q()
    out.connector, out.negated = q.connector, q.negated
    for child in q.children:
        if isinstance(child, Q):
            out.children.append(_prefix(child, prefix))
        else:
            key, value = child
            out.children.append((prefix + key, value))
    return out


def scoped_employees(user):
    from apps.accounts.models import User
    q = employee_scope_q(user)
    if q is None:
        return User.objects.none()
    return User.objects.filter(q, is_active=True)


def can_manage_courses(user) -> bool:
    return any(has_perm(user, p) for p in ('training.create', 'training.edit', 'training.delete'))


# ── Assignment ────────────────────────────────────────────────────────────────

def _notify(user, title, message, notification_type, reference_id='', created_by=None):
    from apps.notifications.signals import _notify as notify
    notify(user, title, message, notification_type, 'training', reference_id, created_by)


def assign_course(course: TrainingCourse, employees, *, assigned_by=None, source=TrainingAssignment.SOURCE_INDIVIDUAL,
                  due_date=None) -> dict:
    """Create one assignment per employee who doesn't have this course yet."""
    if course.archived_at or not course.is_active:
        raise TrainingError('Only an active course can be assigned.')
    # A course deadline that has already passed is not used as the default due date —
    # the assignment would be overdue the moment it is created.
    due = due_date
    if due is None and course.deadline and course.deadline >= timezone.localdate():
        due = course.deadline
    created, skipped = [], 0
    for emp in employees:
        try:
            with transaction.atomic():
                a = TrainingAssignment.objects.create(course=course, employee=emp, assigned_by=assigned_by,
                                                      source=source, due_date=due)
        except IntegrityError:
            skipped += 1
            continue
        created.append(a)
    for a in created:
        when = f' Complete it by {a.due_date:%d %b %Y}.' if a.due_date else ''
        kind = 'mandatory ' if course.is_mandatory else ''
        _notify(a.employee, 'Training Assigned', f'You have been assigned the {kind}training "{course.title}".{when}',
                'training_assigned', str(a.pk), assigned_by)
    return {'assigned': len(created), 'already_assigned': skipped}


def assign_new_joiner(employee) -> int:
    """Courses marked for new joiners whose branch / department filters match `employee`."""
    from apps.tenants.access import module_enabled
    if not module_enabled('training'):
        return 0
    count = 0
    today = timezone.localdate()
    branch = (employee.branch or '').strip().lower()
    dept = (employee.department or '').strip().lower()
    for course in TrainingCourse.objects.filter(auto_assign_new_joiners=True, is_active=True, archived_at__isnull=True):
        branches = [b.strip().lower() for b in (course.new_joiner_branches or []) if b]
        depts = [d.strip().lower() for d in (course.new_joiner_departments or []) if d]
        if (branches and branch not in branches) or (depts and dept not in depts):
            continue
        # No "days" set: assign_course falls back to the course deadline (when not past).
        due = today + datetime.timedelta(days=course.new_joiner_deadline_days) \
            if course.new_joiner_deadline_days else None
        count += assign_course(course, [employee], source=TrainingAssignment.SOURCE_ONBOARDING, due_date=due)['assigned']
    return count


# ── Progress ──────────────────────────────────────────────────────────────────

def active_materials(course):
    return course.materials.filter(is_archived=False).order_by('order', 'created_at')


VIDEO_TYPES = (TrainingMaterial.TYPE_VIDEO, TrainingMaterial.TYPE_EXTERNAL_VIDEO)


def material_required(course, material) -> bool:
    """Does this material have to be completed (course.videos_optional excuses videos)?"""
    return material.is_required and not (course.videos_optional and material.material_type in VIDEO_TYPES)


def required_material_ids(course) -> set:
    qs = active_materials(course).filter(is_required=True)
    if course.videos_optional:
        qs = qs.exclude(material_type__in=VIDEO_TYPES)
    return set(qs.values_list('id', flat=True))


def starts_on(assignment) -> datetime.date | None:
    """The course start date while it is still in the future (the course is not open yet)."""
    start = assignment.course.start_date
    return start if start and start > timezone.localdate() else None


def _check_open(assignment):
    start = starts_on(assignment)
    if start:
        raise TrainingError(f'This course starts on {start:%d %b %Y}.', status=409)


def _progress(assignment, material) -> TrainingMaterialProgress:
    p, _ = TrainingMaterialProgress.objects.get_or_create(assignment=assignment, material=material)
    return p


def _mark_started(assignment):
    if assignment.status == TrainingAssignment.STATUS_ASSIGNED:
        assignment.status = TrainingAssignment.STATUS_IN_PROGRESS
        assignment.started_at = assignment.started_at or timezone.now()
        assignment.save(update_fields=['status', 'started_at', 'updated_at'])


def record_open(assignment, material) -> TrainingMaterialProgress:
    _check_open(assignment)
    p = _progress(assignment, material)
    if p.opened_at is None:
        p.opened_at = timezone.now()
        p.save(update_fields=['opened_at', 'updated_at'])
    _mark_started(assignment)
    return p


def _complete(p: TrainingMaterialProgress, method: str):
    if p.completed_at is None:
        p.completed_at, p.completion_method = timezone.now(), method
        p.save(update_fields=['completed_at', 'completion_method', 'updated_at'])


def record_heartbeat(assignment, material, position: float, duration: float | None = None) -> TrainingMaterialProgress:
    """Playback report from the player. Watched time only grows at real-time speed:
    updates sent too close together are ignored, each update adds no more than the real
    time since the previous one, and the total never exceeds the time since the video was
    first opened. The video length comes only from HR (material.duration_seconds) — the
    length reported by the browser (`duration`) is ignored."""
    if not material.is_tracked:
        raise TrainingError('Playback of this video cannot be tracked.')
    _check_open(assignment)
    now = timezone.now()
    p = _progress(assignment, material)
    if p.last_heartbeat_at is not None and \
            (now - p.last_heartbeat_at).total_seconds() < MIN_HEARTBEAT_GAP_SECONDS:
        return p                                         # too soon after the previous update
    if p.opened_at is None:
        p.opened_at = now
    position = float(position or 0)
    position = max(0.0, position) if math.isfinite(position) else 0.0
    known = float(material.duration_seconds) if material.duration_seconds else None
    if known:
        position = min(position, known)
    if p.last_heartbeat_at is not None and position > p.last_position_seconds:
        elapsed = (now - p.last_heartbeat_at).total_seconds()
        p.watched_seconds += min(position - p.last_position_seconds, elapsed * WATCH_RATE_TOLERANCE)
    p.watched_seconds = min(p.watched_seconds,
                            (now - p.opened_at).total_seconds() + WATCH_TIME_SLACK_SECONDS)
    p.last_position_seconds, p.last_heartbeat_at = position, now
    if known:
        p.watched_seconds = min(p.watched_seconds, known)
    p.save()
    _mark_started(assignment)
    if known and p.completed_at is None and p.watched_seconds >= WATCH_REQUIRED_SHARE * float(known):
        _complete(p, TrainingMaterialProgress.METHOD_TRACKED)
        refresh_status(assignment)
    return p


def confirm_material(assignment, material) -> TrainingMaterialProgress:
    """Document read / untracked video watched — only after it was opened."""
    _check_open(assignment)
    p = _progress(assignment, material)
    if p.completed_at:
        return p
    if p.opened_at is None:
        raise TrainingError('Open the material first.')
    if material.material_type == TrainingMaterial.TYPE_DOCUMENT:
        waited = (timezone.now() - p.opened_at).total_seconds()
        if waited < material.min_view_seconds:
            left = int(material.min_view_seconds - waited) + 1
            raise TrainingError(f'Please spend a little longer on this document ({left} s left).')
        _complete(p, TrainingMaterialProgress.METHOD_READ)
    elif material.is_tracked:
        raise TrainingError('This video completes automatically once you have watched it.')
    elif not material.allow_manual_completion:
        raise TrainingError('This video cannot be confirmed — contact HR.')
    else:
        _complete(p, TrainingMaterialProgress.METHOD_CONFIRMED)
    refresh_status(assignment)
    return p


def materials_complete(assignment) -> bool:
    required = required_material_ids(assignment.course)
    done = set(assignment.material_progress.filter(completed_at__isnull=False, material_id__in=required)
               .values_list('material_id', flat=True))
    return required <= done


def refresh_status(assignment) -> str:
    """Recompute completed / failed after progress or an attempt."""
    if assignment.status in (TrainingAssignment.STATUS_COMPLETED, TrainingAssignment.STATUS_FAILED):
        return assignment.status
    course = assignment.course
    if not materials_complete(assignment):
        return assignment.status
    if course.assessment_id and not assignment.assessment_passed:
        return assignment.status
    assignment.status = TrainingAssignment.STATUS_COMPLETED
    assignment.completed_at = timezone.now()
    assignment.started_at = assignment.started_at or assignment.completed_at
    assignment.save(update_fields=['status', 'completed_at', 'started_at', 'updated_at'])
    _notify(assignment.employee, 'Training Completed', f'You completed the training "{course.title}".',
            'training_completed', str(assignment.pk))
    return assignment.status


# ── Assessment (reuses apps.assessments) ──────────────────────────────────────

def _assessment_limits(assessment) -> tuple[int, int | None]:
    from apps.assessments.models import AssessmentSettings
    cfg = AssessmentSettings.load()
    return assessment.effective_max_attempts(cfg), assessment.effective_time_limit_mins(cfg)


def assessment_state(assignment) -> dict:
    course = assignment.course
    a = course.assessment
    if a is None:
        return {'required': False}
    from apps.assessments.models import AssessmentItem
    max_attempts, time_limit = _assessment_limits(a)
    unlocked = materials_complete(assignment)
    # An assessment without questions can never be taken (it would score 100% and "pass").
    has_questions = a.items.filter(item_type=AssessmentItem.TYPE_QUIZ).exists()
    start = starts_on(assignment)
    left = None if max_attempts == 0 else max(0, max_attempts - assignment.attempts_used)
    retakes_left = None
    if assignment.assessment_passed:
        retakes_left = max(0, MAX_RETAKES_AFTER_PASS - retakes_used(assignment))
        left = retakes_left if left is None else min(left, retakes_left)
    can_attempt = (unlocked and has_questions and start is None and (left is None or left > 0)
                   and assignment.status != TrainingAssignment.STATUS_FAILED)
    last = assignment.attempts.filter(submitted_at__isnull=False).first()
    return {
        'required': True, 'title': a.title, 'pass_percentage': a.pass_percentage,
        'max_attempts': max_attempts, 'attempts_used': assignment.attempts_used, 'attempts_left': left,
        'time_limit_mins': time_limit, 'unlocked': unlocked, 'can_attempt': can_attempt,
        'has_questions': has_questions, 'starts_on': start.isoformat() if start else None,
        'passed': assignment.assessment_passed, 'best_score_percent': assignment.best_score_percent,
        'can_retake': bool(assignment.assessment_passed and can_attempt),
        'last_result': ({'percentage': last.percentage, 'passed': last.passed, 'score': last.score,
                         'max_score': last.max_score, 'submitted_at': last.submitted_at.isoformat()}
                        if last else None),
    }


def start_attempt(assignment) -> tuple[TrainingAssessmentAttempt, list]:
    from apps.assessments.models import AssessmentItem
    state = assessment_state(assignment)
    if not state.get('required'):
        raise TrainingError('This course has no assessment.')
    _check_open(assignment)
    if not state['has_questions']:
        raise TrainingError('This assessment has no questions yet — contact HR.', status=409)
    if not state['unlocked']:
        raise TrainingError('Complete the required learning materials first.')
    if not state['can_attempt']:
        raise TrainingError('No attempts left for this assessment.' if not assignment.assessment_passed
                            else 'You have already passed and used all your retakes.', status=409)
    a = assignment.course.assessment
    with transaction.atomic():
        open_attempt = assignment.attempts.select_for_update().filter(submitted_at__isnull=True).first()
        if open_attempt is None:
            last_no = assignment.attempts.aggregate(n=Max('attempt_number'))['n'] or 0
            open_attempt = TrainingAssessmentAttempt.objects.create(
                assignment=assignment, assessment=a, attempt_number=last_no + 1, pass_percentage=a.pass_percentage)
        attempt = open_attempt
    items = a.items.filter(item_type=AssessmentItem.TYPE_QUIZ).select_related('section').order_by(
        'section__order', 'order', 'created_at')
    questions = [{
        'id': str(i.id), 'question': i.question or i.title, 'section': i.section.title if i.section_id else '',
        'options': [{'key': k, 'text': getattr(i, f'option_{k}')} for k in ('a', 'b', 'c', 'd')
                    if getattr(i, f'option_{k}')],
    } for i in items]
    return attempt, questions


def submit_attempt(assignment, answers: dict) -> TrainingAssessmentAttempt:
    from apps.assessments.scoring import score_answers
    if not isinstance(answers, dict):
        raise TrainingError('Answers must be an object of question id → option.', 'answers')
    with transaction.atomic():
        attempt = assignment.attempts.select_for_update().filter(submitted_at__isnull=True).first()
        if attempt is None:
            raise TrainingError('Start the assessment first.', status=409)
        a = attempt.assessment or assignment.course.assessment
        if a is None:
            raise TrainingError('This course no longer has an assessment.', status=409)
        _max_attempts, time_limit = _assessment_limits(a)
        late = bool(time_limit) and (
            (timezone.now() - attempt.started_at).total_seconds() > time_limit * 60 + ATTEMPT_GRACE_SECONDS)
        clean = {str(k): str(v).strip().lower() for k, v in answers.items() if isinstance(v, str)}
        result = score_answers(a, {} if late else clean)
        if not result['question_count']:
            raise TrainingError('This assessment has no questions yet — contact HR.', status=409)
        attempt.answers = clean
        attempt.score, attempt.max_score = result['score'], result['max_score']
        attempt.percentage, attempt.passed = result['percentage'], (result['passed'] and not late)
        attempt.pass_percentage = a.pass_percentage
        attempt.submitted_at = timezone.now()
        attempt.save()

        assignment.attempts_used += 1
        assignment.best_score_percent = max(assignment.best_score_percent or 0, attempt.percentage)
        was_passed = bool(assignment.assessment_passed)
        if attempt.passed:
            assignment.assessment_passed = True
        elif not was_passed:
            # A lower retake after passing never undoes the pass.
            max_attempts, _ = _assessment_limits(a)
            assignment.assessment_passed = False
            if max_attempts and assignment.attempts_used >= max_attempts:
                assignment.status = TrainingAssignment.STATUS_FAILED
        assignment.save(update_fields=['attempts_used', 'best_score_percent', 'assessment_passed', 'status',
                                       'updated_at'])
    if was_passed:
        message = (f'Retake of the assessment for "{assignment.course.title}": {attempt.percentage}%. '
                   f'Your best score is {assignment.best_score_percent}% and the course stays completed.')
    else:
        outcome = 'passed' if attempt.passed else ('did not pass' + (' — the time limit was exceeded' if late else ''))
        message = (f'You {outcome} the assessment for "{assignment.course.title}" ({attempt.percentage}%, '
                   f'pass mark {attempt.pass_percentage}%).')
    _notify(assignment.employee, 'Assessment Result', message, 'training_assessment_result', str(assignment.pk))
    refresh_status(assignment)
    return attempt


def retakes_used(assignment) -> int:
    """Attempts submitted after the first passing attempt."""
    first_pass = (assignment.attempts.filter(passed=True, submitted_at__isnull=False)
                  .order_by('attempt_number').values_list('attempt_number', flat=True).first())
    if first_pass is None:
        return 0
    return assignment.attempts.filter(submitted_at__isnull=False, attempt_number__gt=first_pass).count()


def reset_assessment(assignment) -> None:
    """HR gives a failed employee a fresh set of attempts (history kept). Only a failed,
    not-passed assessment can be reset — resetting a passed or completed course would
    clear the pass and could turn a completed course into a failed one."""
    if assignment.status != TrainingAssignment.STATUS_FAILED or assignment.assessment_passed:
        raise TrainingError('Only a failed assessment can be reset.', status=409)
    assignment.attempts.filter(submitted_at__isnull=True).delete()
    assignment.attempts_used = 0
    assignment.assessment_passed = None
    if assignment.status == TrainingAssignment.STATUS_FAILED:
        assignment.status = TrainingAssignment.STATUS_IN_PROGRESS
    assignment.save(update_fields=['attempts_used', 'assessment_passed', 'status', 'updated_at'])
