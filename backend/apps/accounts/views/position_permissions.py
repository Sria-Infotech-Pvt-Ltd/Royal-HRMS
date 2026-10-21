"""What access a seat carries — replaces assigning permissions through Roles.

GET  /org-structure/positions/<id>/permissions/  -> the seat's permission codenames and scope flags
PUT  /org-structure/positions/<id>/permissions/  -> replace them (settings.edit only; audit-logged)
"""
import logging

from django.db import transaction
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView

from apps.accounts.models import AuditLog, Permission, Position, PositionPermission
from core.permissions import has_perm as _has_perm
from core.responses import error, get_client_ip, success

logger = logging.getLogger(__name__)


def _seat_payload(position: Position) -> dict:
    codenames = sorted(position.position_permissions.values_list('permission__codename', flat=True))
    return {
        'position': str(position.pk),
        'codenames': codenames,
        'can_manage_team': position.can_manage_team,
        'can_manage_branch': position.can_manage_branch,
    }


class PositionPermissionsView(APIView):
    permission_classes = [IsAuthenticated]

    def _position(self, pk):
        return Position.objects.filter(pk=pk).first()

    def get(self, request, pk):
        if not _has_perm(request.user, 'org_chart.view'):
            return error('You do not have permission to view the org structure.', http_status=status.HTTP_403_FORBIDDEN)
        position = self._position(pk)
        if not position:
            return error('Position not found.', http_status=status.HTTP_404_NOT_FOUND)
        return success('Position permissions retrieved.', data=_seat_payload(position))

    def put(self, request, pk):
        if not _has_perm(request.user, 'settings.edit'):
            return error('Only a full-access user can change what a position is allowed to do.', http_status=status.HTTP_403_FORBIDDEN)
        position = self._position(pk)
        if not position:
            return error('Position not found.', http_status=status.HTTP_404_NOT_FOUND)

        codenames = request.data.get('codenames')
        if not isinstance(codenames, list) or not all(isinstance(item, str) for item in codenames):
            return error('codenames must be a list of permission codenames.', http_status=status.HTTP_400_BAD_REQUEST)
        wanted = set(codenames)
        known = set(Permission.objects.filter(codename__in=wanted).values_list('codename', flat=True))
        if wanted - known:
            return error(f'Unknown permission(s): {", ".join(sorted(wanted - known))}.', http_status=status.HTTP_400_BAD_REQUEST)

        before = _seat_payload(position)
        with transaction.atomic():
            position.position_permissions.exclude(permission__codename__in=wanted).delete()
            have = set(position.position_permissions.values_list('permission__codename', flat=True))
            for permission in Permission.objects.filter(codename__in=wanted - have):
                PositionPermission.objects.create(position=position, permission=permission, granted_by=request.user)
            for flag in ('can_manage_team', 'can_manage_branch'):
                if flag in request.data:
                    setattr(position, flag, bool(request.data[flag]))
            position.save(update_fields=['can_manage_team', 'can_manage_branch', 'updated_at'])
        after = _seat_payload(position)
        AuditLog.objects.create(
            user=request.user, action='position_permissions_update', module='org_structure',
            object_id=str(position.pk), changes={'before': before, 'after': after},
            ip_address=get_client_ip(request),
        )
        logger.info('Position %s permissions updated by %s', position.pk, request.user.employee_id)
        return success('Position permissions updated.', data=after)
