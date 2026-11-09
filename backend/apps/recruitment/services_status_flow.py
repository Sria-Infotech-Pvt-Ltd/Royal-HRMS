"""
Which candidate status may follow which, in the HR-led recruitment pipeline.

    Pending -> Screening -> Interview Scheduled -> Interview Done -> Selected -> (onboarding link sent) -> Converted
                 any stage before Converted -> Rejected

A candidate cannot jump straight to Selected: they must have had an interview (Interview Done) and at least one interviewer's
feedback (see services_interview_feedback.selection_refusal). "Onboarding Link Sent" and "Converted" are set by the system when
HR sends the link and when HR approves the onboarding, never by choosing a status.
"""
from __future__ import annotations

from apps.recruitment.models import Candidate

_PENDING, _SCREENING = Candidate.STATUS_PENDING, Candidate.STATUS_SCREENING
_SCHEDULED, _DONE = Candidate.STATUS_INTERVIEW_SCHEDULED, Candidate.STATUS_INTERVIEW_DONE
_SELECTED, _REJECTED = Candidate.STATUS_SELECTED, Candidate.STATUS_REJECTED

ALLOWED_NEXT: dict[str, set[str]] = {
    _PENDING: {_SCREENING, _SCHEDULED, _REJECTED},
    _SCREENING: {_PENDING, _SCHEDULED, _REJECTED},
    _SCHEDULED: {_SCREENING, _DONE, _REJECTED},
    _DONE: {_SCHEDULED, _SELECTED, _REJECTED},
    _SELECTED: {_REJECTED},
    Candidate.STATUS_OFFER_SENT: {_REJECTED},
    _REJECTED: set(),
    Candidate.STATUS_CONVERTED: set(),
}


def transition_refusal(candidate: Candidate, new_status: str) -> str | None:
    """Why `candidate` cannot move to `new_status`, or None."""
    current = candidate.status
    if new_status == current:
        return f'The candidate is already {candidate.get_status_display()}.'
    if new_status in ALLOWED_NEXT.get(current, set()):
        return None
    label, target = candidate.get_status_display(), dict(Candidate.STATUS_CHOICES).get(new_status, new_status)
    if new_status == _SELECTED and current in (_PENDING, _SCREENING, _SCHEDULED):
        return 'A candidate must have completed an interview (Interview Done) before being marked Selected.'
    return f'A candidate who is {label} cannot be moved to {target}.'
