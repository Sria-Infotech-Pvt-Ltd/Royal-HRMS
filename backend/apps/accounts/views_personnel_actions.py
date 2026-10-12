"""
Pending-approval ("maker-checker") personnel actions.

  POST /api/employees/<code>/action-requests/      raise  (employees.raise_action)
  GET  /api/employees/<code>/action-requests/      history of requests for one employee
  GET  /api/action-requests/?scope=inbox|mine      what I can decide / what I raised
  POST /api/action-requests/<id>/approve|reject|cancel/

Logic lives in services_personnel_actions.py; these views only translate
HTTP <-> service calls and shape the response.
"""
import logging

from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView

from core.pagination import paginate, paginated_data
from core.permissions import has_perm as _has_perm
from core.responses import error, success

from . import services_personnel_actions as svc
from .models import Position, User
from .models_personnel_action import PersonnelActionRequest as PAR
from .views.shared import _employee_out_of_branch_scope, _get_employee

logger = logging.getLogger(__name__)

_DENIED = 'You do not have permission to perform this action.'


def request_dict(req: PAR, viewer: User) -> dict:
    """One request, with the display values the UI needs (position title,
    manager name) resolved so the client never has to look anything up."""
    payload = dict(req.payload or {})
    after = {}
    if payload.get('position'):
        position = Position.objects.filter(pk=payload['position']).first()
        after['position'] = position.title if position else '—'
    if payload.get('annual_ctc'):
        after['annual_ctc'] = payload['annual_ctc']
    if payload.get('reporting_manager_id'):
        manager = User.objects.filter(pk=payload['reporting_manager_id']).first()
        after['reporting_manager'] = manager.full_name if manager else '—'
    if payload.get('work_location'):
        after['work_location'] = payload['work_location']
    if req.action_type == PAR.TYPE_CONFIRMATION:
        after['employment_status'] = 'Confirmed'

    # The employee's CURRENT pay is payroll data: show it only to someone who
    # could see it anyway (payroll.view), the employee themself, or whoever is
    # asked to decide on it. The proposed figure stays visible to the raiser,
    # who typed it.
    before = dict(req.before or {})
    can_see_current_pay = (
        _has_perm(viewer, 'payroll.view')
        or viewer.pk == req.employee_id
        or svc.can_user_decide(viewer, req)
    )
    if 'annual_ctc' in before and not can_see_current_pay:
        before['annual_ctc'] = None

    step = svc.current_step(req)
    return {
        'id':               str(req.id),
        'employee':         {'id': str(req.employee_id), 'code': req.employee.employee_id, 'name': req.employee.full_name,
                             'designation': req.employee.designation},
        'action_type':      req.action_type,
        'action_label':     req.get_action_type_display(),
        'reason':           req.reason,
        'effective_from':   req.effective_from.isoformat(),
        'before':           before,
        'after':            after,
        'raised_by_name':   req.raised_by.full_name if req.raised_by_id else '—',
        'status':           req.status,
        'status_display':   req.get_status_display(),
        'steps':            req.steps,
        'current_step':     req.current_step,
        'current_step_label': step['label'] if step else '',
        'route':            ' → '.join(s['label'] for s in req.steps),
        'decision_note':    req.decision_note,
        'apply_error':      req.apply_error,
        'created_at':       req.created_at.isoformat(),
        'applied_at':       req.applied_at.isoformat() if req.applied_at else None,
        'can_decide':       svc.can_user_decide(viewer, req),
        'can_cancel':       svc.can_user_cancel(viewer, req),
    }


class EmployeeActionRequestsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, employee_id: str):
        is_self = request.user.employee_id == employee_id
        if not is_self and not _has_perm(request.user, 'employees.view'):
            return error(_DENIED, http_status=status.HTTP_403_FORBIDDEN)
        employee = _get_employee(employee_id)
        if employee is None or (not is_self and _employee_out_of_branch_scope(request.user, employee)):
            return error('Employee not found.', http_status=status.HTTP_404_NOT_FOUND)
        qs = PAR.objects.filter(employee=employee).select_related('employee', 'raised_by')
        page_obj, paginator = paginate(qs, request)
        return success('Action requests retrieved.', paginated_data(
            paginator, page_obj, [request_dict(r, request.user) for r in page_obj.object_list],
        ))

    def post(self, request, employee_id: str):
        if not _has_perm(request.user, 'employees.raise_action'):
            return error(_DENIED, http_status=status.HTTP_403_FORBIDDEN)
        employee = _get_employee(employee_id)
        if employee is None or _employee_out_of_branch_scope(request.user, employee):
            return error('Employee not found.', http_status=status.HTTP_404_NOT_FOUND)
        try:
            req = svc.raise_request(request.user, employee, request.data)
        except svc.ActionRequestError as exc:
            return error(exc.message, http_status=exc.http_status)
        return success('Action raised and sent for approval.', request_dict(req, request.user), http_status=status.HTTP_201_CREATED)


class ActionRequestListView(APIView):
    """scope=inbox (default): requests whose CURRENT step I may decide.
       scope=mine: requests I raised, any status."""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        scope = request.query_params.get('scope', 'inbox')
        if scope == 'mine':
            qs = PAR.objects.filter(raised_by=request.user).select_related('employee', 'raised_by')
            page_obj, paginator = paginate(qs, request)
            rows = list(page_obj.object_list)
            return success('Action requests retrieved.', paginated_data(
                paginator, page_obj, [request_dict(r, request.user) for r in rows]))
        rows = svc.inbox_for(request.user)
        return success('Action requests retrieved.', {
            'count': len(rows), 'results': [request_dict(r, request.user) for r in rows],
        })


class ActionRequestDecisionView(APIView):
    permission_classes = [IsAuthenticated]
    verb = ''

    def post(self, request, pk):
        try:
            if self.verb == 'cancel':
                req = svc.cancel(pk, request.user)
            else:
                req = svc.decide(pk, request.user, self.verb, request.data.get('note', ''))
        except PAR.DoesNotExist:
            return error('Request not found.', http_status=status.HTTP_404_NOT_FOUND)
        except svc.ActionRequestError as exc:
            return error(exc.message, http_status=exc.http_status)
        req = PAR.objects.select_related('employee', 'raised_by').get(pk=req.pk)
        return success('Request updated.', request_dict(req, request.user))


class ActionRequestApproveView(ActionRequestDecisionView):
    verb = 'approve'


class ActionRequestRejectView(ActionRequestDecisionView):
    verb = 'reject'


class ActionRequestCancelView(ActionRequestDecisionView):
    verb = 'cancel'
