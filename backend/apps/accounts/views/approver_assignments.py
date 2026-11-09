"""
Approver assignments (reporting manager, L1 approver, L2 HR approver).

  - ApproverOptionsView            people a screen may offer for one of the three roles (the same rules a save enforces);
  - EmployeeApproverAssignmentsView  an HR user viewing / changing one employee's assignments;
  - MyApprovalsView                the signed-in employee's own chain, read-only.

The rules live in services_approver_assignment.py and services_approval_chain.py; this module only checks who is asking.
"""
from __future__ import annotations

from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView

from apps.accounts.models import ApprovalWorkflowRule
from apps.accounts.services_approval_chain import describe_chain
from apps.accounts.services_approver_assignment import (
    KINDS, LEAVE, AssignmentError, approver_options, assign_approvers, current_l1_override, user_ref,
)
from apps.accounts.services_reporting_line import resolve_manager_with_source
from apps.accounts.views.shared import _get_employee
from core.access import employee_in_scope
from core.cache_service import ApprovalWorkflowCacheService
from core.pagination import paginate, paginated_data
from core.permissions import has_perm as _has_perm
from core.responses import error, get_client_ip, success

_DENIED = 'You do not have permission to perform this action.'
_WORKFLOWS = [choice[0] for choice in ApprovalWorkflowRule.WORKFLOW_CHOICES]


def _employee_for(actor, employee_id: str):
    employee = _get_employee(employee_id)
    return employee if employee is not None and employee_in_scope(actor, employee) else None


def _rule_payload() -> dict:
    """What an empty L1 / L2 choice means: the global approval rule for leave. A screen uses it to say so; it never assumes
    L1 is the reporting manager unless the rule says that."""
    rule = ApprovalWorkflowCacheService.get_rule(LEAVE)
    return {
        'l1': rule.get_l1_approver_kind_display() if rule else '', 'l2': rule.get_l2_approver_kind_display() if rule else '',
        'l1_kind': rule.l1_approver_kind if rule else '', 'l2_kind': rule.l2_approver_kind if rule else '',
    }


def _assignments_payload(actor, employee) -> dict:
    manager = resolve_manager_with_source(employee)
    chain = describe_chain(employee, LEAVE, detail=True)
    stages = {item['stage']: item['user'] for item in chain['stages']}
    return {
        'employee': {'id': str(employee.pk), 'employee_id': employee.employee_id, 'full_name': employee.full_name},
        'can_edit': _has_perm(actor, 'employees.edit') and actor.pk != employee.pk,
        'reporting_manager': {
            'assigned': user_ref(employee.reporting_manager) if not employee.reporting_manager_from_org_chart else None,
            'effective': {**user_ref(manager.user), 'source': manager.source} if manager.user else None,
        },
        'l1_approver': {'assigned': user_ref(current_l1_override(employee)), 'effective': stages.get('l1')},
        'l2_hr_approver': {'assigned': user_ref(employee.hr), 'effective': stages.get('l2')},
        'rule': _rule_payload(),
        'chain': chain,
    }


class ApproverOptionsView(APIView):
    """GET /employees/approver-options/?kind=reporting_manager|l1|l2[&employee_id=][&q=]: who may be picked."""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        if not (_has_perm(request.user, 'employees.edit') or _has_perm(request.user, 'employees.create')):
            return error(_DENIED, http_status=status.HTTP_403_FORBIDDEN)
        kind = request.query_params.get('kind', '')
        if kind not in KINDS:
            return error(f'kind must be one of: {", ".join(KINDS)}.')
        employee = None
        if request.query_params.get('employee_id'):
            employee = _employee_for(request.user, request.query_params['employee_id'])
            if employee is None:
                return error('Employee not found.', http_status=status.HTTP_404_NOT_FOUND)
        people = approver_options(request.user, kind, employee, request.query_params.get('q', ''))
        page_obj, paginator = paginate(people, request, default_page_size=20)
        data = paginated_data(paginator, page_obj, list(page_obj.object_list))
        return success('Approver options retrieved.', data={**data, 'rule': _rule_payload()})


class EmployeeApproverAssignmentsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, employee_id: str):
        if not _has_perm(request.user, 'employees.view'):
            return error(_DENIED, http_status=status.HTTP_403_FORBIDDEN)
        employee = _employee_for(request.user, employee_id)
        if employee is None:
            return error('Employee not found.', http_status=status.HTTP_404_NOT_FOUND)
        return success('Approver assignments retrieved.', data=_assignments_payload(request.user, employee))

    def put(self, request, employee_id: str):
        if not _has_perm(request.user, 'employees.edit'):
            return error(_DENIED, http_status=status.HTTP_403_FORBIDDEN)
        employee = _employee_for(request.user, employee_id)
        if employee is None:
            return error('Employee not found.', http_status=status.HTTP_404_NOT_FOUND)
        if employee.pk == request.user.pk:
            return error('You cannot change your own approvers.', http_status=status.HTTP_403_FORBIDDEN)
        try:
            changes = assign_approvers(request.user, employee, request.data, ip_address=get_client_ip(request))
        except AssignmentError as exc:
            return error(exc.message, data={exc.field: exc.message})
        employee.refresh_from_db()
        return success('Approver assignments saved.' if changes else 'No changes to save.',
                       data={**_assignments_payload(request.user, employee), 'changes': changes})

    patch = put


class MyApprovalsView(APIView):
    """The signed-in employee's own reporting manager and approvers. Read-only, and only ever about the caller."""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        workflow = request.query_params.get('workflow', LEAVE)
        if workflow not in _WORKFLOWS:
            return error(f'workflow must be one of: {", ".join(_WORKFLOWS)}.')
        return success('Your approvers retrieved.', data=describe_chain(request.user, workflow, detail=False))
