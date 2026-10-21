"""The permissions EVERY employee has, whatever seat they hold (self-service) — replaces the default employee role.

GET  /settings/baseline-permissions/  -> codenames (any authenticated user: the UI needs them to render)
PUT  /settings/baseline-permissions/  -> replace the set (settings.edit only; audit-logged)
"""
import logging

from django.db import transaction
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView

from apps.accounts.models import AuditLog, BaselinePermission, Permission
from core.access import baseline_codenames
from core.permissions import has_perm as _has_perm
from core.responses import error, get_client_ip, success

logger = logging.getLogger(__name__)


class BaselinePermissionsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        return success('Baseline permissions retrieved.', data={'codenames': sorted(baseline_codenames())})

    def put(self, request):
        if not _has_perm(request.user, 'settings.edit'):
            return error('Only a full-access user can change what every employee is allowed to do.', http_status=status.HTTP_403_FORBIDDEN)
        codenames = request.data.get('codenames')
        if not isinstance(codenames, list) or not all(isinstance(item, str) for item in codenames):
            return error('codenames must be a list of permission codenames.', http_status=status.HTTP_400_BAD_REQUEST)
        wanted = set(codenames)
        known = set(Permission.objects.filter(codename__in=wanted).values_list('codename', flat=True))
        if wanted - known:
            return error(f'Unknown permission(s): {", ".join(sorted(wanted - known))}.', http_status=status.HTTP_400_BAD_REQUEST)
        # Granting full access to every employee would hand the whole system to everyone.
        if 'settings.edit' in wanted:
            return error('settings.edit cannot be a baseline permission.', http_status=status.HTTP_400_BAD_REQUEST)

        before = sorted(baseline_codenames())
        with transaction.atomic():
            BaselinePermission.objects.exclude(permission__codename__in=wanted).delete()
            for permission in Permission.objects.filter(codename__in=wanted - set(before)):
                BaselinePermission.objects.create(permission=permission)
        after = sorted(baseline_codenames())
        AuditLog.objects.create(
            user=request.user, action='baseline_permissions_update', module='settings',
            changes={'before': before, 'after': after}, ip_address=get_client_ip(request),
        )
        logger.info('Baseline permissions updated by %s', request.user.employee_id)
        return success('Baseline permissions updated.', data={'codenames': after})
