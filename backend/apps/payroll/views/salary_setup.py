"""Salary Setup: one endpoint that returns employees TOGETHER with their salary record (paginated, searchable), and a
summary for the KPI cards. Both read the same readiness definition (services_payroll_readiness) as the dashboards, so the
numbers on every screen agree.

GET /api/payroll/salary-setup/           ?search= &status=all|configured|missing|ready|blocked &page= &page_size=
GET /api/payroll/salary-setup/summary/   counts for the whole scope, not the current page
"""
from __future__ import annotations

from django.db.models import Q
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView

from core.access import can_manage_team
from core.pagination import paginate, paginated_data
from core.permissions import has_perm as _has_perm
from core.responses import error, success
from apps.payroll.models import EmployeeSalaryConfig
from apps.payroll.services_payroll_readiness import (
    PAYROLL_READY_REQUIREMENTS, payroll_employees, payroll_readiness,
)
from apps.payroll.views.shared import _is_admin

STATUS_FILTERS = ('all', 'configured', 'missing', 'ready', 'blocked')


def scoped_payroll_employees(user):
    """The employees `user` may see in Salary Setup, or (None, error response). Same scoping as the employee list: an
    admin sees everyone, a manager their direct reports, anyone else their own branch."""
    employees = payroll_employees()
    if _is_admin(user):
        return employees, None
    if can_manage_team(user):
        return employees.filter(reporting_manager=user), None
    if user.branch:
        return employees.filter(branch=user.branch), None
    return None, error('Your account is not assigned to a branch. Contact an administrator.', http_status=400)


def _salary_payload(config) -> dict | None:
    if config is None:
        return None
    return {
        'id': str(config.pk),
        'annual_ctc': str(config.annual_ctc),
        'monthly_ctc': str(round(config.annual_ctc / 12, 2)),
        'effective_from': config.effective_from.isoformat(),
        'salary_structure': str(config.salary_structure_id) if config.salary_structure_id else None,
        'structure_name': config.salary_structure.name if config.salary_structure_id else None,
        'reason_note': config.reason_note,
    }


class SalarySetupSummaryView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        if not _has_perm(request.user, 'payroll.view'):
            return error('Only HR admin can view salary configurations.', http_status=403)
        employees, failure = scoped_payroll_employees(request.user)
        if failure:
            return failure
        data = payroll_readiness(employees).summary()
        data['requirements'] = list(PAYROLL_READY_REQUIREMENTS)
        return success('Salary setup summary retrieved.', data)


class SalarySetupListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        if not _has_perm(request.user, 'payroll.view'):
            return error('Only HR admin can view salary configurations.', http_status=403)
        employees, failure = scoped_payroll_employees(request.user)
        if failure:
            return failure

        status_filter = request.query_params.get('status', 'all')
        if status_filter not in STATUS_FILTERS:
            return error(f'status must be one of: {", ".join(STATUS_FILTERS)}.', http_status=400)

        snapshot = payroll_readiness(employees)
        rows = employees
        if status_filter == 'configured':
            rows = rows.filter(pk__in=snapshot.configured_ids)
        elif status_filter == 'missing':
            rows = rows.filter(pk__in=snapshot.missing_ids)
        elif status_filter == 'ready':
            rows = rows.filter(pk__in=snapshot.ready_ids)
        elif status_filter == 'blocked':
            rows = rows.exclude(pk__in=snapshot.ready_ids)

        search = request.query_params.get('search', '').strip()
        if search:
            rows = rows.filter(
                Q(full_name__icontains=search) | Q(employee_id__icontains=search) | Q(email__icontains=search)
                | Q(department__icontains=search) | Q(branch__icontains=search)
            )

        page_obj, paginator = paginate(rows.order_by('full_name'), request, strict_pages=True)
        page_employees = list(page_obj.object_list)
        configs = {}
        for config in (
            EmployeeSalaryConfig.objects.filter(employee__in=page_employees, is_active=True)
            .select_related('salary_structure').order_by('effective_from', 'created_at')
        ):
            configs[config.employee_id] = config  # the latest active record wins

        results = [
            {
                'uuid': str(employee.pk),
                'employee_id': employee.employee_id,
                'full_name': employee.full_name,
                'department': employee.department,
                'branch': employee.branch,
                'salary': _salary_payload(configs.get(employee.pk)),
                'state': (
                    'configured' if employee.pk in snapshot.current_ids
                    else 'scheduled' if employee.pk in snapshot.scheduled_ids else 'missing'
                ),
                'payroll_ready': employee.pk in snapshot.ready_ids,
                'blockers': snapshot.blockers_for(employee.pk),
            }
            for employee in page_employees
        ]
        return success('Salary setup retrieved.', paginated_data(paginator, page_obj, results))
