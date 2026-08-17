import logging

from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView

from core.permissions import has_perm as _has_perm
from core.responses import error, first_error, success

from ..models import Assessment, AssessmentSection
from ..serializers import AssessmentSectionCreateSerializer, AssessmentSectionSerializer

logger = logging.getLogger(__name__)


class AssessmentSectionListCreateView(APIView):
    """
    GET  /api/assessments/<assessment_id>/sections/  — list sections
    POST /api/assessments/<assessment_id>/sections/  — add a section

    Section score = total marks allocated to this section.
    Quiz items inside the section share the section score equally.
    """
    permission_classes = [IsAuthenticated]

    def _get_assessment(self, assessment_id):
        try:
            return Assessment.objects.get(pk=assessment_id)
        except Assessment.DoesNotExist:
            return None

    def get(self, request, assessment_id):
        if not _has_perm(request.user, 'assessments.view'):
            return error('Permission denied.', http_status=status.HTTP_403_FORBIDDEN)
        assessment = self._get_assessment(assessment_id)
        if not assessment:
            return error('Assessment not found.', http_status=status.HTTP_404_NOT_FOUND)
        sections = assessment.sections.prefetch_related('items').all()
        return success('Sections retrieved.', AssessmentSectionSerializer(sections, many=True).data)

    def post(self, request, assessment_id):
        if not _has_perm(request.user, 'assessments.edit'):
            return error('Permission denied.', http_status=status.HTTP_403_FORBIDDEN)
        assessment = self._get_assessment(assessment_id)
        if not assessment:
            return error('Assessment not found.', http_status=status.HTTP_404_NOT_FOUND)
        serializer = AssessmentSectionCreateSerializer(data=request.data)
        if not serializer.is_valid():
            return error(first_error(serializer.errors))
        section = serializer.save(assessment=assessment)
        logger.info('Section "%s" added to assessment "%s" by %s', section.title, assessment.title, request.user.email)
        return success(
            'Section created.',
            AssessmentSectionSerializer(section).data,
            http_status=status.HTTP_201_CREATED,
        )


class AssessmentSectionDetailView(APIView):
    """
    PUT    /api/assessments/<assessment_id>/sections/<section_id>/  — update title/order/score
    DELETE /api/assessments/<assessment_id>/sections/<section_id>/  — remove section
                                                                       (items become unsectioned)
    """
    permission_classes = [IsAuthenticated]

    def _get(self, assessment_id, section_id):
        try:
            return AssessmentSection.objects.prefetch_related('items').get(
                pk=section_id, assessment_id=assessment_id,
            )
        except AssessmentSection.DoesNotExist:
            return None

    def put(self, request, assessment_id, section_id):
        if not _has_perm(request.user, 'assessments.edit'):
            return error('Permission denied.', http_status=status.HTTP_403_FORBIDDEN)
        section = self._get(assessment_id, section_id)
        if not section:
            return error('Section not found.', http_status=status.HTTP_404_NOT_FOUND)
        serializer = AssessmentSectionCreateSerializer(section, data=request.data)
        if not serializer.is_valid():
            return error(first_error(serializer.errors))
        serializer.save()
        logger.info('Section "%s" updated by %s', section.title, request.user.email)
        return success('Section updated.', AssessmentSectionSerializer(serializer.instance).data)

    def delete(self, request, assessment_id, section_id):
        if not _has_perm(request.user, 'assessments.edit'):
            return error('Permission denied.', http_status=status.HTTP_403_FORBIDDEN)
        section = self._get(assessment_id, section_id)
        if not section:
            return error('Section not found.', http_status=status.HTTP_404_NOT_FOUND)
        title = section.title
        section.items.update(section=None)
        section.delete()
        logger.info('Section "%s" deleted by %s — items moved to unsectioned', title, request.user.email)
        return success('Section deleted. Items moved to unsectioned.')
