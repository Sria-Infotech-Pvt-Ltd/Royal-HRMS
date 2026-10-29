"""
Reusable bulk permission bundles (PermissionTemplate) and applying one to
many positions at once — the bulk alternative to PositionPermissionsView's
one-position-at-a-time editing. See models_permission_template.py for why
applying a template is a one-time stamp, not a live binding.

GET/POST   /settings/permission-templates/                -> list / create templates
GET/PUT/DELETE /settings/permission-templates/<id>/        -> one template
POST       /settings/permission-templates/<id>/apply/      -> apply to a list of position IDs
"""
import logging

from django.db import transaction
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView

from apps.accounts.models import AuditLog, Permission, PermissionTemplate, Position, PositionPermission
from apps.accounts.serializers import PermissionTemplateSerializer
from apps.accounts.services_sessions import current_holder_ids, force_relogin
from apps.accounts.views.position_permissions import _seat_payload
from core.permissions import has_perm as _has_perm
from core.responses import error, first_error, get_client_ip, success

logger = logging.getLogger(__name__)


class PermissionTemplateListCreateView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        if not _has_perm(request.user, 'settings.edit'):
            return error('You do not have permission to perform this action.', http_status=status.HTTP_403_FORBIDDEN)
        templates = PermissionTemplate.objects.prefetch_related('permissions').all()
        return success('Permission templates retrieved.', data=PermissionTemplateSerializer(templates, many=True).data)

    def post(self, request):
        if not _has_perm(request.user, 'settings.edit'):
            return error('You do not have permission to perform this action.', http_status=status.HTTP_403_FORBIDDEN)
        serializer = PermissionTemplateSerializer(data=request.data)
        if not serializer.is_valid():
            return error(first_error(serializer.errors), data=serializer.errors)
        template = serializer.save(created_by=request.user)
        AuditLog.objects.create(
            user=request.user, action='permission_template_created', module='settings',
            object_id=str(template.pk), changes={'name': template.name},
            ip_address=get_client_ip(request),
        )
        return success('Permission template created.', data=PermissionTemplateSerializer(template).data, http_status=status.HTTP_201_CREATED)


class PermissionTemplateDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def _get(self, pk):
        return PermissionTemplate.objects.prefetch_related('permissions').filter(pk=pk).first()

    def put(self, request, pk):
        if not _has_perm(request.user, 'settings.edit'):
            return error('You do not have permission to perform this action.', http_status=status.HTTP_403_FORBIDDEN)
        template = self._get(pk)
        if not template:
            return error('Permission template not found.', http_status=status.HTTP_404_NOT_FOUND)
        serializer = PermissionTemplateSerializer(template, data=request.data, partial=False)
        if not serializer.is_valid():
            return error(first_error(serializer.errors), data=serializer.errors)
        serializer.save()
        AuditLog.objects.create(
            user=request.user, action='permission_template_updated', module='settings',
            object_id=str(template.pk), changes={'name': template.name},
            ip_address=get_client_ip(request),
        )
        return success('Permission template updated.', data=serializer.data)

    def delete(self, request, pk):
        if not _has_perm(request.user, 'settings.edit'):
            return error('You do not have permission to perform this action.', http_status=status.HTTP_403_FORBIDDEN)
        template = self._get(pk)
        if not template:
            return error('Permission template not found.', http_status=status.HTTP_404_NOT_FOUND)
        name = template.name
        template.delete()
        AuditLog.objects.create(
            user=request.user, action='permission_template_deleted', module='settings',
            object_id=str(pk), changes={'name': name},
            ip_address=get_client_ip(request),
        )
        return success('Permission template deleted.')


class PermissionTemplateApplyView(APIView):
    """Applies one template's permission set + scope flags to every position
    listed in `position_ids`, replacing (not merging with) whatever that
    position already had — same "replace" semantics as
    PositionPermissionsView.put() for a single position, just looped over
    many at once inside one transaction."""
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        if not _has_perm(request.user, 'settings.edit'):
            return error('You do not have permission to perform this action.', http_status=status.HTTP_403_FORBIDDEN)
        template = PermissionTemplate.objects.prefetch_related('permissions').filter(pk=pk).first()
        if not template:
            return error('Permission template not found.', http_status=status.HTTP_404_NOT_FOUND)

        position_ids = request.data.get('position_ids')
        if not isinstance(position_ids, list) or not position_ids:
            return error('position_ids must be a non-empty list.', http_status=status.HTTP_400_BAD_REQUEST)

        positions = list(Position.objects.filter(pk__in=position_ids))
        found_ids = {str(p.pk) for p in positions}
        missing = [pid for pid in position_ids if str(pid) not in found_ids]
        if missing:
            return error(f'Position(s) not found: {", ".join(str(m) for m in missing)}.', http_status=status.HTTP_404_NOT_FOUND)

        wanted_codenames = set(template.permissions.values_list('codename', flat=True))
        all_holder_ids: set[str] = set()
        with transaction.atomic():
            for position in positions:
                all_holder_ids |= set(current_holder_ids(position))
                position.position_permissions.exclude(permission__codename__in=wanted_codenames).delete()
                have = set(position.position_permissions.values_list('permission__codename', flat=True))
                for permission in Permission.objects.filter(codename__in=wanted_codenames - have):
                    PositionPermission.objects.create(position=position, permission=permission, granted_by=request.user)
                position.can_manage_team = template.can_manage_team
                position.can_manage_branch = template.can_manage_branch
                position.save(update_fields=['can_manage_team', 'can_manage_branch', 'updated_at'])

        if all_holder_ids:
            force_relogin(all_holder_ids)

        AuditLog.objects.create(
            user=request.user, action='permission_template_applied', module='settings',
            object_id=str(template.pk),
            changes={
                'template': template.name,
                'position_ids': [str(p.pk) for p in positions],
                'position_titles': [p.title for p in positions],
            },
            ip_address=get_client_ip(request),
        )
        logger.info(
            'Permission template %s applied to %d position(s) by %s',
            template.name, len(positions), request.user.employee_id,
        )
        return success(
            f'"{template.name}" applied to {len(positions)} position(s).',
            data={'positions': [_seat_payload(p) for p in positions]},
        )
