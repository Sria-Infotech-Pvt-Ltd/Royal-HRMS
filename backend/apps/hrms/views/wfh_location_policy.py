"""Allow, or stop allowing, "punch from any location" on a work-from-home request.

A WFH punch is normally checked against the location declared in the request (services_geofencing._validate_wfh). Someone who moves
around during the approved days (to another village, a relative's house) can be refused every punch with no way to change the declared
spot, so the people who can approve the request may lift the location check for it. Face verification and the approved dates still
apply, GPS readings are still recorded, and every change is written to the audit log.
"""
from __future__ import annotations

import logging

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView

from core.permissions import HasCompletedOnboardingStatus, has_perm as _has_perm
from core.responses import error, get_client_ip, success

from ..models import REQ_APPROVED, REQ_L2_PENDING, REQ_PENDING, WorkFromHomeRequest
from ..serializers import WorkFromHomeRequestSerializer
from .workfromhome import _can_approve_at_stage

logger = logging.getLogger(__name__)

OPEN_STATUSES = (REQ_PENDING, REQ_L2_PENDING, REQ_APPROVED)


def can_set_location_policy(user, wfh_request) -> bool:
    """True for the people who can approve this request (not its owner), while it is open or approved."""
    if wfh_request.employee_id == user.id or wfh_request.status not in OPEN_STATUSES:
        return False
    if not _has_perm(user, 'wfh.approve'):
        return False
    return _can_approve_at_stage(user, wfh_request, 'l1') or _can_approve_at_stage(user, wfh_request, 'l2')


class WorkFromHomeLocationPolicyView(APIView):
    """POST /wfh/requests/<id>/location-policy/  {"allow_any_location": true | false}"""
    permission_classes = [IsAuthenticated, HasCompletedOnboardingStatus]

    def post(self, request, request_id: str):
        if not _has_perm(request.user, 'wfh.approve'):
            return error('Permission denied.', http_status=status.HTTP_403_FORBIDDEN)

        allow_any = request.data.get('allow_any_location')
        if not isinstance(allow_any, bool):
            return error('allow_any_location must be true or false.')

        with transaction.atomic():
            try:
                wfh_request = (
                    WorkFromHomeRequest.objects.select_related('employee', 'l1_approver', 'l2_approver')
                    .select_for_update(of=('self',)).get(id=request_id)
                )
            except (WorkFromHomeRequest.DoesNotExist, ValidationError, ValueError):
                return error('Work from home request not found.', http_status=status.HTTP_404_NOT_FOUND)

            if wfh_request.employee_id == request.user.id:
                return error('You cannot change the location check on your own request.', http_status=status.HTTP_403_FORBIDDEN)
            if not (_can_approve_at_stage(request.user, wfh_request, 'l1') or _can_approve_at_stage(request.user, wfh_request, 'l2')):
                return error('You are not authorised to change this request.', http_status=status.HTTP_403_FORBIDDEN)
            if wfh_request.status not in OPEN_STATUSES:
                return error('Only a pending or approved request can be changed.')

            wfh_request.enforce_location = not allow_any
            wfh_request.location_unlocked_by = request.user if allow_any else None
            wfh_request.location_unlocked_at = timezone.now() if allow_any else None
            wfh_request.save(update_fields=['enforce_location', 'location_unlocked_by', 'location_unlocked_at', 'updated_at'])

        from apps.accounts.models import AuditLog
        AuditLog.objects.create(
            user=request.user, action='wfh_location_unlocked' if allow_any else 'wfh_location_locked', module='wfh',
            object_id=str(wfh_request.id),
            changes={
                'employee': wfh_request.employee.full_name, 'employee_id': wfh_request.employee.employee_id,
                'start_date': str(wfh_request.start_date), 'end_date': str(wfh_request.end_date),
                'allow_any_location': allow_any,
            },
            branch=wfh_request.employee.branch, ip_address=get_client_ip(request),
        )
        logger.info('WFH request %s: any-location punching %s by %s', wfh_request.id, 'allowed' if allow_any else 'stopped', request.user.pk)
        message = ('Punching is now allowed from any location for these days.' if allow_any
                   else 'Punches must be near the declared location again.')
        return success(message, WorkFromHomeRequestSerializer(wfh_request, context={'request': request}).data)
