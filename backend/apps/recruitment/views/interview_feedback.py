"""
Interviewer feedback endpoints.

  - GET  /recruitment/my-interviews/                     the interviews assigned to the signed-in user, nothing else;
  - GET  /recruitment/my-interviews/<id>/feedback/       their own feedback on one of them;
  - PUT  /recruitment/my-interviews/<id>/feedback/       submit or change it (rating, recommendation, comments);
  - GET  /recruitment/candidates/<id>/feedback/          HR: every interviewer's feedback and a summary.

An interviewer never needs a recruitment permission: being the candidate's assigned interviewer is what grants access, and
only to that candidate. HR reads feedback with recruitment.view, inside their branch scope.
"""
from __future__ import annotations

from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView

from apps.recruitment.models import Candidate, InterviewFeedback
from apps.recruitment.services_interview_feedback import (
    candidate_for_interviewer, feedback_summary, interviews_for, save_feedback, submission_refusal, validate_feedback,
)
from apps.recruitment.views.shared import _can_access_candidate
from core.pagination import paginate, paginated_data
from core.permissions import HasCompletedOnboardingStatus, has_perm as _has_perm
from core.responses import error, success

_DENIED = 'You do not have permission to perform this action.'
_NOT_FOUND = 'Interview not found.'


def _feedback_dict(entry: InterviewFeedback) -> dict:
    return {
        'id': str(entry.pk), 'interviewer': entry.interviewer_name, 'rating': entry.rating,
        'recommendation': entry.recommendation, 'recommendation_label': entry.get_recommendation_display(),
        'comments': entry.comments, 'submitted_at': entry.created_at, 'updated_at': entry.updated_at,
    }


def _interview_dict(candidate: Candidate, mine: InterviewFeedback | None) -> dict:
    """What an interviewer sees about a candidate: name, role and schedule. No contact details."""
    return {
        'id': candidate.pk, 'candidate_name': candidate.name, 'position_applied': candidate.position_applied,
        'branch': candidate.branch.branch_name if candidate.branch else '',
        'interview_date': candidate.interview_date, 'interview_time': candidate.interview_time,
        'interview_mode': candidate.interview_mode, 'interview_mode_label': candidate.get_interview_mode_display(),
        'meeting_link': candidate.meeting_link, 'status': candidate.status, 'status_label': candidate.get_status_display(),
        'can_submit': submission_refusal(candidate) is None, 'my_feedback': _feedback_dict(mine) if mine else None,
    }


class MyInterviewsView(APIView):
    permission_classes = [IsAuthenticated, HasCompletedOnboardingStatus]

    def get(self, request):
        page_obj, paginator = paginate(interviews_for(request.user), request, default_page_size=20)
        mine = {f.candidate_id: f for f in InterviewFeedback.objects.filter(
            interviewer=request.user, candidate__in=[c.pk for c in page_obj.object_list])}
        rows = [_interview_dict(candidate, mine.get(candidate.pk)) for candidate in page_obj.object_list]
        return success('Your interviews retrieved.', data=paginated_data(paginator, page_obj, rows))


class MyInterviewFeedbackView(APIView):
    permission_classes = [IsAuthenticated, HasCompletedOnboardingStatus]

    def get(self, request, pk: int):
        candidate = candidate_for_interviewer(request.user, pk)
        if candidate is None:
            return error(_NOT_FOUND, http_status=status.HTTP_404_NOT_FOUND)
        mine = InterviewFeedback.objects.filter(candidate=candidate, interviewer=request.user).first()
        return success('Interview retrieved.', data=_interview_dict(candidate, mine))

    def put(self, request, pk: int):
        candidate = candidate_for_interviewer(request.user, pk)
        if candidate is None:
            return error(_NOT_FOUND, http_status=status.HTTP_404_NOT_FOUND)
        refusal = submission_refusal(candidate)
        if refusal:
            return error(refusal, http_status=status.HTTP_409_CONFLICT)
        values, errors = validate_feedback(request.data)
        if errors:
            return error(next(iter(errors.values())), data=errors)
        entry, created = save_feedback(candidate, request.user, values)
        candidate.refresh_from_db()
        return success('Feedback submitted.' if created else 'Feedback updated.', data=_interview_dict(candidate, entry),
                       http_status=status.HTTP_201_CREATED if created else status.HTTP_200_OK)

    patch = put


class CandidateFeedbackView(APIView):
    """HR's view of every interviewer's feedback on one candidate."""
    permission_classes = [IsAuthenticated]

    def get(self, request, pk: int):
        if not _has_perm(request.user, 'recruitment.view'):
            return error(_DENIED, http_status=status.HTTP_403_FORBIDDEN)
        candidate = Candidate.objects.select_related('branch').filter(pk=pk).first()
        if candidate is None or not _can_access_candidate(request.user, candidate):
            return error('Candidate not found.', http_status=status.HTTP_404_NOT_FOUND)
        entries = InterviewFeedback.objects.filter(candidate=candidate).order_by('created_at')
        return success('Interview feedback retrieved.', data={
            'candidate': {'id': candidate.pk, 'name': candidate.name, 'status': candidate.status, 'status_label': candidate.get_status_display()},
            'summary': feedback_summary(candidate), 'feedback': [_feedback_dict(entry) for entry in entries],
        })
