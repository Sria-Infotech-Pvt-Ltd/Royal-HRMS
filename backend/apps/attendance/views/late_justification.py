"""
Late-arrival justification endpoints (AttendanceCorrection, kind=late_justification).

POST /api/attendance/late-justification/                  employee: submit for one of their own late days
POST /api/attendance/late-justification/<uuid>/resubmit/  employee: resubmit after "Resubmission Required"
GET  /api/attendance/corrections/<uuid>/document/         the proof, streamed (never a public link)

Listing and review reuse /api/attendance/corrections/ (kind / missing_proof
filters), /api/attendance/corrections/my/ and
/api/attendance/corrections/<uuid>/review/ (approve | reject | resubmit).
The employee is always request.user: no endpoint accepts another employee.
"""
from __future__ import annotations

import logging

from django.http import HttpResponse
from django.utils.http import content_disposition_header
from rest_framework import serializers, status
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView

from core.responses import error, first_error, success

from apps.attendance import services_late_justification as late
from apps.attendance.models import AttendanceCorrection
from apps.attendance.services_hr_corrections import _build_row

logger = logging.getLogger(__name__)


class _SubmitSerializer(serializers.Serializer):
    date        = serializers.DateField()
    reason      = serializers.ChoiceField(choices=AttendanceCorrection.LATE_REASONS)
    explanation = serializers.CharField(allow_blank=True, max_length=late.EXPLANATION_MAX)
    document    = serializers.FileField(required=False, allow_null=True)


class _ResubmitSerializer(serializers.Serializer):
    reason      = serializers.ChoiceField(choices=AttendanceCorrection.LATE_REASONS, required=False)
    explanation = serializers.CharField(allow_blank=True, max_length=late.EXPLANATION_MAX)
    document    = serializers.FileField(required=False, allow_null=True)


def _late_error(exc: late.LateJustificationError):
    if exc.field == 'not_found':
        return error(str(exc), http_status=status.HTTP_404_NOT_FOUND)
    return error(str(exc), data={exc.field: [str(exc)]} if exc.field else None,
                 http_status=status.HTTP_400_BAD_REQUEST)


class LateJustificationSubmitView(APIView):
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser, JSONParser]

    def post(self, request):
        ser = _SubmitSerializer(data=request.data)
        if not ser.is_valid():
            return error(first_error(ser.errors), data=ser.errors)
        d = ser.validated_data
        try:
            correction = late.submit(employee=request.user, day=d['date'], reason=d['reason'],
                                     explanation=d['explanation'], document=d.get('document'))
        except late.LateJustificationError as exc:
            return _late_error(exc)
        return success('Late arrival justification submitted. You will be notified once it is reviewed.',
                       _build_row(correction, viewer=request.user), http_status=status.HTTP_201_CREATED)


class LateJustificationResubmitView(APIView):
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser, JSONParser]

    def post(self, request, pk):
        ser = _ResubmitSerializer(data=request.data)
        if not ser.is_valid():
            return error(first_error(ser.errors), data=ser.errors)
        d = ser.validated_data
        try:
            correction = late.resubmit(employee=request.user, correction_id=pk, explanation=d['explanation'],
                                       reason=d.get('reason'), document=d.get('document'))
        except late.LateJustificationError as exc:
            return _late_error(exc)
        return success('Justification resubmitted for review.', _build_row(correction, viewer=request.user))


class CorrectionDocumentView(APIView):
    """The proof file — only for its uploader and users with medical-proof access."""
    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        correction = (AttendanceCorrection.objects.select_related('employee')
                      .filter(pk=pk, kind=AttendanceCorrection.KIND_LATE).first())
        # Same answer for "doesn't exist" and "not allowed": nothing about the request leaks.
        if correction is None or not late.can_view_document(request.user, correction):
            return error('Document not available.', http_status=status.HTTP_404_NOT_FOUND)
        try:
            content, content_type = late.read_document(correction)
        except Exception:
            logger.warning('Could not read late-justification proof for %s', correction.pk, exc_info=True)
            return error('Could not load the document. Please try again.', http_status=status.HTTP_502_BAD_GATEWAY)
        response = HttpResponse(content, content_type=content_type)
        response['Content-Disposition'] = content_disposition_header(
            as_attachment=request.query_params.get('download') == '1',
            filename=correction.document_name or 'proof')
        response['Cache-Control'] = 'private, no-store'
        response['X-Content-Type-Options'] = 'nosniff'
        return response
