from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView

from core.pagination import paginate, paginated_data
from core.permissions import HasCompletedOnboarding
from core.responses import success
from apps.hrms.models import ProjectAssignment
from apps.hrms.services_project_sync import sync_employee_assignments_if_unknown

# "removed" rows are kept in the budgeting tool's history but mean the person is no longer on it.
HIDDEN_ASSIGNMENT_STATUSES = ('removed',)


def _assignment_dict(assignment: ProjectAssignment) -> dict:
    return {
        'assignment_id':             assignment.assignment_id,
        'project_id':                assignment.project_id,
        'project_name':              assignment.project_name,
        'project_status':            assignment.project_status,
        'project_status_display':    assignment.project_status_display,
        'project_start_date':        assignment.project_start_date.isoformat() if assignment.project_start_date else None,
        'project_end_date':          assignment.project_end_date.isoformat() if assignment.project_end_date else None,
        'assignment_start_date':     assignment.assignment_start_date.isoformat() if assignment.assignment_start_date else None,
        'assignment_end_date':       assignment.assignment_end_date.isoformat() if assignment.assignment_end_date else None,
        'assignment_status':         assignment.assignment_status,
        'assignment_status_display': assignment.assignment_status_display,
        'milestone_name':            assignment.milestone_name,
    }


class EmployeeProjectAssignmentsView(APIView):
    """GET /api/dashboard/employee/projects/ — the signed-in employee's own projects/tasks from the Project Budget &
    Tracking tool, for the dashboard's "My Projects" card. Always the requester's own rows: the employee code comes from
    request.user, never from a query param."""
    permission_classes = [IsAuthenticated, HasCompletedOnboarding]

    def get(self, request):
        employee_code = request.user.employee_id
        sync_employee_assignments_if_unknown(employee_code)

        assignments = (
            ProjectAssignment.objects
            .filter(employee_code=employee_code)
            .exclude(assignment_status__in=HIDDEN_ASSIGNMENT_STATUSES)
            if employee_code else ProjectAssignment.objects.none()
        )
        page_obj, paginator = paginate(assignments, request, default_page_size=5)
        results = [_assignment_dict(a) for a in page_obj]
        return success('Projects retrieved.', paginated_data(paginator, page_obj, results))
