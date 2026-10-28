"""POST /employees/bulk-assign-manager/ — HR picks several employees and one reporting manager; one audit entry per change."""
from __future__ import annotations

from django.db import transaction
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView

from apps.accounts.models import AuditLog, User
from core.access import can_manage_team
from core.permissions import has_perm as _has_perm
from core.responses import error, get_client_ip, success
from apps.accounts.views.shared import _employee_out_of_branch_scope, _get_employee

MAX_BULK = 200


class EmployeeBulkAssignManagerView(APIView):
    """Body: {"manager_id": "<employee code or uuid>", "employee_ids": ["EMP001", ...]}. Each employee is changed or skipped with a reason."""

    permission_classes = [IsAuthenticated]

    def post(self, request):
        if not _has_perm(request.user, 'employees.edit'):
            return error('You do not have permission to perform this action.', http_status=status.HTTP_403_FORBIDDEN)

        employee_ids = request.data.get('employee_ids') or []
        if not isinstance(employee_ids, list) or not employee_ids:
            return error('Select at least one employee.', data={'employee_ids': 'Select at least one employee.'})
        if len(employee_ids) > MAX_BULK:
            return error(f'Select at most {MAX_BULK} employees at a time.', data={'employee_ids': f'At most {MAX_BULK}.'})

        manager_ref = str(request.data.get('manager_id') or '').strip()
        manager = _get_employee(manager_ref) if manager_ref else None
        if manager is None:
            manager = User.objects.filter(pk=manager_ref).first() if manager_ref and len(manager_ref) >= 32 else None
        if manager is None or not manager.is_active:
            return error('Choose an active reporting manager.', data={'manager_id': 'Choose an active reporting manager.'})
        if not can_manage_team(manager):
            return error(f'{manager.full_name} is not set up to manage a team.', data={'manager_id': 'Not a team manager.'})

        assigned, skipped = [], []
        with transaction.atomic():
            for reference in employee_ids:
                employee = _get_employee(str(reference))
                if employee is None or _employee_out_of_branch_scope(request.user, employee):
                    skipped.append({'employee_id': str(reference), 'reason': 'Employee not found.'})
                    continue
                if employee.pk == manager.pk:
                    skipped.append({'employee_id': employee.employee_id, 'reason': 'An employee cannot be their own manager.'})
                    continue
                if can_manage_team(employee):
                    skipped.append({'employee_id': employee.employee_id, 'reason': 'Managers do not have a reporting manager.'})
                    continue
                old = employee.reporting_manager
                if old is not None and old.pk == manager.pk:
                    skipped.append({'employee_id': employee.employee_id, 'reason': 'Already reports to this manager.'})
                    continue
                employee.reporting_manager = manager
                employee.reporting_manager_from_org_chart = False
                employee.save(update_fields=['reporting_manager', 'reporting_manager_from_org_chart', 'updated_at'])
                AuditLog.objects.create(
                    user=request.user, action='employee_updated', module='employees', object_id=str(employee.id),
                    changes={
                        'employee_id': employee.employee_id, 'full_name': employee.full_name,
                        'reporting_manager': {'from': old.employee_id if old else '', 'to': manager.employee_id},
                        'via': 'bulk_assign_manager',
                    },
                    branch=employee.branch, ip_address=get_client_ip(request),
                )
                assigned.append(employee.employee_id)

        message = f'{len(assigned)} employee(s) now report to {manager.full_name}.' + (f' {len(skipped)} skipped.' if skipped else '')
        return success(message, data={'assigned': assigned, 'skipped': skipped})
