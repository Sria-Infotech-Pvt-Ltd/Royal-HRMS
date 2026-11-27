from django.utils import timezone
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView

from core.access import can_manage_team
from core.pagination import paginate, paginated_data
from core.permissions import HasCompletedOnboarding, has_perm
from core.responses import error, success
from apps.accounts.models import User
from apps.hrms.services_work_status import assignment_dict, history_queryset, is_current


def _in_branch_scope(viewer: User, employee: User) -> bool:
    from apps.accounts.views.shared import _employee_out_of_branch_scope
    return not _employee_out_of_branch_scope(viewer, employee)


def _can_view_work_status(viewer: User, employee: User) -> bool:
    """The employee themself; admins (employees.view) and managers (their direct reports), within the same branch
    scoping the employee directory already applies."""
    if viewer.id == employee.id:
        return True
    if not (has_perm(viewer, 'employees.view') or can_manage_team(viewer)):
        return False
    return _in_branch_scope(viewer, employee)


def can_manage_assignments(viewer: User, employee: User) -> bool:
    """Assigning, editing, extending and ending projects is for admins (employees.edit) within their branch scope."""
    return has_perm(viewer, 'employees.edit') and _in_branch_scope(viewer, employee)


def _work_status_response(request, employee: User, *, manager: User | None):
    today = timezone.localdate()
    history_page, paginator = paginate(history_queryset(employee.employee_id), request, default_page_size=20)
    current = [a for a in history_queryset(employee.employee_id) if is_current(a, today)]
    return success('Work status retrieved.', {
        'employee_id':        employee.employee_id,
        'employee_name':      employee.full_name,
        'employee_is_active': employee.is_active,
        'can_manage':         bool(manager) and employee.is_active and can_manage_assignments(manager, employee),
        'current':            [assignment_dict(a, today) for a in current],
        'history':            paginated_data(paginator, history_page, [assignment_dict(a, today) for a in history_page]),
    })


class MyWorkStatusView(APIView):
    """GET /api/work-status/me/ — the signed-in employee's own current projects and history."""
    permission_classes = [IsAuthenticated, HasCompletedOnboarding]

    def get(self, request):
        if not request.user.employee_id:
            return error('Your account has no employee ID.', http_status=404)
        # Your own page is read-only. When an admin opens an employee's workspace ("view as"), request.user is the
        # employee and `viewed_by` is the admin: the admin may manage that employee's projects from there.
        viewer = getattr(request.user, 'viewed_by', None)
        return _work_status_response(request, request.user, manager=viewer)


class EmployeeWorkStatusView(APIView):
    """GET /api/work-status/<employee_id>/ — an employee's Work Status for an admin or their manager."""
    permission_classes = [IsAuthenticated]

    def get(self, request, employee_id):
        employee = User.objects.filter(employee_id=employee_id).first()
        # Same answer for "doesn't exist" and "not yours to see", so employee IDs can't be probed.
        if employee is None or not _can_view_work_status(request.user, employee):
            return error('No employee found with that employee_id.', http_status=404)
        return _work_status_response(request, employee, manager=request.user)
