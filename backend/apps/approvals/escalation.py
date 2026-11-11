"""
Automatic reminders and escalation for pending approvals (leave, attendance
corrections and late justifications). Run daily by
apps.approvals.tasks.run_approval_escalations, once per company.

For a request waiting at its current stage (L1 since it was submitted, L2
since the manager approved it), counted in working days of the current
approver (their week-offs and their branch's holidays are skipped):

  reminder_after_days            → reminder to the current approver(s) (+ delegates)
  first_escalation_after_days    → escalated to the next higher approver
  + second_escalation_after_days → escalated to the escalation head

Next higher approver: the current approver's reporting manager, else their
reporting approver, else (at L1) the request's HR approver. An escalation
target may then approve or reject the request at that stage
(apps.approvals.services.acts_for). Each step happens once per request and
stage (unique log row); when the request moves to the next stage the clock
starts again. Disabled companies are skipped.
"""
from __future__ import annotations

import datetime
import logging

from django.db import IntegrityError, transaction
from django.utils import timezone

from apps.approvals.models import KIND_ATTENDANCE, KIND_LEAVE, ApprovalEscalation, ApprovalEscalationSettings
from apps.approvals.services import with_delegates

logger = logging.getLogger(__name__)


def working_days_between(since: datetime.date, today: datetime.date, user) -> int:
    """Working days after `since` up to and including `today`, for `user`."""
    if today <= since:
        return 0
    from core.cache_service import HolidayCacheService, WeeklyOffCacheService
    start = since + datetime.timedelta(days=1)
    offs = WeeklyOffCacheService.get_effective_range(user, start, today) if user else {}
    holidays = HolidayCacheService.get_holiday_dates(start, today, (getattr(user, 'branch', '') or '') if user else '')
    n, d = 0, start
    while d <= today:
        off = d.strftime('%A').lower() in (offs.get(d, set()) if offs else set())
        if not off and d not in holidays:
            n += 1
        d += datetime.timedelta(days=1)
    return n


def _stage(req):
    return 'l1' if req.status == 'pending' else 'l2'


def _since(req, stage) -> datetime.date:
    at = req.created_at if stage == 'l1' else (req.l1_actioned_at or req.created_at)
    return timezone.localtime(at).date()


def _current_approvers(req, stage, kind) -> list:
    if stage == 'l1':
        return [req.l1_approver] if req.l1_approver else []
    if req.l2_approver:
        return [req.l2_approver]
    from apps.notifications.recipients import fallback_hr_approvers
    if kind == KIND_LEAVE:
        return fallback_hr_approvers(req.employee, 'leave.approve')
    return fallback_hr_approvers(req.employee, 'attendance.create', staff_only=True)


def _next_higher(req, stage):
    current = req.l1_approver if stage == 'l1' else req.l2_approver
    candidates = []
    if current:
        candidates += [getattr(current, 'reporting_manager', None), getattr(current, 'reporting_approver', None)]
    if stage == 'l1':
        candidates.append(req.l2_approver)
    for c in candidates:
        if c and c.is_active and c.pk != req.employee_id and (not current or c.pk != current.pk):
            return c
    return None


def _describe(req, kind) -> str:
    if kind == KIND_LEAVE:
        return f'{req.employee.full_name}\'s leave ({req.start_date:%d %b} – {req.end_date:%d %b})'
    what = 'late arrival justification' if getattr(req, 'kind', '') == 'late_justification' else 'attendance correction'
    return f'{req.employee.full_name}\'s {what} for {req.date:%d %b}'


def _record(req, kind, stage, level, action, target, waited, note='') -> bool:
    """Write the step once. False when it already happened (unique key)."""
    try:
        with transaction.atomic():
            ApprovalEscalation.objects.create(kind=kind, request_id=req.pk, stage=stage, level=level, action=action,
                                              target=target, working_days_waited=waited, note=note[:300])
        return True
    except IntegrityError:
        return False


def _done(req, kind, stage) -> set:
    return set(ApprovalEscalation.objects.filter(kind=kind, request_id=req.pk, stage=stage)
               .values_list('level', flat=True))


def _process(req, kind, cfg, today) -> list[str]:
    from apps.notifications.signals import _notify
    stage = _stage(req)
    approvers = _current_approvers(req, stage, kind)
    reference = approvers[0] if approvers else req.employee
    waited = working_days_between(_since(req, stage), today, reference)
    done = _done(req, kind, stage)
    what = _describe(req, kind)
    module = 'leave' if kind == KIND_LEAVE else 'attendance'
    ref_id = str(req.pk)
    steps = []

    if 0 not in done and cfg.reminder_after_days and waited >= cfg.reminder_after_days:
        if _record(req, kind, stage, 0, ApprovalEscalation.ACTION_REMINDER, None, waited):
            for u in with_delegates(approvers, kind):
                _notify(u, 'Approval Reminder', f'{what} has been waiting {waited} working day(s) for your approval.',
                        'approval_reminder', module, ref_id, category='approval')
            steps.append('reminder')

    first_at = cfg.first_escalation_after_days
    if first_at and 1 not in done and waited >= first_at:
        target = _next_higher(req, stage)
        action = ApprovalEscalation.ACTION_ESCALATED if target else ApprovalEscalation.ACTION_SKIPPED
        note = '' if target else 'No higher approver (reporting manager / approver) set for the current approver.'
        if _record(req, kind, stage, 1, action, target, waited, note):
            if target:
                _notify(target, 'Request Escalated To You',
                        f'{what} has waited {waited} working day(s) at the {"manager" if stage == "l1" else "HR"} '
                        'stage and was escalated to you. You can approve or reject it.',
                        'approval_escalated', module, ref_id, category='approval')
                for u in approvers:
                    _notify(u, 'Request Escalated', f'{what} was escalated to {target.full_name} after {waited} '
                            'working day(s).', 'approval_escalated', module, ref_id, category='approval')
            steps.append(action)

    second_at = (first_at or 0) + (cfg.second_escalation_after_days or 0)
    if first_at and cfg.second_escalation_after_days and 2 not in done and waited >= second_at:
        head = cfg.escalation_head if cfg.escalation_head_id and cfg.escalation_head.is_active else None
        previous = ApprovalEscalation.objects.filter(kind=kind, request_id=req.pk, stage=stage, level=1).first()
        if head and (head.pk == req.employee_id or (previous and previous.target_id == head.pk)):
            head = None
        action = ApprovalEscalation.ACTION_ESCALATED if head else ApprovalEscalation.ACTION_SKIPPED
        note = '' if head else 'No escalation head configured (or the head is already handling it).'
        if _record(req, kind, stage, 2, action, head, waited, note):
            if head:
                _notify(head, 'Request Escalated To You',
                        f'{what} has waited {waited} working day(s) without a decision and was escalated to you. '
                        'You can approve or reject it.', 'approval_escalated', module, ref_id, category='approval')
            steps.append(f'{action}-2')
    return steps


def run_escalations(today: datetime.date | None = None) -> dict:
    cfg = ApprovalEscalationSettings.current()
    if not cfg.pk or not cfg.is_enabled:
        return {'skipped': True, 'reason': 'escalation disabled'}
    today = today or timezone.localdate()
    summary = {'checked': 0, 'reminders': 0, 'escalations': 0, 'skipped_no_target': 0}

    pending = ('pending', 'l2_pending')
    sources = []
    if cfg.applies_to(KIND_LEAVE):
        from apps.hrms.models import LeaveRequest
        sources.append((KIND_LEAVE, LeaveRequest.objects.filter(status__in=pending)))
    if cfg.applies_to(KIND_ATTENDANCE):
        from apps.attendance.models import AttendanceCorrection
        sources.append((KIND_ATTENDANCE, AttendanceCorrection.objects.filter(status__in=pending)))
    for kind, qs in sources:
        for req in qs.select_related('employee', 'l1_approver__reporting_manager', 'l1_approver__reporting_approver',
                                     'l2_approver__reporting_manager', 'l2_approver__reporting_approver'):
            summary['checked'] += 1
            try:
                for step in _process(req, kind, cfg, today):
                    if step == 'reminder':
                        summary['reminders'] += 1
                    elif step.startswith('escalated'):
                        summary['escalations'] += 1
                    else:
                        summary['skipped_no_target'] += 1
            except Exception:
                logger.exception('Escalation failed for %s %s', kind, req.pk)
    logger.info('run_escalations: %s', summary)
    return summary
