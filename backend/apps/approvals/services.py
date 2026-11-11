"""
Delegation and escalation authority, used by the existing approval checks:

  leave:      apps.hrms.views.leave._can_approve_at_stage / _approval_scope_filter
  attendance: apps.attendance.services_hr_corrections._can_approve_at_stage /
              _approval_scope_filter (punch corrections and late justifications)

A user may act on a request at its current stage when, besides the existing
rules, they are
  * an active delegate of that stage's designated approver, or
  * the target of an escalation of that request at that stage.
Never on their own request. The approve endpoints still require their usual
permission (leave.approve / attendance staff) — delegation checks for it up front.
"""
from __future__ import annotations

import datetime

from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from core.permissions import has_perm

from apps.approvals.models import KIND_ATTENDANCE, KIND_LEAVE, ApprovalDelegation, ApprovalEscalation

WORKFLOWS = (KIND_LEAVE, KIND_ATTENDANCE)
MAX_DELEGATION_DAYS = 180


class DelegationError(Exception):
    def __init__(self, message: str, field: str = ''):
        super().__init__(message)
        self.field = field


def can_approve_workflow(user, kind: str) -> bool:
    """Holds what the approve endpoint itself requires for this workflow."""
    if not user or not user.is_active:
        return False
    if kind == KIND_LEAVE:
        return has_perm(user, 'leave.approve')
    from apps.attendance.access import can_manage_attendance
    return can_manage_attendance(user)


def _today():
    return timezone.localdate()


def _active(qs, day=None):
    day = day or _today()
    return qs.filter(revoked_at__isnull=True, start_date__lte=day, end_date__gte=day)


def delegator_ids(user, kind: str, day=None) -> list:
    rows = _active(ApprovalDelegation.objects.filter(delegate=user), day)
    return [d.delegator_id for d in rows if kind in (d.workflows or [])]


def delegates_of(approver, kind: str, day=None) -> list:
    rows = _active(ApprovalDelegation.objects.filter(delegator=approver).select_related('delegate'), day)
    return [d.delegate for d in rows if kind in (d.workflows or []) and d.delegate.is_active]


def escalated_request_ids(user, kind: str, stage: str) -> list:
    return list(ApprovalEscalation.objects.filter(
        target=user, kind=kind, stage=stage, action=ApprovalEscalation.ACTION_ESCALATED,
    ).values_list('request_id', flat=True))


def _designated(req, stage: str):
    return req.l1_approver_id if stage == 'l1' else req.l2_approver_id


def acts_for(user, req, stage: str, kind: str) -> bool:
    """Delegate of the stage's designated approver, or escalation target of this request at this stage."""
    if not user or req.employee_id == user.id:
        return False
    designated = _designated(req, stage)
    if designated and designated in delegator_ids(user, kind):
        return True
    return ApprovalEscalation.objects.filter(
        target=user, kind=kind, request_id=req.pk, stage=stage, action=ApprovalEscalation.ACTION_ESCALATED,
    ).exists()


def scope_q(user, kind: str) -> Q:
    """Requests this user may act on through delegation or escalation (for the review queues)."""
    pending, l2 = 'pending', 'l2_pending'
    q = Q(pk__in=[])
    delegators = delegator_ids(user, kind)
    if delegators:
        q |= Q(status=pending, l1_approver_id__in=delegators) | Q(status=l2, l2_approver_id__in=delegators)
    esc1, esc2 = escalated_request_ids(user, kind, 'l1'), escalated_request_ids(user, kind, 'l2')
    if esc1:
        q |= Q(status=pending, pk__in=esc1)
    if esc2:
        q |= Q(status=l2, pk__in=esc2)
    return q & ~Q(employee=user)


def with_delegates(approvers, kind: str) -> list:
    """Approvers plus their active delegates (each once) — for 'pending approval' notifications."""
    out, seen = [], set()
    for a in approvers:
        for u in [a, *delegates_of(a, kind)]:
            if u and u.pk not in seen:
                seen.add(u.pk)
                out.append(u)
    return out


# ── Delegation management ─────────────────────────────────────────────────────

def _audit(actor, action: str, delegation: ApprovalDelegation, ip=None):
    from apps.accounts.models import AuditLog
    AuditLog.objects.create(
        user=actor, action=action, module='approvals', object_id=str(delegation.pk),
        changes={'delegator': delegation.delegator.full_name, 'delegate': delegation.delegate.full_name,
                 'from': delegation.start_date.isoformat(), 'to': delegation.end_date.isoformat(),
                 'workflows': delegation.workflows, 'reason': delegation.reason},
        branch=getattr(delegation.delegator, 'branch', '') or '', ip_address=ip,
    )


def _same_scope(delegator, delegate) -> bool:
    """A delegate in the delegator's branch — or a company-wide approver."""
    if has_perm(delegate, 'settings.edit'):
        return True
    a = (getattr(delegator, 'branch', '') or '').strip().lower()
    b = (getattr(delegate, 'branch', '') or '').strip().lower()
    return not a or a == b


def create_delegation(*, actor, delegator, delegate, start_date: datetime.date, end_date: datetime.date,
                      workflows, reason: str = '', ip=None) -> ApprovalDelegation:
    if actor.pk != delegator.pk and not has_perm(actor, 'settings.edit'):
        raise DelegationError('You can only delegate your own approvals.')
    workflows = sorted(set(workflows or []))
    if not workflows or any(w not in WORKFLOWS for w in workflows):
        raise DelegationError('Choose Leave and/or Attendance requests.', 'workflows')
    if delegate.pk == delegator.pk:
        raise DelegationError('Choose someone other than the approver.', 'delegate')
    if not delegate.is_active:
        raise DelegationError('That employee is not active.', 'delegate')
    if end_date < start_date:
        raise DelegationError('The end date must be on or after the start date.', 'end_date')
    if end_date < _today():
        raise DelegationError('The end date is in the past.', 'end_date')
    if (end_date - start_date).days + 1 > MAX_DELEGATION_DAYS:
        raise DelegationError(f'A delegation can last at most {MAX_DELEGATION_DAYS} days.', 'end_date')
    for w in workflows:
        if not can_approve_workflow(delegator, w):
            raise DelegationError(f'{delegator.full_name} does not approve {w} requests.', 'workflows')
        if not can_approve_workflow(delegate, w):
            raise DelegationError(f'{delegate.full_name} is not allowed to approve {w} requests.', 'delegate')
    if not _same_scope(delegator, delegate):
        raise DelegationError('The delegate must be in the same branch as the approver.', 'delegate')
    with transaction.atomic():
        overlapping = ApprovalDelegation.objects.select_for_update().filter(
            delegator=delegator, revoked_at__isnull=True, start_date__lte=end_date, end_date__gte=start_date)
        for d in overlapping:
            if set(d.workflows or []) & set(workflows):
                raise DelegationError('These dates overlap another active delegation — revoke it first.',
                                      'start_date')
        d = ApprovalDelegation.objects.create(delegator=delegator, delegate=delegate, start_date=start_date,
                                              end_date=end_date, workflows=workflows, reason=reason[:300],
                                              created_by=actor)
        _audit(actor, 'approval_delegation_created', d, ip)
    from apps.notifications.signals import _notify
    _notify(delegate, 'Approvals Delegated To You',
            f'{delegator.full_name} delegated their {" and ".join(workflows)} approvals to you '
            f'from {start_date:%d %b %Y} to {end_date:%d %b %Y}.', 'approval', 'approvals', str(d.pk),
            actor, category='approval')
    return d


def revoke_delegation(*, actor, delegation: ApprovalDelegation, ip=None) -> ApprovalDelegation:
    if actor.pk not in (delegation.delegator_id, delegation.created_by_id) and not has_perm(actor, 'settings.edit'):
        raise DelegationError('Only the approver or an administrator can revoke this delegation.')
    if delegation.revoked_at:
        raise DelegationError('Already revoked.')
    delegation.revoked_at, delegation.revoked_by = timezone.now(), actor
    delegation.save(update_fields=['revoked_at', 'revoked_by'])
    _audit(actor, 'approval_delegation_revoked', delegation, ip)
    return delegation
