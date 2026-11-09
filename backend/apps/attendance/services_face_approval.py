"""Who may see, review and be told about a Face ID registration request.

A reviewer must hold `facial_recognition.approve` AND be in the request's scope:

  1. the employee's assigned HR (User.hr), when that person is active and holds the permission;
  2. when the employee has no such assigned HR (none assigned, inactive, or without the permission, so the request can
     never be left with nobody): anyone holding the permission who shares the employee's branch;
  3. a superuser (the existing full-access override) sees and reviews everything.

Nobody ever reviews their own request. Rule 2 uses the same branch comparison as core.access (branch FK when both sides
have one, otherwise the legacy branch name, and a blank branch never matches). An approver with no branch therefore
only sees requests assigned to them.

The same scope drives the pending list, the review endpoint and the submission notification, so they cannot disagree.
"""
from __future__ import annotations

import logging

from django.db.models import Q, QuerySet

from apps.accounts.models import User
from apps.attendance.models import FaceRegistrationRequest
from core.access import is_full_access, users_with_permission
from core.permissions import has_perm

logger = logging.getLogger(__name__)

APPROVE_PERMISSION = 'facial_recognition.approve'
NOTIFICATION_TYPE = 'face_registration_pending'
NOTIFICATION_MODULE = 'facial_recognition'


def _same_branch_q(fk_id, name: str) -> Q:
    """Users on the branch described by (branch FK id, legacy branch name). Nothing when both are blank."""
    name = (name or '').strip()
    if not (fk_id or name):
        return Q(pk__in=[])
    if fk_id:
        condition = Q(branch_fk_id=fk_id)
        if name:
            condition |= Q(branch_fk__isnull=True, branch=name)
        return condition
    return Q(branch=name)


def _approver_pool() -> QuerySet:
    """Active people who can approve Face ID registrations at all."""
    return User.objects.filter(is_active=True).filter(users_with_permission(APPROVE_PERMISSION) | Q(is_superuser=True))


def _has_active_hr() -> Q:
    """The employee's assigned HR is active and is able to approve."""
    return Q(employee__hr_id__in=_approver_pool().values('pk'))


def scope_q(reviewer: User, *, assigned_to_me_only: bool = False) -> Q:
    """Q over FaceRegistrationRequest: the requests `reviewer` may see and review. Own requests are always excluded."""
    if not has_perm(reviewer, APPROVE_PERMISSION):
        return Q(pk__in=[])
    assigned = Q(employee__hr=reviewer) & _has_active_hr()
    if assigned_to_me_only:
        return assigned & ~Q(employee=reviewer)
    if is_full_access(reviewer):
        return ~Q(employee=reviewer)
    peers = User.objects.filter(_same_branch_q(reviewer.branch_fk_id, reviewer.branch)).values('pk')
    unassigned_in_branch = ~_has_active_hr() & Q(employee_id__in=peers)
    return (assigned | unassigned_in_branch) & ~Q(employee=reviewer)


def visible_to(reviewer: User, *, assigned_to_me_only: bool = False) -> QuerySet:
    return FaceRegistrationRequest.objects.filter(scope_q(reviewer, assigned_to_me_only=assigned_to_me_only))


def can_review(reviewer: User, face_request: FaceRegistrationRequest) -> bool:
    return visible_to(reviewer).filter(pk=face_request.pk).exists()


def approvers_for(employee: User) -> list[User]:
    """Who should be told about `employee`'s new request: their active assigned HR if that person can approve; otherwise
    approvers on the employee's branch; otherwise (so the request is never unseen) superusers."""
    approvers = _approver_pool().exclude(pk=employee.pk)
    if employee.hr_id is not None:
        assigned = list(approvers.filter(pk=employee.hr_id))
        if assigned:
            return assigned
    in_branch = list(approvers.filter(_same_branch_q(employee.branch_fk_id, employee.branch)).distinct())
    return in_branch or list(User.objects.filter(is_active=True, is_superuser=True).exclude(pk=employee.pk))


def notify_approvers_of_submission(face_request: FaceRegistrationRequest) -> int:
    """One in-app notification per approver, once per request. No email: delivery depends on SMTP, and the in-app
    notification must not claim otherwise. Returns how many notifications were created."""
    from apps.notifications.models import Notification
    from apps.notifications.signals import _notify

    employee = face_request.employee
    name = employee.full_name or employee.email
    reference = str(face_request.pk)
    created = 0
    for approver in approvers_for(employee):
        if Notification.objects.filter(user=approver, notification_type=NOTIFICATION_TYPE, reference_id=reference).exists():
            continue
        _notify(
            approver, 'Face ID registration awaiting review',
            f'{name} ({employee.employee_id or "no employee ID"}) submitted a Face ID registration for your approval.',
            NOTIFICATION_TYPE, NOTIFICATION_MODULE, reference, created_by=employee,
        )
        created += 1
    return created
