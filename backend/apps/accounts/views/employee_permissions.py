"""Access for ONE employee: what they already get, and the extra permissions granted to them personally.

GET  /employees/<id>/permissions/  -> baseline, the seat they hold, and their extra permissions
PUT  /employees/<id>/permissions/  -> replace their extra permissions (settings.edit only; audit-logged)

Extra permissions are additive: they never take away anything the baseline or the seat gives.
"""
import logging

from django.db import transaction
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView

from apps.accounts.models import AuditLog, EmployeePermission, Permission, User
from apps.accounts.services_sessions import force_relogin
from core.access import baseline_codenames, current_seat
from core.permissions import has_perm as _has_perm
from core.responses import error, get_client_ip, success

logger = logging.getLogger(__name__)


def _access_payload(employee: User) -> dict:
    seat = current_seat(employee)
    return {
        'employee': str(employee.pk),
        'employee_id': employee.employee_id,
        'full_name': employee.full_name,
        'baseline': sorted(baseline_codenames()),
        'seat': {
            'title': seat.title,
            'codenames': sorted(seat.position_permissions.values_list('permission__codename', flat=True)),
        } if seat else None,
        'extra': sorted(employee.extra_permissions.values_list('permission__codename', flat=True)),
    }


class EmployeePermissionsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        if not _has_perm(request.user, 'settings.view'):
            return error('You do not have permission to view access settings.', http_status=status.HTTP_403_FORBIDDEN)
        employee = User.objects.filter(pk=pk).first()
        if not employee:
            return error('Employee not found.', http_status=status.HTTP_404_NOT_FOUND)
        return success('Employee access retrieved.', data=_access_payload(employee))

    def put(self, request, pk):
        if not _has_perm(request.user, 'settings.edit'):
            return error('Only a full-access user can change what an employee is allowed to do.', http_status=status.HTTP_403_FORBIDDEN)
        employee = User.objects.filter(pk=pk).first()
        if not employee:
            return error('Employee not found.', http_status=status.HTTP_404_NOT_FOUND)

        codenames = request.data.get('codenames')
        if not isinstance(codenames, list) or not all(isinstance(item, str) for item in codenames):
            return error('codenames must be a list of permission codenames.', http_status=status.HTTP_400_BAD_REQUEST)
        wanted = set(codenames)
        known = set(Permission.objects.filter(codename__in=wanted).values_list('codename', flat=True))
        if wanted - known:
            return error(f'Unknown permission(s): {", ".join(sorted(wanted - known))}.', http_status=status.HTTP_400_BAD_REQUEST)
        # Full access is a deliberate seat or superuser decision, not a per-person tick box.
        if 'settings.edit' in wanted:
            return error('settings.edit cannot be granted to one employee. Give it through a position.', http_status=status.HTTP_400_BAD_REQUEST)

        before = _access_payload(employee)['extra']
        with transaction.atomic():
            employee.extra_permissions.exclude(permission__codename__in=wanted).delete()
            for permission in Permission.objects.filter(codename__in=wanted - set(before)):
                EmployeePermission.objects.create(employee=employee, permission=permission, granted_by=request.user)
        payload = _access_payload(employee)
        if payload['extra'] != before:
            force_relogin([employee.pk])
        AuditLog.objects.create(
            user=request.user, action='employee_permissions_update', module='settings',
            object_id=str(employee.pk), changes={'before': before, 'after': payload['extra']},
            ip_address=get_client_ip(request),
        )
        logger.info('Extra permissions for employee %s updated by %s', employee.employee_id, request.user.employee_id)
        return success('Employee access updated.', data=payload)
