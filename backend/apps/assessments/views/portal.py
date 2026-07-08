import logging

from django.utils import timezone
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView

from core.responses import error, success

from collections import defaultdict

from ..models import AssessmentItem, AssessmentSection, AssessmentSettings, CandidateAssignment, CandidateResponse
from ..serializers import PortalAssignmentSerializer

logger = logging.getLogger(__name__)


def _compute_weighted_result(assignment) -> tuple:
    """
    Returns (achieved_score, max_score) using section weights.
    Falls back to raw correct count when no sections are defined.
    """
    sections = list(assignment.assessment.sections.all())
    quiz_items = list(
        assignment.assessment.items
            .filter(item_type=AssessmentItem.TYPE_QUIZ)
            .values('id', 'section_id')
    )
    if not sections:
        return assignment.score, len(quiz_items) or assignment.max_score

    correct_ids = frozenset(
        assignment.responses.filter(is_correct=True).values_list('item_id', flat=True)
    )
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


def _get_candidate(user):
    from apps.recruitment.models import Candidate
    return Candidate.objects.filter(portal_user=user).first()


def _resolve_assignment(user, assignment_id):
    """
    Returns (assignment, error_response). Works for both candidate and employee paths.
    """
    candidate = _get_candidate(user)
    filter_kwargs = {'id': assignment_id}
    if candidate:
        filter_kwargs['candidate'] = candidate
    else:
        filter_kwargs['employee'] = user
    try:
        return (
            CandidateAssignment.objects.select_related('assessment').get(**filter_kwargs),
            None,
        )
    except CandidateAssignment.DoesNotExist:
        return None, error('Assignment not found.', http_status=status.HTTP_404_NOT_FOUND)


def _sync_user_assessment_status(user) -> None:
    """Recompute and persist assessment_status for user (candidate or employee path)."""
    from apps.accounts.models import User
    pending_statuses = [CandidateAssignment.STATUS_PENDING, CandidateAssignment.STATUS_IN_PROGRESS]
    candidate = _get_candidate(user)
    if candidate:
        has_incomplete = CandidateAssignment.objects.filter(
            candidate=candidate, status__in=pending_statuses,
        ).exists()
    else:
        has_incomplete = CandidateAssignment.objects.filter(
            employee=user, status__in=pending_statuses,
        ).exists()
    new_status = User.ASSESSMENT_PENDING if has_incomplete else User.ASSESSMENT_COMPLETE
    if user.assessment_status != new_status:
        user.assessment_status = new_status
        user.save(update_fields=['assessment_status', 'updated_at'])


class MyAssessmentView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        candidate = _get_candidate(request.user)

        # Build queryset — candidate-based (new joiner) OR employee-based (existing employee)
        base_qs = (
            CandidateAssignment.objects.select_related('assessment')
                                       .prefetch_related(
                                           'responses', 'responses__item',
                                           'assessment__items',
                                       )
        )
        if candidate:
            assignments = base_qs.filter(candidate=candidate)
        else:
            assignments = base_qs.filter(employee=request.user)

        if not assignments.exists():
            from apps.accounts.models import User
            if request.user.assessment_status != User.ASSESSMENT_COMPLETE:
                request.user.assessment_status = User.ASSESSMENT_COMPLETE
                request.user.save(update_fields=['assessment_status', 'updated_at'])
            return success('No assessments assigned.', {'assignments': [], 'all_complete': True})

        all_complete = not assignments.filter(
            status__in=[CandidateAssignment.STATUS_PENDING, CandidateAssignment.STATUS_IN_PROGRESS]
        ).exists()
        global_settings = AssessmentSettings.load()
        serializer = PortalAssignmentSerializer(
            assignments, many=True, context={'settings': global_settings},
        )
        return success('Assessments retrieved.', {
            'assignments':  serializer.data,
            'all_complete': all_complete,
        })


class RespondToItemView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, assignment_id, item_id):
        assignment, err = _resolve_assignment(request.user, assignment_id)
        if err:
            return err
        if assignment.status == CandidateAssignment.STATUS_COMPLETE:
            return error('This assessment is already completed.', http_status=status.HTTP_409_CONFLICT)
        if assignment.deadline and timezone.now() > assignment.deadline:
            return error('The deadline for this assessment has passed.', http_status=status.HTTP_403_FORBIDDEN)
        try:
            item = assignment.assessment.items.get(pk=item_id)
        except AssessmentItem.DoesNotExist:
            return error('Item not found in this assessment.', http_status=status.HTTP_404_NOT_FOUND)

        response, _ = CandidateResponse.objects.get_or_create(
            assignment=assignment, item=item,
        )
        old_score = response.score_awarded

        if item.item_type == AssessmentItem.TYPE_VIDEO:
            response.is_watched   = True
            response.responded_at = timezone.now()
            response.save(update_fields=['is_watched', 'responded_at', 'updated_at'])

        elif item.item_type == AssessmentItem.TYPE_QUIZ:
            selected = request.data.get('selected_option', '').strip().lower()
            if selected not in ('a', 'b', 'c', 'd'):
                return error('selected_option must be a, b, c, or d.')
            is_correct            = selected == item.correct_option
            response.selected_option = selected
            response.is_correct      = is_correct
            response.score_awarded   = 1 if is_correct else 0
            response.responded_at    = timezone.now()
            response.save(update_fields=[
                'selected_option', 'is_correct', 'score_awarded', 'responded_at', 'updated_at',
            ])
            score_diff = response.score_awarded - old_score
            if score_diff != 0:
                assignment.score = max(0, assignment.score + score_diff)
                assignment.save(update_fields=['score', 'updated_at'])

        update_fields = ['updated_at']
        if assignment.status == CandidateAssignment.STATUS_PENDING:
            assignment.status = CandidateAssignment.STATUS_IN_PROGRESS
            update_fields.append('status')
        if assignment.started_at is None:
            assignment.started_at = timezone.now()
            update_fields.append('started_at')
        if len(update_fields) > 1:
            assignment.save(update_fields=update_fields)

        return success('Response recorded.', {
            'item_id':       str(item.id),
            'item_type':     item.item_type,
            'is_correct':    response.is_correct,
            'score_awarded': response.score_awarded,
            'assignment_score': assignment.score,
        })


class RetryAssessmentView(APIView):
    """Reset a completed assignment so the candidate can attempt it again."""
    permission_classes = [IsAuthenticated]

    def post(self, request, assignment_id):
        assignment, err = _resolve_assignment(request.user, assignment_id)
        if err:
            return err
        if assignment.status != CandidateAssignment.STATUS_COMPLETE:
            return error(
                'Only completed assessments can be retried.',
                http_status=status.HTTP_409_CONFLICT,
            )
        global_settings = AssessmentSettings.load()
        effective_max = assignment.assessment.effective_max_attempts(global_settings)
        if effective_max != 0 and assignment.attempt_count >= effective_max:
            return error(
                f'Maximum attempts ({effective_max}) reached. This assessment is locked.',
                http_status=status.HTTP_403_FORBIDDEN,
            )
        assignment.responses.all().delete()
        assignment.status        = CandidateAssignment.STATUS_PENDING
        assignment.score         = 0
        assignment.started_at    = None
        assignment.completed_at  = None
        assignment.attempt_count = assignment.attempt_count + 1
        assignment.save(update_fields=['status', 'score', 'started_at', 'completed_at', 'attempt_count', 'updated_at'])
        _sync_user_assessment_status(request.user)
        logger.info('Assignment %s reset for retry by %s', assignment_id, request.user.email)
        return success('Assessment reset. You can now retry.')


class CompleteAssessmentView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, assignment_id):
        assignment, err = _resolve_assignment(request.user, assignment_id)
        if err:
            return err
        if assignment.status == CandidateAssignment.STATUS_COMPLETE:
            return error('Assignment already completed.', http_status=status.HTTP_409_CONFLICT)
        if assignment.deadline and timezone.now() > assignment.deadline:
            return error('The deadline for this assessment has passed.', http_status=status.HTTP_403_FORBIDDEN)

        video_item_ids = list(
            assignment.assessment.items
                .filter(item_type=AssessmentItem.TYPE_VIDEO)
                .values_list('id', flat=True)
        )
        quiz_item_ids = list(
            assignment.assessment.items
                .filter(item_type=AssessmentItem.TYPE_QUIZ)
                .values_list('id', flat=True)
        )
        total = len(video_item_ids) + len(quiz_item_ids)
        if total == 0:
            return error('This assessment has no items and cannot be completed.')

        watched  = assignment.responses.filter(item_id__in=video_item_ids, is_watched=True).count() if video_item_ids else 0
        answered = assignment.responses.filter(item_id__in=quiz_item_ids).exclude(selected_option='').count() if quiz_item_ids else 0
        responded = watched + answered
        if responded < total:
            return error(
                f'Complete all items first. {responded}/{total} done.',
                http_status=status.HTTP_400_BAD_REQUEST,
            )
        assignment.status       = CandidateAssignment.STATUS_COMPLETE
        assignment.completed_at = timezone.now()
        # Recompute score using section weights (overwrites incremental raw count)
        weighted_score, weighted_max = _compute_weighted_result(assignment)
        assignment.score     = weighted_score
        assignment.max_score = weighted_max
        assignment.save(update_fields=['status', 'score', 'max_score', 'completed_at', 'updated_at'])
        logger.info('Assignment %s completed by %s', assignment_id, request.user.email)
        _sync_user_assessment_status(request.user)
        if assignment.max_score:
            score_pct = round((assignment.score / assignment.max_score) * 100)
            passed = score_pct >= assignment.assessment.pass_percentage
        else:
            score_pct = 100
            passed = True
        return success('Assessment submitted.', {
            'score':            assignment.score,
            'max_score':        assignment.max_score,
            'score_percentage': score_pct,
            'pass_percentage':  assignment.assessment.pass_percentage,
            'passed':           passed,
        })
