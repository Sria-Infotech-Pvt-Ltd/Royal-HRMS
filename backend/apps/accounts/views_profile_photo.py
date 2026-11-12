"""
Profile photo — self-service upload for the requesting user's own display
photo (shown in the sidebar, header, and Profile page). Every authenticated
user manages their own, including system_admin — this is identity display,
not a permission-gated HR action.

Deliberately its own file, not views.py (already far past the 300-line
convention) — mirrors the split pattern used elsewhere (e.g.
apps.attendance.views.face_registration).
"""
from __future__ import annotations

import logging

from rest_framework import status
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from core.responses import error, first_error, success

from apps.accounts.serializers_profile_photo import ProfilePhotoUploadSerializer

logger = logging.getLogger(__name__)


def _photo_url(user, request) -> str | None:
    if not user.profile_photo:
        return None
    return request.build_absolute_uri(user.profile_photo.url) if request else user.profile_photo.url


class ProfilePhotoView(APIView):
    """
    POST   /api/employees/me/photo/  — upload or replace own profile photo
    DELETE /api/employees/me/photo/  — remove own profile photo
    """

    permission_classes = [IsAuthenticated]
    parser_classes     = [MultiPartParser, FormParser]

    def post(self, request: Request) -> Response:
        serializer = ProfilePhotoUploadSerializer(data=request.data)
        if not serializer.is_valid():
            return error(
                first_error(serializer.errors),
                data=serializer.errors,
                http_status=status.HTTP_422_UNPROCESSABLE_ENTITY,
            )

        user = request.user
        # Replace old photo file when a new one is uploaded — same pattern as
        # Company.logo replacement (views.py CompanyRetrieveUpdateView).
        if user.profile_photo:
            user.profile_photo.delete(save=False)
        user.profile_photo = serializer.validated_data['photo']
        user.save(update_fields=['profile_photo', 'updated_at'])

        logger.info('Profile photo updated by %s', user.email)
        return success('Profile photo updated successfully.', {
            'profile_photo_url': _photo_url(user, request),
        })

    def delete(self, request: Request) -> Response:
        user = request.user
        if user.profile_photo:
            user.profile_photo.delete(save=False)
            user.profile_photo = None
            user.save(update_fields=['profile_photo', 'updated_at'])

        logger.info('Profile photo removed by %s', user.email)
        return success('Profile photo removed successfully.', {'profile_photo_url': None})
