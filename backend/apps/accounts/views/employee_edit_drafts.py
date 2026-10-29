from __future__ import annotations

from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView

from apps.accounts.models import AuditLog, EmployeeEditDraft
from core.permissions import has_perm as _has_perm
from core.responses import error, get_client_ip, success

from .shared import _get_employee


def _draft_dict(draft: EmployeeEditDraft) -> dict:
    return {
        'id': str(draft.id),
        'data': draft.data,
        'last_step': draft.last_step,
        'updated_at': draft.updated_at.isoformat(),
    }


class EmployeeEditDraftView(APIView):
    """
    GET    /employees/<employee_id>/edit-draft/          — check for a draft (no audit entry; the panel calls this on every open)
    POST   /employees/<employee_id>/edit-draft/           — save/update the draft's content (create vs update both audited)
    DELETE /employees/<employee_id>/edit-draft/           — discard the draft

    A draft is private to the admin who saved it — always looked up by
    (employee, created_by=request.user), never by employee alone.
    """
    permission_classes = [IsAuthenticated]

    def _employee_or_404(self, employee_id: str):
        if not _has_perm(self.request.user, 'employees.edit'):
            return None, error('You do not have permission to perform this action.', http_status=403)
        employee = _get_employee(employee_id)
        if employee is None:
            return None, error('Employee not found.', http_status=404)
        return employee, None

    def get(self, request, employee_id: str):
        employee, err = self._employee_or_404(employee_id)
        if err:
            return err
        draft = EmployeeEditDraft.objects.filter(employee=employee, created_by=request.user).first()
        return success('Draft retrieved.', data={'draft': _draft_dict(draft) if draft else None})

    def post(self, request, employee_id: str):
        employee, err = self._employee_or_404(employee_id)
        if err:
            return err
        data = request.data.get('data')
        if not isinstance(data, dict):
            return error('data must be an object.')
        last_step = request.data.get('last_step') or 0
        try:
            last_step = int(last_step)
        except (TypeError, ValueError):
            return error('last_step must be a number.')

        draft, created = EmployeeEditDraft.objects.update_or_create(
            employee=employee, created_by=request.user,
            defaults={'data': data, 'last_step': last_step},
        )
        AuditLog.objects.create(
            user=request.user,
            action='employee_edit_draft_created' if created else 'employee_edit_draft_updated',
            module='employees',
            object_id=str(employee.id),
            changes={'employee_id': employee.employee_id, 'full_name': employee.full_name},
            branch=employee.branch,
            ip_address=get_client_ip(request),
        )
        return success('Draft saved.', data={'draft': _draft_dict(draft)})

    def delete(self, request, employee_id: str):
        employee, err = self._employee_or_404(employee_id)
        if err:
            return err
        deleted, _ = EmployeeEditDraft.objects.filter(employee=employee, created_by=request.user).delete()
        if deleted:
            AuditLog.objects.create(
                user=request.user, action='employee_edit_draft_discarded', module='employees',
                object_id=str(employee.id),
                changes={'employee_id': employee.employee_id, 'full_name': employee.full_name},
                branch=employee.branch, ip_address=get_client_ip(request),
            )
        return success('Draft discarded.')


class EmployeeEditDraftResumeView(APIView):
    """POST /employees/<employee_id>/edit-draft/resume/ — explicit "Resume Draft" click; audited separately from the passive GET above."""
    permission_classes = [IsAuthenticated]

    def post(self, request, employee_id: str):
        if not _has_perm(request.user, 'employees.edit'):
            return error('You do not have permission to perform this action.', http_status=403)
        employee = _get_employee(employee_id)
        if employee is None:
            return error('Employee not found.', http_status=404)
        draft = EmployeeEditDraft.objects.filter(employee=employee, created_by=request.user).first()
        if draft is None:
            return error('No draft to resume.', http_status=404)
        AuditLog.objects.create(
            user=request.user, action='employee_edit_draft_resumed', module='employees',
            object_id=str(employee.id),
            changes={'employee_id': employee.employee_id, 'full_name': employee.full_name},
            branch=employee.branch, ip_address=get_client_ip(request),
        )
        return success('Draft resumed.', data={'draft': _draft_dict(draft)})
