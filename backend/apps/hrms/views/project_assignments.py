"""
Admin actions on an employee's project assignments, from the Work Status panel on the employee record:

POST  /api/work-status/<employee_id>/assignments/                      assign a project
PATCH /api/work-status/<employee_id>/assignments/<assignment_id>/      edit an active assignment
POST  /api/work-status/<employee_id>/assignments/<assignment_id>/extend/   move the end date later
POST  /api/work-status/<employee_id>/assignments/<assignment_id>/end/      finish it early

Only admins holding employees.edit, within their branch scope. Every action is audit-logged.
"""
import logging

from django.utils import timezone
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView

from core.responses import error, first_error, get_client_ip, success
from apps.accounts.models import AuditLog, User
from apps.hrms.models import ProjectAssignment
from apps.hrms.serializers_project_assignment import (
    AssignProjectSerializer,
    EditAssignmentSerializer,
    EndAssignmentSerializer,
    ExtendAssignmentSerializer,
)
from apps.hrms.services_project_assignments import (
    AssignmentError,
    assign_project,
    edit_assignment,
    end_assignment,
    extend_assignment,
)
from apps.hrms.services_project_notifications import notify_assigned
from apps.hrms.services_work_status import assignment_dict, history_queryset
from apps.hrms.views.work_status import can_manage_assignments

logger = logging.getLogger(__name__)

NOT_FOUND = 'No employee found with that employee_id.'


def _employee_for(request, employee_id: str) -> User | None:
    """The employee, or None when they don't exist or the viewer can't manage them (same answer, so IDs can't be probed)."""
    employee = User.objects.filter(employee_id=employee_id).first()
    if employee is None or not can_manage_assignments(request.user, employee):
        return None
    return employee


def _assignment_for(employee: User, assignment_id: int) -> ProjectAssignment | None:
    return ProjectAssignment.objects.filter(employee_code=employee.employee_id, assignment_id=assignment_id).first()


def _audit(request, action: str, employee: User, assignment: ProjectAssignment) -> None:
    AuditLog.objects.create(
        user=request.user, action=action, module='work_status', object_id=str(assignment.pk),
        changes={'employee_id': employee.employee_id, 'project_name': assignment.project_name,
                 'start_date': assignment.assignment_start_date.isoformat(),
                 'end_date': assignment.assignment_end_date.isoformat()},
        ip_address=get_client_ip(request),
    )


def _fresh(assignment: ProjectAssignment) -> dict:
    """The assignment as the Work Status panel shows it, with its change log."""
    reloaded = history_queryset(assignment.employee_code).get(pk=assignment.pk)
    return assignment_dict(reloaded, timezone.localdate())


class AssignProjectView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, employee_id):
        employee = _employee_for(request, employee_id)
        if employee is None:
            return error(NOT_FOUND, http_status=404)
        if not employee.is_active:
            return error('Projects cannot be assigned to an employee who has left.')
        serializer = AssignProjectSerializer(data=request.data)
        if not serializer.is_valid():
            return error(first_error(serializer.errors))
        try:
            assignment = assign_project(employee, serializer.validated_data, request.user)
        except AssignmentError as exc:
            return error(str(exc))
        notify_assigned(assignment)
        _audit(request, 'project_assigned', employee, assignment)
        return success('Project assigned.', _fresh(assignment), http_status=201)


class _AssignmentActionView(APIView):
    """Shared lookup + validation for edit / extend / end."""
    permission_classes = [IsAuthenticated]
    serializer_class = None
    audit_action = ''
    success_message = ''

    def apply(self, assignment, data, actor):
        raise NotImplementedError

    def handle(self, request, employee_id, assignment_id):
        employee = _employee_for(request, employee_id)
        if employee is None:
            return error(NOT_FOUND, http_status=404)
        assignment = _assignment_for(employee, assignment_id)
        if assignment is None:
            return error('No such project assignment for this employee.', http_status=404)
        serializer = self.serializer_class(data=request.data, context={'assignment': assignment})
        if not serializer.is_valid():
            return error(first_error(serializer.errors))
        try:
            assignment = self.apply(assignment, serializer.validated_data, request.user)
        except AssignmentError as exc:
            return error(str(exc))
        _audit(request, self.audit_action, employee, assignment)
        return success(self.success_message, _fresh(assignment))


class EditAssignmentView(_AssignmentActionView):
    serializer_class = EditAssignmentSerializer
    audit_action = 'project_assignment_edited'
    success_message = 'Project assignment updated.'

    def apply(self, assignment, data, actor):
        return edit_assignment(assignment, data, actor)

    def patch(self, request, employee_id, assignment_id):
        return self.handle(request, employee_id, assignment_id)


class ExtendAssignmentView(_AssignmentActionView):
    serializer_class = ExtendAssignmentSerializer
    audit_action = 'project_assignment_extended'
    success_message = 'Project extended.'

    def apply(self, assignment, data, actor):
        return extend_assignment(assignment, data['end_date'], data.get('reason', ''), actor)

    def post(self, request, employee_id, assignment_id):
        return self.handle(request, employee_id, assignment_id)


class EndAssignmentView(_AssignmentActionView):
    serializer_class = EndAssignmentSerializer
    audit_action = 'project_assignment_ended'
    success_message = 'Project ended.'

    def apply(self, assignment, data, actor):
        return end_assignment(assignment, data.get('end_date'), data.get('reason', ''), actor)

    def post(self, request, employee_id, assignment_id):
        return self.handle(request, employee_id, assignment_id)
