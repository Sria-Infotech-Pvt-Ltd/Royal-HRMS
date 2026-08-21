"""
Face Registration views.

Single-approver workflow: the facial_recognition.approve permission grant IS
the approver pool — no manager/HR approval-chain resolution like leave or
expenses, since this is an identity-verification control, not a delegated
approval.

Endpoints:
  POST  /api/attendance/face-registration/         — Employee submits embedding for approval
  GET   /api/attendance/face-registration/me/      — Employee's own latest request status
  GET   /api/attendance/face-registration/pending/  — HR/admin queue of pending requests
  PATCH /api/attendance/face-registration/<uuid:pk>/review/ — Approve/reject

HR-initiated registration (picker/register/status-by-employee, for HR
capturing a face in person on someone else's behalf) lives in
face_registration_hr.py — split out to keep this file under the 300-line
convention; it reuses _has_perm/_resolve_branch from here.
"""
from __future__ import annotations

import logging

from django.db import transaction
from django.utils import timezone
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from core.pagination import paginate, paginated_data
from core.permissions import RequiresSecureTransport, has_perm as _has_perm
from core.responses import error, first_error, success

from apps.attendance.models import (
    FACE_CONSENT_TEXT_VERSION,
    FACE_RECOGNITION_MODEL_VERSION,
    FaceRegistrationRequest,
)
from apps.attendance.serializers_face_registration import (
    FaceRegistrationDecisionSerializer,
    FaceRegistrationReadSerializer,
    FaceRegistrationSubmitSerializer,
)
from apps.attendance.services_face_matching import activate_registration, is_face_verification_mandatory

_FEATURE_DISABLED_MESSAGE = (
    'Face ID verification is currently disabled. Contact your administrator to use this feature.'
)

logger = logging.getLogger(__name__)


def _resolve_branch(user):
    branch_name = getattr(user, 'branch', None)
    if not branch_name:
        return None
    from apps.branch.models import Branch
    return Branch.objects.filter(branch_name__iexact=branch_name).first()


class FaceRegistrationSubmitView(APIView):
    """
    POST /api/attendance/face-registration/

    Any authenticated employee submits their own face embedding for
    approval — no special permission needed to submit, only to approve.
    """

    permission_classes = [IsAuthenticated, RequiresSecureTransport]

    def post(self, request: Request) -> Response:
        if not is_face_verification_mandatory():
            return error(_FEATURE_DISABLED_MESSAGE, http_status=status.HTTP_403_FORBIDDEN)

        serializer = FaceRegistrationSubmitSerializer(data=request.data)
        if not serializer.is_valid():
            return error(
                first_error(serializer.errors),
                data=serializer.errors,
                http_status=status.HTTP_422_UNPROCESSABLE_ENTITY,
            )

        data = serializer.validated_data

        # The client's own multi-frame liveness/motion check already ran
        # before this request was ever sent (see useFaceLivenessCapture) —
        # there is no path through the normal UI that submits with this
        # False. A request that does is either a bug in that client or one
        # bypassing it entirely; either way there is no reason to accept a
        # self-reported liveness failure. (This does not, and cannot on its
        # own, stop a client from simply lying and always sending True —
        # that would need server-side frame analysis, which this endpoint
        # deliberately never receives; see the "never a raw image" note on
        # FaceRegistrationSubmitSerializer.)
        if not data['liveness_passed']:
            return error(
                'Liveness check did not pass. Please try again in good lighting, facing the camera directly.',
                http_status=status.HTTP_422_UNPROCESSABLE_ENTITY,
            )

        # One pending request per employee at a time — otherwise repeatedly
        # clicking "Register Again" while HR hasn't yet reviewed the first
        # one (most likely during onboarding) floods the approval queue with
        # duplicates that only the newest is ever reachable to act on from
        # the employee's own side.
        if FaceRegistrationRequest.objects.filter(
            employee=request.user, status=FaceRegistrationRequest.STATUS_PENDING,
        ).exists():
            return error(
                'You already have a face registration request awaiting approval. '
                'Please wait for it to be reviewed before submitting another.',
                http_status=status.HTTP_409_CONFLICT,
            )

        # consent_acknowledged is validated True-or-reject by the serializer;
        # the timestamp/version actually persisted are stamped here, server-side
        # — never taken from the client — so the recorded consent moment can't
        # be backdated or forged.
        face_request = FaceRegistrationRequest.objects.create(
            employee=request.user,
            branch=_resolve_branch(request.user),
            face_embedding=data['face_embedding'],
            embedding_model_version=FACE_RECOGNITION_MODEL_VERSION,
            liveness_passed=data['liveness_passed'],
            liveness_score=data.get('liveness_score'),
            consent_given_at=timezone.now(),
            consent_text_version=FACE_CONSENT_TEXT_VERSION,
            capture_frame_count=data.get('capture_frame_count'),
            capture_variance=data.get('capture_variance'),
        )
        logger.info('Face registration submitted by %s', request.user.email)

        return success(
            'Face registration request submitted for approval.',
            FaceRegistrationReadSerializer(face_request).data,
            http_status=status.HTTP_201_CREATED,
        )


class FaceRegistrationMyStatusView(APIView):
    """
    GET /api/attendance/face-registration/me/

    The caller's own latest face registration request, any status — lets the
    web clock-in flow (useClockWidget.ts) know whether it must run the face
    capture step before punching (status == 'approved').
    """

    permission_classes = [IsAuthenticated]

    def get(self, request: Request) -> Response:
        latest = (
            FaceRegistrationRequest.objects
            .filter(employee=request.user)
            .order_by('-created_at')
            .first()
        )
        if not latest:
            return success('No face registration found.', None)
        return success(
            'Face registration status retrieved.',
            FaceRegistrationReadSerializer(latest).data,
        )


class FaceRegistrationPendingListView(APIView):
    """
    GET /api/attendance/face-registration/pending/

    HR/admin queue backing the approval UI — gated by the same
    facial_recognition.approve permission required to act on a request.
    """

    permission_classes = [IsAuthenticated]

    def get(self, request: Request) -> Response:
        if not _has_perm(request.user, 'facial_recognition.approve'):
            return error('Permission denied.', http_status=status.HTTP_403_FORBIDDEN)

        queryset = (
            FaceRegistrationRequest.objects
            .filter(status=FaceRegistrationRequest.STATUS_PENDING)
            .select_related('employee', 'approved_by')
            .order_by('-created_at')
        )
        page_obj, paginator = paginate(queryset, request)
        serializer = FaceRegistrationReadSerializer(page_obj.object_list, many=True)
        return success(
            f'{paginator.count} pending face registration request(s) found.',
            paginated_data(paginator, page_obj, serializer.data),
        )


class FaceRegistrationReviewView(APIView):
    """
    PATCH /api/attendance/face-registration/<uuid:pk>/review/

    Approve or reject a pending face registration request.
    """

    permission_classes = [IsAuthenticated]

    def patch(self, request: Request, pk) -> Response:
        if not _has_perm(request.user, 'facial_recognition.approve'):
            return error('Permission denied.', http_status=status.HTTP_403_FORBIDDEN)

        try:
            face_request = FaceRegistrationRequest.objects.select_related('employee').get(pk=pk)
        except FaceRegistrationRequest.DoesNotExist:
            return error('Face registration request not found.', http_status=status.HTTP_404_NOT_FOUND)

        if face_request.employee_id == request.user.id:
            return error(
                'You cannot approve or reject your own face registration request.',
                http_status=status.HTTP_403_FORBIDDEN,
            )
        if face_request.status != FaceRegistrationRequest.STATUS_PENDING:
            return error(
                f'Request is already {face_request.status}. Only pending requests can be actioned.',
                http_status=status.HTTP_409_CONFLICT,
            )

        serializer = FaceRegistrationDecisionSerializer(data=request.data)
        if not serializer.is_valid():
            return error(first_error(serializer.errors))

        data = serializer.validated_data
        face_request.status      = data['status']
        face_request.approved_by = request.user
        face_request.approved_at = timezone.now()
        if data.get('notes'):
            face_request.notes = data['notes']

        with transaction.atomic():
            face_request.save(update_fields=['status', 'approved_by', 'approved_at', 'notes', 'updated_at'])
            if data['status'] == FaceRegistrationRequest.STATUS_APPROVED:
                activate_registration(face_request)

        logger.info('Face registration %s %s by %s', pk, data['status'], request.user.email)

        return success(
            f"Face registration request {data['status']}.",
            FaceRegistrationReadSerializer(face_request).data,
        )


class FaceVerificationStatusView(APIView):
    """
    GET /api/attendance/face-verification/status/

    Exposes the org-wide face ID toggle (AttendanceFaceVerificationRules,
    configured on the Attendance Settings page) to every authenticated
    employee — not gated behind settings.view, since every employee's own
    Profile page and clock-in flow need to know whether the feature is on
    to render "Register your face" vs. "Contact admin to use this feature".
    """

    permission_classes = [IsAuthenticated]

    def get(self, request: Request) -> Response:
        return success(
            'Face verification status retrieved.',
            {'is_mandatory': is_face_verification_mandatory()},
        )
