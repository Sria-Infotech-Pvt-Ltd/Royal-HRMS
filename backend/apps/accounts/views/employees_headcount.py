"""GET /employees/headcount/ — the one headcount summary (see apps.accounts.services_headcount for the bucket definitions)."""
from __future__ import annotations

from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView

from apps.accounts.models import User
from apps.accounts.services_headcount import get_headcount
from core.access import can_manage_team
from core.permissions import has_perm as _has_perm
from core.responses import error, success


class EmployeeHeadcountView(APIView):
    """Query params: `branch` (name, optional), `as_of` (YYYY-MM-DD, optional). Scoped like the Employees directory."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        if not _has_perm(request.user, 'employees.view'):
            return error('You do not have permission to perform this action.', http_status=status.HTTP_403_FORBIDDEN)

        people = User.objects.exclude(employee_id='')
        if can_manage_team(request.user):
            people = people.filter(reporting_manager=request.user)
        elif not _has_perm(request.user, 'settings.edit') and request.user.branch:
            people = people.filter(branch=request.user.branch)

        as_of = None
        as_of_raw = request.query_params.get('as_of', '').strip()
        if as_of_raw:
            from datetime import date
            try:
                as_of = date.fromisoformat(as_of_raw)
            except ValueError:
                return error('as_of must be in YYYY-MM-DD format.', data={'as_of': 'as_of must be in YYYY-MM-DD format.'})

        branch = request.query_params.get('branch', '').strip()
        return success('Headcount retrieved.', data=get_headcount(
            branch=None if branch in ('', 'all') else branch, as_of=as_of, base_queryset=people,
        ))
