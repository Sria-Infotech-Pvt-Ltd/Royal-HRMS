import logging

from django.utils import timezone
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView

from core.responses import error, success

from ..models import AssessmentItem, CandidateAssignment, CandidateResponse
from ..serializers import PortalAssignmentSerializer

logger = logging.getLogger(__name__)


def _get_candidate(user):
    from apps.recruitment.models import Candidate
    return Candidate.objects.filter(portal_user=user).first()


def _sync_assessment_status(candidate):
    has_incomplete = CandidateAssignment.objects.filter(
        candidate=candidate,
        status__in=[CandidateAssignment.STATUS_PENDING, CandidateAssignment.STATUS_IN_PROGRESS],
    ).exists()
    portal_user = candidate.portal_user
    if not portal_user:
        return
    from apps.accounts.models import User
    new_status = User.ASSESSMENT_PENDING if has_incomplete else User.ASSESSMENT_COMPLETE
    if portal_user.assessment_status != new_status:
        portal_user.assessment_status = new_status
        portal_user.save(update_fields=['assessment_status', 'updated_at'])


class MyAssessmentView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        candidate = _get_candidate(request.user)
        if not candidate:
            return error('No candidate profile linked to this account.', http_status=status.HTTP_404_NOT_FOUND)
        assignments = (
            CandidateAssignment.objects.select_related('assessment')
                                       .prefetch_related(
                                           'responses', 'responses__item',
                                           'assessment__items',
                                       )
                                       .filter(candidate=candidate)
        )
        if not assignments.exists():
            from apps.accounts.models import User
            if request.user.assessment_status != User.ASSESSMENT_COMPLETE:
                request.user.assessment_status = User.ASSESSMENT_COMPLETE
                request.user.save(update_fields=['assessment_status', 'updated_at'])
            return success('No assessments assigned.', {'assignments': [], 'all_complete': True})
        all_complete = not assignments.filter(
            status__in=[CandidateAssignment.STATUS_PENDING, CandidateAssignment.STATUS_IN_PROGRESS]
        ).exists()
        serializer = PortalAssignmentSerializer(assignments, many=True)
        return success('Assessments retrieved.', {
            'assignments':   serializer.data,
            'all_complete':  all_complete,
        })


class RespondToItemView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, assignment_id, item_id):
        candidate = _get_candidate(request.user)
        if not candidate:
            return error('No candidate profile linked to this account.', http_status=status.HTTP_404_NOT_FOUND)
        try:
            assignment = CandidateAssignment.objects.select_related('assessment').get(
                id=assignment_id, candidate=candidate,
            )
        except CandidateAssignment.DoesNotExist:
            return error('Assignment not found.', http_status=status.HTTP_404_NOT_FOUND)
        if assignment.status == CandidateAssignment.STATUS_COMPLETE:
            return error('This assessment is already completed.', http_status=status.HTTP_409_CONFLICT)
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
            response.score_awarded   = item.pass_score if is_correct else 0
            response.responded_at    = timezone.now()
            response.save(update_fields=[
                'selected_option', 'is_correct', 'score_awarded', 'responded_at', 'updated_at',
            ])
            score_diff = response.score_awarded - old_score
            if score_diff != 0:
                assignment.score = max(0, assignment.score + score_diff)
                assignment.save(update_fields=['score', 'updated_at'])

        if assignment.status == CandidateAssignment.STATUS_PENDING:
            assignment.status = CandidateAssignment.STATUS_IN_PROGRESS
            assignment.save(update_fields=['status', 'updated_at'])

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
        candidate = _get_candidate(request.user)
        if not candidate:
            return error('No candidate profile linked to this account.', http_status=status.HTTP_404_NOT_FOUND)
        try:
            assignment = CandidateAssignment.objects.select_related('assessment').get(
                id=assignment_id, candidate=candidate,
            )
        except CandidateAssignment.DoesNotExist:
            return error('Assignment not found.', http_status=status.HTTP_404_NOT_FOUND)
        if assignment.status != CandidateAssignment.STATUS_COMPLETE:
            return error(
                'Only completed assessments can be retried.',
                http_status=status.HTTP_409_CONFLICT,
            )
        assignment.responses.all().delete()
        assignment.status        = CandidateAssignment.STATUS_PENDING
        assignment.score         = 0
        assignment.completed_at  = None
        assignment.attempt_count = assignment.attempt_count + 1
        assignment.save(update_fields=['status', 'score', 'completed_at', 'attempt_count', 'updated_at'])
        _sync_assessment_status(candidate)
        logger.info('Assignment %s reset for retry by %s', assignment_id, request.user.email)
        return success('Assessment reset. You can now retry.')


class CompleteAssessmentView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, assignment_id):
        candidate = _get_candidate(request.user)
        if not candidate:
            return error('No candidate profile linked to this account.', http_status=status.HTTP_404_NOT_FOUND)
        try:
            assignment = CandidateAssignment.objects.select_related('assessment').get(
                id=assignment_id, candidate=candidate,
            )
        except CandidateAssignment.DoesNotExist:
            return error('Assignment not found.', http_status=status.HTTP_404_NOT_FOUND)
        if assignment.status == CandidateAssignment.STATUS_COMPLETE:
            return error('Assignment already completed.', http_status=status.HTTP_409_CONFLICT)

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
        assignment.save(update_fields=['status', 'completed_at', 'updated_at'])
        logger.info('Assignment %s completed by %s', assignment_id, request.user.email)
        _sync_assessment_status(candidate)
        passed = assignment.score >= assignment.max_score if assignment.max_score else True
        return success('Assessment submitted.', {
            'score':    assignment.score,
            'max_score': assignment.max_score,
            'passed':   passed,
        })
