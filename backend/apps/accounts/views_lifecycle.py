"""
Phase 5B Task I — read-only employment "as of a date" view and lifecycle
timeline, surfacing this phase's own new structures (EmploymentAction,
EmployeeRelationship) plus Phase 5A's Address/BankAccount. See
services_lifecycle_view.py for the honesty caveats on what "as of" can
and can't reconstruct given no full history migration has run.

Distinct from the pre-existing `EmployeeActionHistoryView`
(action-history/) which surfaces the legacy Hire/PromotionRecord trail —
this is additive, not a replacement.
"""
from __future__ import annotations

from datetime import datetime

from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView

from core.responses import error, success


class EmployeeAsOfView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, employee_id: str):
        from core.permissions import has_perm as _has_perm

        from apps.accounts.views.shared import _employee_out_of_branch_scope, _get_employee

        is_self = request.user.employee_id == employee_id
        if not is_self and not _has_perm(request.user, 'employees.view'):
            return error('You do not have permission to perform this action.', http_status=status.HTTP_403_FORBIDDEN)
        employee = _get_employee(employee_id)
        if employee is None or (not is_self and _employee_out_of_branch_scope(request.user, employee)):
            return error('Employee not found.', http_status=status.HTTP_404_NOT_FOUND)

        raw_date = request.query_params.get('date')
        as_of = None
        if raw_date:
            try:
                as_of = datetime.strptime(raw_date, '%Y-%m-%d').date()
            except ValueError:
                return error('date must be YYYY-MM-DD.', http_status=status.HTTP_400_BAD_REQUEST)

        from apps.accounts.services_lifecycle_view import get_employee_as_of
        return success('Employee as-of view retrieved.', data=get_employee_as_of(employee, as_of=as_of))


class EmployeeLifecycleTimelineView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, employee_id: str):
        from core.permissions import has_perm as _has_perm

        from apps.accounts.views.shared import _employee_out_of_branch_scope, _get_employee

        is_self = request.user.employee_id == employee_id
        if not is_self and not _has_perm(request.user, 'employees.view'):
            return error('You do not have permission to perform this action.', http_status=status.HTTP_403_FORBIDDEN)
        employee = _get_employee(employee_id)
        if employee is None or (not is_self and _employee_out_of_branch_scope(request.user, employee)):
            return error('Employee not found.', http_status=status.HTTP_404_NOT_FOUND)

        from apps.accounts.services_lifecycle_view import get_employee_timeline
        return success('Employee lifecycle timeline retrieved.', data=get_employee_timeline(employee))
