import logging
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated

from core.responses import success, error, first_error
from apps.payroll.models import PayrollSettings
from apps.payroll.serializers import PayrollSettingsSerializer

logger = logging.getLogger(__name__)


def _has_perm(user, codename: str) -> bool:
    if not user or not user.role:
        return False
    if getattr(user, 'is_superuser', False):
        return True
    return user.role.role_permissions.filter(permission__codename=codename).exists()


class PayrollSettingsView(APIView):
    """GET — return current settings (create defaults if none exist).
       PUT — update settings. HR admin and system_admin only."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        settings_obj, _ = PayrollSettings.objects.get_or_create(
            pk=PayrollSettings.objects.values_list('pk', flat=True).first()
            or '00000000-0000-0000-0000-000000000001',
            defaults={
                'id': '00000000-0000-0000-0000-000000000001',
            },
        )
        serializer = PayrollSettingsSerializer(settings_obj)
        return success('Payroll settings retrieved.', serializer.data)

    def put(self, request):
        if not _has_perm(request.user, 'payroll.edit'):
            return error('Only HR admin can update payroll settings.', http_status=403)

        settings_obj = PayrollSettings.objects.first()
        if settings_obj is None:
            settings_obj = PayrollSettings()

        serializer = PayrollSettingsSerializer(settings_obj, data=request.data, partial=True)
        if not serializer.is_valid():
            return error(first_error(serializer.errors))

        serializer.save()
        logger.info('Payroll settings updated by %s', request.user.email)
        return success('Payroll settings updated.', serializer.data)
