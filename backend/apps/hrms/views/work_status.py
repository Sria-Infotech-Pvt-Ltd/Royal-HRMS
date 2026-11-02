from datetime import timedelta

from django.conf import settings
from django.utils import timezone
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView

from core.access import can_manage_team
from core.pagination import paginate, paginated_data
from core.permissions import HasCompletedOnboarding, HasSettingsPermission, has_perm
from core.responses import error, success
from apps.accounts.models import User
from apps.hrms.models import ProjectAssignment, ProjectSyncLog
from apps.hrms.services_project_assignments import STATUS_COMPLETED, STATUS_REMOVED
from apps.hrms.services_project_sync import sync_employee_assignments_if_unknown
from apps.hrms.services_work_status import (
    MANAGED_IN,
    assignment_dict,
    find_conflicts,
    history_queryset,
    is_current,
    last_synced_at,
)


def _can_view_work_status(viewer: User, employee: User) -> bool:
    """The employee themself; HR/admin (employees.view) and managers (their direct reports), within the same branch
    scoping the employee directory already applies."""
    if viewer.id == employee.id:
        return True
    if not (has_perm(viewer, 'employees.view') or can_manage_team(viewer)):
        return False
    from apps.accounts.views.shared import _employee_out_of_branch_scope
    return not _employee_out_of_branch_scope(viewer, employee)


def _work_status_response(request, employee: User):
    today = timezone.localdate()
    history_page, paginator = paginate(history_queryset(employee.employee_id), request, default_page_size=20)
    current = [a for a in history_queryset(employee.employee_id) if is_current(a, today)]
    return success('Work status retrieved.', {
        'employee_id':        employee.employee_id,
        'employee_name':      employee.full_name,
        'employee_is_active': employee.is_active,
        'managed_in':         MANAGED_IN,
        'is_read_only':       True,
        'last_synced_at':     last_synced_at(),
        'current':            [assignment_dict(a, today) for a in current],
        'conflicts':          find_conflicts(current),
        'history':            paginated_data(paginator, history_page, [assignment_dict(a, today) for a in history_page]),
    })


class MyWorkStatusView(APIView):
    """GET /api/work-status/me/ — the signed-in employee's own current projects and history."""
    permission_classes = [IsAuthenticated, HasCompletedOnboarding]

    def get(self, request):
        if not request.user.employee_id:
            return error('Your account has no employee ID.', http_status=404)
        # Nothing stored for this employee yet (e.g. a push was missed): ask Project Budgeting once. Never raises.
        sync_employee_assignments_if_unknown(request.user.employee_id)
        return _work_status_response(request, request.user)


class EmployeeWorkStatusView(APIView):
    """GET /api/work-status/<employee_id>/ — an employee's Work Status for HR/admin or their manager."""
    permission_classes = [IsAuthenticated]

    def get(self, request, employee_id):
        employee = User.objects.filter(employee_id=employee_id).first()
        # Same answer for "doesn't exist" and "not yours to see", so employee IDs can't be probed.
        if employee is None or not _can_view_work_status(request.user, employee):
            return error('No employee found with that employee_id.', http_status=404)
        return _work_status_response(request, employee)


class ProjectSyncStatusView(APIView):
    """GET /api/project-sync/status/ — for admins: is the Project Budgeting sync healthy, what failed, and which
    employee IDs Project Budgeting sent that we can't match."""
    permission_classes = [IsAuthenticated, HasSettingsPermission]

    def get(self, request):
        day_ago = timezone.now() - timedelta(hours=24)
        logs = ProjectSyncLog.objects.all()
        page_obj, paginator = paginate(logs, request, default_page_size=20)

        known_codes = set(User.objects.exclude(employee_id='').values_list('employee_id', flat=True))
        unmatched = [
            code for code in
            ProjectAssignment.objects.values_list('employee_code', flat=True).distinct()
            if code not in known_codes
        ]
        return success('Project sync status retrieved.', {
            'is_pull_configured': bool(settings.PROJECT_BUDGET_API_BASE_URL and settings.PROJECT_BUDGET_API_KEY),
            'last_synced_at':     last_synced_at(),
            'failed_last_24h':    logs.filter(status=ProjectSyncLog.STATUS_FAILED, created_at__gte=day_ago).count(),
            'unmatched_employee_ids': sorted(unmatched),
            'open_assignments':   ProjectAssignment.objects.exclude(
                assignment_status__in=(STATUS_REMOVED, STATUS_COMPLETED)).count(),
            'logs': paginated_data(paginator, page_obj, [
                {
                    'source': log.source, 'triggered_by': log.triggered_by, 'employee_id': log.employee_code,
                    'status': log.status, 'saved': log.saved, 'changed': log.changed, 'removed': log.removed,
                    'message': log.message, 'at': log.created_at.isoformat(),
                }
                for log in page_obj
            ]),
        })
