"""
HR-side employee photo upload — the "Edit full record" modal's Personal
identity section needs HR to be able to set an employee's photo on their
behalf, which views_profile_photo.py's ProfilePhotoView deliberately does
NOT support (that view is documented as self-service only, always acting
on `request.user`, with no target-employee parameter at all). Rather than
repurpose that view and contradict its own stated contract, this is a
separate, explicitly HR-gated endpoint reusing the same validation/
compression serializer.
"""
from __future__ import annotations

import logging

from rest_framework import status
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from core.permissions import has_perm
from core.responses import error, first_error, success

from apps.accounts.serializers_profile_photo import ProfilePhotoUploadSerializer
from apps.accounts.views.shared import _get_employee, _employee_out_of_branch_scope

logger = logging.getLogger(__name__)


def _photo_url(user, request) -> str | None:
    if not user.profile_photo:
        return None
    return request.build_absolute_uri(user.profile_photo.url) if request else user.profile_photo.url


class EmployeePhotoView(APIView):
    """POST /api/employees/<employee_id>/photo/ — HR sets an employee's
    display photo on their behalf (Edit full record > Personal identity)."""

    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser]

    def post(self, request: Request, employee_id: str) -> Response:
        if not has_perm(request.user, 'employees.edit'):
            return error('You do not have permission to change this employee\'s photo.', http_status=status.HTTP_403_FORBIDDEN)

        target = _get_employee(employee_id)
        if target is None or _employee_out_of_branch_scope(request.user, target):
            return error('Employee not found.', http_status=status.HTTP_404_NOT_FOUND)

        serializer = ProfilePhotoUploadSerializer(data=request.data)
        if not serializer.is_valid():
            return error(first_error(serializer.errors), data=serializer.errors, http_status=status.HTTP_422_UNPROCESSABLE_ENTITY)

        if target.profile_photo:
            target.profile_photo.delete(save=False)
        target.profile_photo = serializer.validated_data['photo']
        target.save(update_fields=['profile_photo', 'updated_at'])

        logger.info('Profile photo for %s updated by %s', target.email, request.user.email)
        return success('Profile photo updated successfully.', {'profile_photo_url': _photo_url(target, request)})
