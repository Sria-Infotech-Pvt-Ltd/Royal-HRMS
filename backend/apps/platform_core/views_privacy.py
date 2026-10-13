"""
Phase 9B Task E — DSR intake (self-service, any authenticated employee can
file a request about themselves) + HR fulfilment queue (gated on the new
`privacy.manage_dsr` codename, same seeded-permission convention as
`hr_help.respond`/`employees.confirm`).
"""
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView

from apps.platform_core.models import DataSubjectRequest
from apps.platform_core.services_privacy import (
    DSRAlreadyFulfilledError, create_request, fulfil_access_or_export_request,
    fulfil_erasure_request, reject_request,
)
from core.permissions import BasePermission, has_perm
from core.responses import error, success


class HasPrivacyPermission(BasePermission):
    message = 'You do not have permission to manage data subject requests.'

    def has_permission(self, request, view) -> bool:
        return bool(request.user and request.user.is_authenticated and has_perm(request.user, 'privacy.manage_dsr'))


def _dsr_dict(dsr: DataSubjectRequest) -> dict:
    return {
        'id': str(dsr.id), 'request_type': dsr.request_type, 'status': dsr.status,
        'subject_user_id': str(dsr.subject_user_id), 'reason': dsr.reason,
        'rejection_reason': dsr.rejection_reason, 'fulfilment_evidence': dsr.fulfilment_evidence,
        'created_at': str(dsr.created_at), 'fulfilled_at': str(dsr.fulfilled_at) if dsr.fulfilled_at else None,
    }


class MyDataSubjectRequestListCreateView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        qs = DataSubjectRequest.objects.filter(subject_user=request.user).order_by('-created_at')
        return success('Your data subject requests.', [_dsr_dict(d) for d in qs])

    def post(self, request):
        request_type = request.data.get('request_type')
        if request_type not in dict(DataSubjectRequest.TYPE_CHOICES):
            return error('request_type must be one of access/export/erasure.')
        dsr = create_request(
            request_type=request_type, subject_user=request.user, requested_by=request.user,
            reason=request.data.get('reason', ''),
        )
        return success('Request filed.', _dsr_dict(dsr), http_status=201)


class DataSubjectRequestQueueView(APIView):
    permission_classes = [HasPrivacyPermission]

    def get(self, request):
        qs = DataSubjectRequest.objects.all().order_by('-created_at')
        status_filter = request.query_params.get('status')
        if status_filter:
            qs = qs.filter(status=status_filter)
        return success('Data subject request queue.', [_dsr_dict(d) for d in qs[:200]])


class DataSubjectRequestFulfilView(APIView):
    permission_classes = [HasPrivacyPermission]

    def post(self, request, pk):
        try:
            dsr = DataSubjectRequest.objects.get(pk=pk)
        except DataSubjectRequest.DoesNotExist:
            return error('Request not found.', http_status=404)

        action = request.data.get('action')
        try:
            if action == 'reject':
                dsr = reject_request(dsr, reason=request.data.get('reason', ''))
            elif dsr.request_type == DataSubjectRequest.TYPE_ERASURE:
                dsr = fulfil_erasure_request(dsr, fulfilled_by=request.user)
            else:
                dsr = fulfil_access_or_export_request(dsr, fulfilled_by=request.user)
        except DSRAlreadyFulfilledError as exc:
            return error(str(exc))
        return success('Request updated.', _dsr_dict(dsr))
