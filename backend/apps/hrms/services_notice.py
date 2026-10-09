"""
Notice-period countdown derived from an approved SeparationRequest.

The countdown starts only at final approval (status becomes SEP_APPROVED in
SeparationApprovalStageActionView). Approved requests are immutable, so the
proposed_last_working_day at approval is the confirmed last working day, and
the final approval time is the latest actioned_at among its approved stages —
no extra stored fields are needed.
"""
from __future__ import annotations

import datetime

from django.utils import timezone

from .models import APPROVAL_APPROVED, SEP_APPROVED

NOTICE_SERVING   = 'serving'
NOTICE_COMPLETED = 'completed'


def final_approval_at(sep_request) -> datetime.datetime | None:
    if sep_request.status != SEP_APPROVED:
        return None
    times = [
        s.actioned_at for s in sep_request.approval_stages.all()
        if s.status == APPROVAL_APPROVED and s.actioned_at is not None
    ]
    return max(times) if times else None


def notice_info(sep_request, today: datetime.date | None = None) -> dict | None:
    """None unless the request is fully approved."""
    if sep_request.status != SEP_APPROVED:
        return None
    today = today or timezone.localdate()
    last_day = sep_request.proposed_last_working_day
    days = (last_day - today).days
    approved_at = final_approval_at(sep_request)
    return {
        'notice_status':              NOTICE_SERVING if days >= 0 else NOTICE_COMPLETED,
        'days_remaining':             max(days, 0),
        'confirmed_last_working_day': last_day.isoformat(),
        'approved_at':                timezone.localtime(approved_at).isoformat() if approved_at else None,
    }
