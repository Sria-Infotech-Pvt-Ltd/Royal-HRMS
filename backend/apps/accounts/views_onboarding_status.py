"""
Admin side of the Onboarding status: the history timeline behind the "Onboarding" badge, and (re)sending the invite email.

Lifecycle rules live in apps.accounts.services_onboarding; these views only check who may act and shape the response.
"""
from __future__ import annotations

import logging

from django.core.exceptions import ValidationError
from django.core.validators import validate_email
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from core.responses import error, get_client_ip, success

from apps.accounts import services_onboarding as onboarding
from apps.accounts.models import AuditLog, OnboardingEvent, User
from apps.accounts.views import _employee_out_of_branch_scope
from apps.accounts.views_reset_password import _can_manage_accounts, _invite_status_dict

logger = logging.getLogger(__name__)


def _load_target(request: Request, pk):
    """Return (user, None) or (None, error response) for the employee an admin is acting on."""
    if not _can_manage_accounts(request.user):
        return None, error(
            'You do not have permission to manage onboarding invites.', http_status=status.HTTP_403_FORBIDDEN,
        )
    try:
        target = User.objects.get(pk=pk, is_active=True)
    except (User.DoesNotExist, ValueError):
        return None, error('Employee not found.', http_status=status.HTTP_404_NOT_FOUND)
    if _employee_out_of_branch_scope(request.user, target):
        return None, error('Employee not found.', http_status=status.HTTP_404_NOT_FOUND)
    return target, None


def _history_payload(target: User) -> dict:
    return {
        'employee_name': target.full_name or target.email,
        'email': target.email,
        'is_onboarding': onboarding.is_onboarding(target),
        'state': onboarding.current_state(target),
        'timeline': onboarding.timeline(target),
        'resend_limit_per_hour': onboarding.resend_limit_per_hour(),
        **_invite_status_dict(target),
    }


class EmployeeOnboardingHistoryView(APIView):
    """GET /employees/<uuid:pk>/onboarding-history/ — what happened since HR started this person's onboarding."""
    permission_classes = [IsAuthenticated]

    def get(self, request: Request, pk) -> Response:
        target, problem = _load_target(request, pk)
        if problem is not None:
            return problem
        return success('Onboarding history retrieved.', data=_history_payload(target))


class ResendInviteView(APIView):
    """
    POST /employees/<uuid:pk>/resend-invite/ — reissue the onboarding invite (the previous link stops working).
    Optional body {"email": "..."} first corrects a wrong address, only while the person is still onboarding.
    Limited per employee per hour; every send, failure and correction is written to the onboarding history.
    """
    permission_classes = [IsAuthenticated]

    def post(self, request: Request, pk) -> Response:
        target, problem = _load_target(request, pk)
        if problem is not None:
            return problem

        if not (target.must_change_password or target.activation_pending):
            return error(
                'This employee has already activated their account and set a password.',
                http_status=status.HTTP_400_BAD_REQUEST,
            )

        new_email = (request.data.get('email') or '').strip()
        if new_email and new_email.lower() != target.email.lower():
            problem = self._correct_email(request, target, new_email)
            if problem is not None:
                return problem

        try:
            sent = onboarding.send_onboarding_email(target, actor=request.user, is_resend=True)
        except onboarding.ResendLimitError as exc:
            return error(str(exc), data=_history_payload(target), http_status=status.HTTP_429_TOO_MANY_REQUESTS)

        AuditLog.objects.create(
            user=request.user, action='invite_resent', module='accounts',
            object_id=str(target.pk), changes={'employee': target.email, 'sent': sent},
            branch=target.branch, ip_address=get_client_ip(request),
        )
        if not sent:
            return error(
                'The onboarding email could not be sent. The reason is in the onboarding history.',
                data=_history_payload(target), http_status=status.HTTP_502_BAD_GATEWAY,
            )
        return success('Onboarding email resent.', data=_history_payload(target))

    @staticmethod
    def _correct_email(request: Request, target: User, new_email: str):
        if not target.activation_pending:
            return error('The email address can only be corrected while onboarding is pending.')
        try:
            validate_email(new_email)
        except ValidationError:
            return error('Enter a valid email address.')
        if User.objects.filter(email__iexact=new_email).exclude(pk=target.pk).exists():
            return error('Another employee already uses this email address.')
        old_email = target.email
        target.email = new_email
        target.save(update_fields=['email', 'updated_at'])
        onboarding.record_event(
            target, OnboardingEvent.EMAIL_CORRECTED, actor=request.user, detail=f'Changed from {old_email} to {new_email}.',
        )
        AuditLog.objects.create(
            user=request.user, action='onboarding_email_corrected', module='accounts',
            object_id=str(target.pk), changes={'from': old_email, 'to': new_email},
            branch=target.branch, ip_address=get_client_ip(request),
        )
        return None
