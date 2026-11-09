"""
Interviewer feedback, and the two rules built on it.

  - An interviewer reaches only the candidates assigned to them (Candidate.interviewer): nothing else about other candidates,
    other interviewers' feedback, or the rest of the pipeline is visible to them.
  - HR can read every entry, and a candidate cannot be marked Selected until at least one interviewer has submitted feedback.

Submitting the first feedback for a scheduled interview moves the candidate from "Interview Scheduled" to "Interview Done".
"""
from __future__ import annotations

from django.db import transaction
from django.db.models import Avg

from apps.recruitment.models import Candidate, CandidateLog, InterviewFeedback

OPEN_STATUSES = (Candidate.STATUS_INTERVIEW_SCHEDULED, Candidate.STATUS_INTERVIEW_DONE)   # feedback can be given or changed
MAX_COMMENT_LENGTH = 5000
MIN_COMMENT_LENGTH = 10


def interviews_for(user):
    """The interviews assigned to `user`: scheduled ones only, and nothing about anyone else's."""
    return (Candidate.objects.filter(interviewer=user, interview_date__isnull=False)
            .select_related('branch').order_by('-interview_date', '-interview_time'))


def candidate_for_interviewer(user, candidate_id) -> Candidate | None:
    """The candidate, only if `user` is their assigned interviewer. A missing and a not-yours candidate look the same."""
    return interviews_for(user).filter(pk=candidate_id).first()


def submission_refusal(candidate: Candidate) -> str | None:
    if candidate.status not in OPEN_STATUSES:
        return 'Feedback can only be submitted while the interview is scheduled or done, before HR has made a decision.'
    return None


def validate_feedback(data: dict) -> tuple[dict, dict[str, str]]:
    """(clean values, {field: message}). Rating 1-5, a recommendation, and written comments are all required."""
    errors: dict[str, str] = {}
    try:
        rating = int(data.get('rating'))
    except (TypeError, ValueError):
        rating = 0
    if not 1 <= rating <= 5:
        errors['rating'] = 'Choose a rating from 1 to 5.'
    recommendation = str(data.get('recommendation') or '')
    if recommendation not in dict(InterviewFeedback.RECOMMENDATION_CHOICES):
        errors['recommendation'] = 'Choose Recommend, Undecided or Do not recommend.'
    comments = str(data.get('comments') or '').strip()
    if len(comments) < MIN_COMMENT_LENGTH:
        errors['comments'] = f'Write at least {MIN_COMMENT_LENGTH} characters of comments.'
    elif len(comments) > MAX_COMMENT_LENGTH:
        errors['comments'] = f'Comments must be {MAX_COMMENT_LENGTH} characters or fewer.'
    return {'rating': rating, 'recommendation': recommendation, 'comments': comments}, errors


@transaction.atomic
def save_feedback(candidate: Candidate, interviewer, values: dict) -> tuple[InterviewFeedback, bool]:
    """Create or update this interviewer's single feedback entry. Returns (feedback, created)."""
    feedback, created = InterviewFeedback.objects.update_or_create(
        candidate=candidate, interviewer=interviewer,
        defaults={**values, 'interviewer_name': interviewer.full_name or interviewer.email},
    )
    who = interviewer.full_name or interviewer.email
    CandidateLog.objects.create(
        candidate=candidate, log_type=CandidateLog.TYPE_INFO,
        title='Interview feedback submitted' if created else 'Interview feedback updated',
        description=f'By {who}: {values["rating"]}/5, {feedback.get_recommendation_display()}.',
    )
    if candidate.status == Candidate.STATUS_INTERVIEW_SCHEDULED:
        candidate.status = Candidate.STATUS_INTERVIEW_DONE
        candidate.save(update_fields=['status', 'updated_at'])
        CandidateLog.objects.create(candidate=candidate, log_type=CandidateLog.TYPE_SUCCESS, title='Status changed to Interview Done',
                                    description=f'Moved automatically when {who} submitted feedback.')
    return feedback, created


def feedback_summary(candidate: Candidate) -> dict:
    entries = InterviewFeedback.objects.filter(candidate=candidate)
    average = entries.aggregate(avg=Avg('rating'))['avg']
    return {
        'count': entries.count(),
        'average_rating': round(float(average), 1) if average is not None else None,
        'recommend': entries.filter(recommendation=InterviewFeedback.RECOMMEND).count(),
        'undecided': entries.filter(recommendation=InterviewFeedback.HOLD).count(),
        'not_recommend': entries.filter(recommendation=InterviewFeedback.NOT_RECOMMEND).count(),
    }


def selection_refusal(candidate: Candidate) -> str | None:
    """Why `candidate` cannot be marked Selected yet, or None."""
    if not InterviewFeedback.objects.filter(candidate=candidate).exists():
        return 'At least one interviewer must submit feedback before this candidate can be marked Selected.'
    return None
