"""
HR-initiated face registration — HR captures a face in person (e.g. during
onboarding) and registers or updates an employee's face ID directly, rather
than the employee self-submitting for a separate approver's review.

Split out of face_registration.py (same domain, kept in its own file to stay
under the 300-line convention) — reuses that file's _has_perm/_resolve_branch
helpers rather than duplicating them.

Endpoints:
  GET  /api/attendance/face-registration/employees/                — Org-wide employee picker, with each person's Face ID state
                                                                       (?face_status=incomplete|approved|pending|rejected|none) and overall counts
  GET  /api/attendance/face-registration/employees/<uuid>/status/  — Any employee's latest status
  POST /api/attendance/face-registration/register/                 — Register/update, auto-approved
"""
from __future__ import annotations

import logging

from django.contrib.auth import get_user_model
from django.db import transaction
from django.db.models import Q
from django.utils import timezone
from rest_framework import status
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView

from core.pagination import paginate, paginated_data
from core.permissions import RequiresSecureTransport
from core.responses import error, first_error, success

from apps.attendance.models import (
    FACE_CONSENT_TEXT_VERSION,
    FACE_RECOGNITION_MODEL_VERSION,
    FaceRegistrationRequest,
)
from apps.attendance.serializers_face_registration import (
    FaceRegistrationHRRegisterSerializer,
    FaceRegistrationReadSerializer,
    FaceRosterEmployeeSerializer,
)
from apps.attendance.services_face_matching import activate_registration, is_face_verification_mandatory
from apps.attendance.services_face_roster import annotate_face_state, apply_face_filter, face_counts
from apps.attendance.views.face_registration import (
    _FEATURE_DISABLED_MESSAGE,
    _has_perm,
    _resolve_branch,
)

logger = logging.getLogger(__name__)
User   = get_user_model()


class FaceRegistrationEmployeePickerView(APIView):
    """
    GET /api/attendance/face-registration/employees/?search=

    Org-wide employee picker for the HR "register/update face ID" screen —
    deliberately NOT the general accounts.EmployeeListCreateView, which
    auto-scopes to a manager's direct reports or the caller's own branch and
    returns a much heavier, PII-laden payload. Anyone who can approve face
    registrations can look up any active employee here, in a minimal shape.
    """

    permission_classes = [IsAuthenticated]

    def get(self, request: Request) -> Response:
        if not _has_perm(request.user, 'facial_recognition.approve'):
            return error('Permission denied.', http_status=status.HTTP_403_FORBIDDEN)

        queryset = User.objects.filter(is_active=True).order_by('full_name')
        search = request.query_params.get('search', '').strip()
        if search:
            queryset = queryset.filter(
                Q(full_name__icontains=search) |
                Q(email__icontains=search) |
                Q(employee_id__icontains=search)
            )

        # Each person's Face ID state, plus totals over everyone (not narrowed by the search or the filter), so the page can show
        # how far registration has got and who has not completed it.
        annotated = annotate_face_state(queryset)
        counts = face_counts(annotate_face_state(User.objects.filter(is_active=True)))
        annotated = apply_face_filter(annotated, request.query_params.get('face_status', ''))

        page_obj, paginator = paginate(annotated, request)
        serializer = FaceRosterEmployeeSerializer(page_obj.object_list, many=True)
        data = paginated_data(paginator, page_obj, serializer.data)
        data['counts'] = counts
        return success(f'{paginator.count} employee(s) found.', data)


class FaceRegistrationEmployeeStatusView(APIView):
    """
    GET /api/attendance/face-registration/employees/<uuid:employee_uuid>/status/

    Same shape as FaceRegistrationMyStatusView, but for a given employee
    instead of the caller — lets the HR picker show whether the selected
    person already has a face ID registered before HR captures a new one.
    """

    permission_classes = [IsAuthenticated]

    def get(self, request: Request, employee_uuid) -> Response:
        if not _has_perm(request.user, 'facial_recognition.approve'):
            return error('Permission denied.', http_status=status.HTTP_403_FORBIDDEN)

        latest = (
            FaceRegistrationRequest.objects
            .filter(employee_id=employee_uuid)
            .order_by('-created_at')
            .first()
        )
        if not latest:
            return success('No face registration found.', None)
        return success(
            'Face registration status retrieved.',
            FaceRegistrationReadSerializer(latest).data,
        )


class FaceRegistrationHRRegisterView(APIView):
    """
    POST /api/attendance/face-registration/register/

    HR captures a face in person (e.g. during onboarding) and registers or
    replaces an employee's face ID directly — approved immediately since HR
    witnessed the capture themselves, unlike the self-submit flow which
    always starts pending. activate_registration marks this fresh row as
    the employee's sole active reference, so "register new" and "update
    existing" are the same action with no schema change.
    """

    permission_classes = [IsAuthenticated, RequiresSecureTransport]

    def post(self, request: Request) -> Response:
        if not _has_perm(request.user, 'facial_recognition.approve'):
            return error('Permission denied.', http_status=status.HTTP_403_FORBIDDEN)
        if not is_face_verification_mandatory():
            return error(_FEATURE_DISABLED_MESSAGE, http_status=status.HTTP_403_FORBIDDEN)

        serializer = FaceRegistrationHRRegisterSerializer(data=request.data)
        if not serializer.is_valid():
            return error(
                first_error(serializer.errors),
                data=serializer.errors,
                http_status=status.HTTP_422_UNPROCESSABLE_ENTITY,
            )

        data = serializer.validated_data
        try:
            employee = User.objects.get(pk=data['employee_uuid'], is_active=True)
        except (User.DoesNotExist, ValueError, TypeError):
            return error('Employee not found.', http_status=status.HTTP_404_NOT_FOUND)

        # Same rule as the self-service submit path — an HR witness present
        # in person is not a substitute for the capture's own liveness/motion
        # check actually passing.
        if not data['liveness_passed']:
            return error(
                'Liveness check did not pass. Please try again in good lighting, facing the camera directly.',
                http_status=status.HTTP_422_UNPROCESSABLE_ENTITY,
            )

        # consent_acknowledged (validated True-or-reject by the serializer)
        # confirms HR obtained the employee's consent in person before this
        # witnessed capture — stamped server-side, same as the self-service path.
        with transaction.atomic():
            face_request = FaceRegistrationRequest.objects.create(
                employee=employee,
                branch=_resolve_branch(employee),
                face_embedding=data['face_embedding'],
                embedding_model_version=FACE_RECOGNITION_MODEL_VERSION,
                liveness_passed=data['liveness_passed'],
                liveness_score=data.get('liveness_score'),
                capture_frame_count=data.get('capture_frame_count'),
                capture_variance=data.get('capture_variance'),
                status=FaceRegistrationRequest.STATUS_APPROVED,
                approved_by=request.user,
                approved_at=timezone.now(),
                notes='Registered directly by HR.',
                consent_given_at=timezone.now(),
                consent_text_version=FACE_CONSENT_TEXT_VERSION,
            )
            activate_registration(face_request)
        logger.info('Face registration for %s captured and auto-approved by %s', employee.email, request.user.email)

        return success(
            'Face ID registered successfully.',
            FaceRegistrationReadSerializer(face_request).data,
            http_status=status.HTTP_201_CREATED,
        )
