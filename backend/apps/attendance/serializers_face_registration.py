"""
Serializers for Face Registration APIs.

Write serializers validate incoming requests.
Read serializers shape outgoing responses.
"""
from __future__ import annotations

from django.contrib.auth import get_user_model
from rest_framework import serializers

from apps.attendance.models import FaceRegistrationRequest

User = get_user_model()


# ══════════════════════════════════════════════════════════════════════════════
#  Write serializers
# ══════════════════════════════════════════════════════════════════════════════

def _validate_consent_acknowledged(value: bool) -> bool:
    """
    Shared validator for both submit serializers below — must be explicitly
    True, not just "present". A missing/False value means the consent
    checkbox was never actually ticked, so the request must be rejected
    rather than silently defaulting consent to given.
    """
    if not value:
        raise serializers.ValidationError(
            'You must acknowledge the biometric consent notice before submitting a face capture.'
        )
    return value


class FaceRegistrationSubmitSerializer(serializers.Serializer):
    """
    POST /api/attendance/face-registration/

    Accepts only the already-computed embedding vector and liveness-check
    result the frontend produced — never a raw image. consent_acknowledged
    confirms the employee ticked the consent notice shown before capture
    started (FaceRegistrationModal) — the view stamps the actual
    consent_given_at timestamp and consent_text_version server-side from
    this boolean, never trusting a client-supplied timestamp.
    """
    face_embedding       = serializers.ListField(child=serializers.FloatField(), allow_empty=False)
    liveness_passed      = serializers.BooleanField()
    liveness_score       = serializers.FloatField(required=False, allow_null=True, default=None)
    consent_acknowledged = serializers.BooleanField(validators=[_validate_consent_acknowledged])


class FaceRegistrationHRRegisterSerializer(serializers.Serializer):
    """
    POST /api/attendance/face-registration/register/

    Same capture fields as FaceRegistrationSubmitSerializer, plus which
    employee this capture is for — the view resolves employee_uuid and
    checks it's a real, active user before anything is created.
    consent_acknowledged here confirms HR obtained the employee's consent in
    person before this witnessed capture (HRFaceCaptureModal) — same
    server-side timestamp handling as the self-service path.
    """
    employee_uuid        = serializers.CharField()
    face_embedding       = serializers.ListField(child=serializers.FloatField(), allow_empty=False)
    liveness_passed      = serializers.BooleanField()
    liveness_score       = serializers.FloatField(required=False, allow_null=True, default=None)
    consent_acknowledged = serializers.BooleanField(validators=[_validate_consent_acknowledged])


class FaceRegistrationDecisionSerializer(serializers.Serializer):
    """PATCH /api/attendance/face-registration/<uuid:pk>/review/"""
    status = serializers.ChoiceField(choices=[
        FaceRegistrationRequest.STATUS_APPROVED,
        FaceRegistrationRequest.STATUS_REJECTED,
    ])
    notes  = serializers.CharField(max_length=1000, required=False, allow_blank=True, default='')


# ══════════════════════════════════════════════════════════════════════════════
#  Read serializers
# ══════════════════════════════════════════════════════════════════════════════

class FaceRegistrationReadSerializer(serializers.ModelSerializer):
    """
    Excludes face_embedding — an approver decides from liveness_passed/
    liveness_score alone and never needs the raw vector, so it's never
    sent back over the wire.
    """
    employee_name    = serializers.SerializerMethodField()
    employee_email   = serializers.SerializerMethodField()
    approved_by_name = serializers.SerializerMethodField()

    class Meta:
        model  = FaceRegistrationRequest
        fields = [
            'id', 'employee_name', 'employee_email',
            'liveness_passed', 'liveness_score', 'embedding_model_version',
            'status', 'approved_by_name', 'approved_at', 'notes', 'created_at',
        ]

    def get_employee_name(self, obj: FaceRegistrationRequest) -> str:
        return obj.employee.full_name if obj.employee_id else ''

    def get_employee_email(self, obj: FaceRegistrationRequest) -> str:
        return obj.employee.email if obj.employee_id else ''

    def get_approved_by_name(self, obj: FaceRegistrationRequest) -> str:
        return obj.approved_by.full_name if obj.approved_by_id else ''


class FaceRegistrationEmployeeSerializer(serializers.ModelSerializer):
    """
    Minimal projection for the HR face-registration employee picker —
    deliberately excludes profile/bank/address fields that a general
    employee-list endpoint would carry; this picker only needs enough to
    identify who's sitting in front of the camera.
    """
    uuid = serializers.CharField(source='id')

    class Meta:
        model  = User
        fields = ['uuid', 'employee_id', 'full_name', 'email', 'branch', 'department', 'designation']
