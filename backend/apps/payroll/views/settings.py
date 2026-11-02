import logging
from rest_framework.views import APIView
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.permissions import IsAuthenticated

from core.responses import success, error, first_error
from core.permissions import has_perm as _has_perm
from apps.accounts.views_id_card import validate_signature_image
from apps.payroll.audit import log_change, snapshot
from apps.payroll.models import PayrollSettings
from apps.payroll.serializers import PayrollSettingsSerializer

logger = logging.getLogger(__name__)


class PayrollSettingsView(APIView):
    """GET — return current settings (create defaults if none exist).
       PUT — update settings. HR admin and system_admin only."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        if not _has_perm(request.user, 'payroll.view'):
            return error('Only HR admin can view payroll settings.', http_status=403)

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

        before = snapshot(settings_obj) if settings_obj.pk and PayrollSettings.objects.filter(pk=settings_obj.pk).exists() else None
        serializer = PayrollSettingsSerializer(settings_obj, data=request.data, partial=True)
        if not serializer.is_valid():
            return error(first_error(serializer.errors))

        serializer.save()
        log_change(request, 'payroll_settings_updated', settings_obj.pk, before, snapshot(settings_obj))
        logger.info('Payroll settings updated by %s', request.user.email)
        return success('Payroll settings updated.', serializer.data)


class PayrollStampView(APIView):
    """POST (multipart 'stamp') — upload / replace the payslip stamp; DELETE — remove it.
    PNG / JPEG / WebP under 2 MB, stored privately (signed URLs only)."""

    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser]

    def _settings(self):
        obj = PayrollSettings.objects.first()
        return obj if obj is not None else PayrollSettings.objects.create()

    def post(self, request):
        if not _has_perm(request.user, 'payroll.edit'):
            return error('Only HR admin can update payroll settings.', http_status=403)
        upload = request.FILES.get('stamp')
        if not upload:
            return error('Choose an image to upload.')
        problem = validate_signature_image(upload)
        if problem:
            return error(problem.replace('signature', 'stamp'))
        obj = self._settings()
        old = obj.payslip_stamp.name if obj.payslip_stamp else None
        if obj.payslip_stamp:
            obj.payslip_stamp.delete(save=False)
        obj.payslip_stamp = upload
        obj.save(update_fields=['payslip_stamp', 'updated_at'])
        log_change(request, 'payroll_stamp_updated', obj.pk, {'payslip_stamp': old},
                   {'payslip_stamp': obj.payslip_stamp.name})
        return success('Stamp uploaded.', PayrollSettingsSerializer(obj).data)

    def delete(self, request):
        if not _has_perm(request.user, 'payroll.edit'):
            return error('Only HR admin can update payroll settings.', http_status=403)
        obj = self._settings()
        if obj.payslip_stamp:
            old = obj.payslip_stamp.name
            obj.payslip_stamp.delete(save=False)
            obj.payslip_stamp = None
            obj.save(update_fields=['payslip_stamp', 'updated_at'])
            log_change(request, 'payroll_stamp_updated', obj.pk, {'payslip_stamp': old}, {'payslip_stamp': None})
        return success('Stamp removed.', PayrollSettingsSerializer(obj).data)
