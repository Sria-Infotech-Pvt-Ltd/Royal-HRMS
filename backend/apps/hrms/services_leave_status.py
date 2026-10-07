"""
Phase 6A Task I.3 — the `leave_status_for(employee, date)` hook Phase 6B's
attendance evaluation engine (and its own prompt, verbatim: "Reuse...
Phase 6A: leave_status_for...") depends on. Built now, deliberately ahead
of Task I's other integrations, specifically so Phase 6B has something
real to call rather than needing to invent its own leave lookup.

Does NOT replace any existing attendance call site in this pass — the 3
existing independent approved-leave-date resolvers found in
apps/attendance (services_absence.py, services_attendance.py,
services_hr_ops.py) are untouched; migrating them onto this shared
function is listed as a catalogued-but-deferred item (Task I.3's own
"replace the current direct reads; list the call sites") in
PHASE6A_REPORT.md, since doing so touches attendance's own processing
pipeline, which is out of this phase's scope (that's Phase 6B's domain).
"""
from __future__ import annotations


def leave_status_for(employee, date) -> dict | None:
    """Returns None if no leave covers `date` in a status that should
    affect attendance (pending/rejected/cancelled requests are excluded —
    only `approved` counts, matching every existing attendance call
    site's own filter), else:
    {
        'leave_request_id': str, 'leave_type_code': str,
        'portion': 'full' | 'half', 'is_paid': bool,
    }
    `is_paid` is read directly from `LeaveRequest.is_lwp` (the existing,
    already-correct field — NOT re-derived from LeaveType.is_paid, since
    is_lwp is set per-request today and is the one value every existing
    payroll/attendance call site already trusts)."""
    from apps.hrms.models import DURATION_FULL, REQ_APPROVED, LeaveRequest

    request = (
        LeaveRequest.objects.filter(
            employee=employee, status=REQ_APPROVED,
            start_date__lte=date, end_date__gte=date,
        )
        .order_by('-updated_at')
        .first()
    )
    if request is None:
        return None

    portion = 'full' if request.duration == DURATION_FULL else 'half'
    return {
        'leave_request_id': str(request.id), 'leave_type_code': request.leave_type,
        'portion': portion, 'is_paid': not request.is_lwp,
    }
