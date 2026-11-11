"""
Maximum Late Arrivals Per Month (Settings → Leave Policy) — tracking only.

GET  /api/attendance/late-arrival-limit/            the company setting (any signed-in user, read-only)
PUT  /api/attendance/late-arrival-limit/            {enabled, maximum} — same permission as editing
                                                    leave policies (settings.edit or leave.approve)
GET  /api/attendance/late-arrival-limit/employees/  ?month=YYYY-MM&include_reached=true — employees
                                                    over (or at) the limit, scoped like HR attendance
"""
from __future__ import annotations

from django.contrib.auth import get_user_model
from django.utils import timezone
from rest_framework import serializers, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView

from core.permissions import has_perm
from core.responses import error, first_error, success

from apps.attendance import services_late_limit as late_limit
from apps.attendance.models import AttendanceLateMarkRules
from apps.attendance.views.hr_attendance import _branch_scope, _manager_scope_employee_ids

User = get_user_model()


def _can_edit(user) -> bool:
    # Mirrors LeavePolicyView.put (apps.hrms.views.leave).
    return has_perm(user, 'settings.edit') or has_perm(user, 'leave.approve')


class _LimitSerializer(serializers.Serializer):
    enabled = serializers.BooleanField()
    maximum = serializers.IntegerField(min_value=1, max_value=late_limit.MAX_LIMIT,
                                       error_messages={'min_value': 'Enter a whole number of at least 1.',
                                                       'max_value': f'Enter at most {late_limit.MAX_LIMIT}.',
                                                       'invalid': 'Enter a whole number.'})


class LateArrivalLimitView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        return success('Late arrival limit retrieved.', {**late_limit.get_limit(), 'can_edit': _can_edit(request.user)})

    def put(self, request):
        if not _can_edit(request.user):
            return error('You do not have permission to change leave policy settings.', http_status=403)
        ser = _LimitSerializer(data=request.data)
        if not ser.is_valid():
            return error(first_error(ser.errors), data=ser.errors)
        rules = late_limit._rules()
        if rules is None:
            # Creating attendance settings here would also switch on the default
            # late-mark LOP rule — a pay change. Attendance Rules are saved first.
            return error('Save Settings → Attendance Rules once before changing this limit.',
                         http_status=status.HTTP_409_CONFLICT)
        AttendanceLateMarkRules.objects.filter(pk=rules.pk).update(
            late_limit_enabled=ser.validated_data['enabled'],
            max_late_arrivals_per_month=ser.validated_data['maximum'])
        from core.cache_service import AttendanceSettingsCacheService
        AttendanceSettingsCacheService.invalidate()
        return success('Late arrival limit saved.', {**late_limit.get_limit(), 'can_edit': True})


class LateArrivalLimitEmployeesView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user
        # Not attendance.view: ordinary employees hold it, and this list shows
        # colleagues' late counts. Leave Policy admins, HR (attendance.edit) or
        # a manager (direct reports only, below).
        is_manager = bool(user.role and getattr(user.role, 'can_manage_team', False))
        if not (_can_edit(user) or has_perm(user, 'attendance.edit') or is_manager):
            return error('Permission denied.', http_status=403)
        today = timezone.localdate()
        raw = (request.query_params.get('month') or f'{today:%Y-%m}').strip()
        try:
            year, month = (int(x) for x in raw.split('-'))
            late_limit.month_bounds(year, month)
        except (ValueError, TypeError):
            return error('month must be YYYY-MM.', data={'month': ['Use YYYY-MM.']})
        qs = User.objects.filter(is_active=True)
        manager_ids = _manager_scope_employee_ids(user)
        if manager_ids is not None and not _can_edit(user):
            qs = qs.filter(id__in=manager_ids)
        else:
            branch = _branch_scope(user, request.query_params.get('branch', ''))
            if branch:
                qs = qs.filter(branch=branch)
        limit = late_limit.get_limit()
        include_reached = request.query_params.get('include_reached') in ('1', 'true', 'True')
        rows = late_limit.employees_at_or_over(qs, year, month, include_reached=include_reached, limit=limit)
        return success(f'{len(rows)} employee(s).', {**limit, 'month': f'{year:04d}-{month:02d}', 'results': rows})
