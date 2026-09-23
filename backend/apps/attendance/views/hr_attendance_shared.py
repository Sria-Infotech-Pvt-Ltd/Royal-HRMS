"""
HR Attendance Management views.

All business logic lives in services_hr, services_hr_audit, services_hr_ops.
Views: validate input → call service → return response.
"""
from __future__ import annotations

import datetime
import logging

from django.http import HttpResponse
from rest_framework.parsers import MultiPartParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView

from core.responses import error, first_error, success

from apps.attendance.serializers_hr import (
    AttendanceListFilterSerializer,
    CorrectionListFilterSerializer,
    CorrectionReviewSerializer,
    DateFilterSerializer,
    HRAttendanceEditSerializer,
    HRAttendanceManualCreateSerializer,
    OvertimeWriteSerializer,
    WeeklyOffAssignmentFilterSerializer,
    WeeklyOffAssignmentWriteSerializer,
    WeeklyOffBulkAssignmentWriteSerializer,
)
from apps.attendance.services_hr import (
    assign_weekly_off,
    build_weekly_off_assignment_queryset,
    bulk_assign_weekly_off,
    get_attendance_detail,
    get_attendance_list,
    get_dashboard_stats,
    get_weekly_off_assignment_history,
    serialize_weekly_off_assignment_row,
)
from apps.attendance.services_hr_audit import (
    get_invalid_punches,
    get_unpunches,
)
from apps.attendance.services_hr_ops import (
    create_overtime,
    export_attendance_csv,
    import_attendance_csv,
    list_overtime,
)
from core.pagination import paginate, paginated_data
from core.permissions import has_perm as _has_perm

logger = logging.getLogger(__name__)


def _is_unrestricted(user) -> bool:
    return _has_perm(user, 'settings.edit')


def _branch_scope(user, requested: str) -> str:
    """
    Resolve the effective branch filter for the current user.

    Unrestricted users: honour whatever branch was requested (empty = all).
    Restricted users (hr_admin etc.): always use their own branch, ignoring
    the query parameter — they cannot see outside their branch.

    Managers should be scoped by _manager_scope_employee_ids instead (their
    own direct reports, not their whole branch) — callers must check that
    first and only fall back to this branch value when it returns None.
    """
    if _is_unrestricted(user):
        return requested
    return getattr(user, 'branch', '') or ''


def _manager_scope_employee_ids(user) -> list[str] | None:
    """
    Returns the employee IDs a manager is restricted to (their own direct
    reports) — or None if this user isn't manager-scoped, meaning the caller
    should fall back to _branch_scope instead (hr_admin/hr/system_admin).

    A branch commonly has multiple managers, each responsible for a
    different team — scoping a manager by branch (like HR is) would show
    them every other manager's team too, not just their own.
    """
    try:
        if user.role and getattr(user.role, 'can_manage_team', False):
            return list(
                user.direct_reports.filter(is_active=True).values_list('id', flat=True)
            )
    except Exception:
        pass
    return None


def _manager_can_access_employee(user, employee) -> bool:
    """
    Single-record gate for manager-scoped users: True when this user is not
    manager-scoped (HR/system_admin, no restriction) or when `employee` is
    one of their own direct reports. Used by views that act on one specific
    employee/record rather than a filtered list, where a queryset filter
    can't apply.
    """
    employee_ids = _manager_scope_employee_ids(user)
    if employee_ids is None:
        return True
    return str(employee.pk) in {str(i) for i in employee_ids}


def _get_policy_or_error(policy_id):
    from apps.attendance.models import WeeklyDayPolicy
    try:
        return WeeklyDayPolicy.objects.get(pk=policy_id, is_active=True), None
    except (WeeklyDayPolicy.DoesNotExist, ValueError):
        return None, error('Weekly off pattern not found.', http_status=404)


__all__ = [
    '_is_unrestricted',
    '_branch_scope',
    '_manager_scope_employee_ids',
    '_manager_can_access_employee',
    '_get_policy_or_error',
]
