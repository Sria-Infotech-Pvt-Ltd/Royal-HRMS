import logging

from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView

from core.responses import error, first_error, success

from ..models import AssessmentSettings
from ..serializers import AssessmentSettingsSerializer

logger = logging.getLogger(__name__)


def _has_perm(user, codename: str) -> bool:
    if not user or not user.role:
        return False
    return user.role.role_permissions.filter(permission__codename=codename).exists()


class AssessmentSettingsView(APIView):
    """
    GET  /api/assessments/settings/  — retrieve global assessment defaults
    PUT  /api/assessments/settings/  — update global assessment defaults

    These values are applied to every assessment unless the assessment has
    its own per-assessment override (max_attempts, time_limit_mins).
    pass_percentage on individual assessments is always stored explicitly.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        if not _has_perm(request.user, 'assessments.view'):
            return error('Permission denied.', http_status=403)
        settings = AssessmentSettings.load()
        return success('Settings retrieved.', AssessmentSettingsSerializer(settings).data)

    def put(self, request):
        if not _has_perm(request.user, 'assessments.edit'):
            return error('Permission denied.', http_status=403)
        settings = AssessmentSettings.load()
        serializer = AssessmentSettingsSerializer(settings, data=request.data)
        if not serializer.is_valid():
            return error(first_error(serializer.errors))
        serializer.save()
        logger.info('Assessment settings updated by %s', request.user.email)
        return success('Settings updated.', AssessmentSettingsSerializer(settings).data)
