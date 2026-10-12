"""
Employee-wise leave credit management (Phase 1) — Employee Profile → Leave tab.

  GET  /api/leave/credits/<employee_id>/?year=&leave_type=      yearly + monthly summary and history
  POST /api/leave/credits/<employee_id>/adjust/                  signed adjustment
  POST /api/leave/credits/<employee_id>/transactions/<id>/reverse/  compensating reversal

Access: leave.approve plus _can_manage_leave_credits (no self, managers →
direct reports only, branch-restricted users → own branch).
"""
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView

from core.permissions import has_perm as _has_perm
from core.responses import error, get_client_ip, success

from ..models import LEAVE_LWP, LeavePolicy
from ..services_leave_credit import (
    LeaveCreditConflict, LeaveCreditError,
    apply_adjustment, current_calendar_year, leave_type_label, monthly_summary,
    reverse_transaction, serialize_transaction, transaction_history, yearly_summary,
)
from .leave import _can_manage_leave_credits


def _resolve_employee(request, employee_id: str):
    if not _has_perm(request.user, 'leave.approve'):
        return None, error('Permission denied.', http_status=status.HTTP_403_FORBIDDEN)
    from apps.accounts.models import User
    employee = User.objects.filter(employee_id=employee_id).exclude(employee_id='').first()
    if employee is None or not _can_manage_leave_credits(request.user, employee):
        return None, error('Employee not found.', http_status=status.HTTP_404_NOT_FOUND)
    return employee, None


def _credit_error(exc: LeaveCreditError):
    code = status.HTTP_409_CONFLICT if isinstance(exc, LeaveCreditConflict) else status.HTTP_400_BAD_REQUEST
    return error(str(exc), http_status=code)


class LeaveCreditOverviewView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, employee_id: str):
        employee, err = _resolve_employee(request, employee_id)
        if err:
            return err
        try:
            year = int(request.query_params.get('year') or current_calendar_year())
        except (TypeError, ValueError):
            return error('year must be a valid integer.')

        summaries = yearly_summary(employee, year)
        leave_type = (request.query_params.get('leave_type') or '').strip()
        if not leave_type and summaries:
            leave_type = summaries[0]['leave_type']

        assignable = [
            {'value': p.leave_type, 'label': leave_type_label(p.leave_type, p)}
            for p in LeavePolicy.objects.filter(is_active=True).exclude(leave_type=LEAVE_LWP).order_by('leave_type')
        ]
        return success('Leave credits retrieved.', {
            'employee':               {'employee_id': employee.employee_id, 'full_name': employee.full_name},
            'year':                   year,
            'current_year':           current_calendar_year(),
            'summaries':              summaries,
            'leave_type':             leave_type or None,
            'monthly':                monthly_summary(employee, leave_type, year) if leave_type else None,
            'transactions':           transaction_history(employee, year, leave_type or None),
            'assignable_leave_types': assignable,
        })


class LeaveCreditAdjustView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, employee_id: str):
        employee, err = _resolve_employee(request, employee_id)
        if err:
            return err
        data = request.data
        try:
            txn, created = apply_adjustment(
                employee=employee, leave_type=data.get('leave_type'), year=data.get('year'),
                amount=data.get('amount'), reason=data.get('reason'), actor=request.user,
                idempotency_key=data.get('idempotency_key'), ip_address=get_client_ip(request),
            )
        except LeaveCreditError as exc:
            return _credit_error(exc)
        return success(
            'Leave credits adjusted.' if created else 'This adjustment was already applied.',
            {'transaction': serialize_transaction(txn), 'duplicate': not created},
            http_status=status.HTTP_201_CREATED if created else status.HTTP_200_OK,
        )


class LeaveCreditReverseView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, employee_id: str, txn_id):
        employee, err = _resolve_employee(request, employee_id)
        if err:
            return err
        try:
            txn, created = reverse_transaction(
                employee=employee, txn_id=txn_id, reason=request.data.get('reason'),
                actor=request.user, idempotency_key=request.data.get('idempotency_key'),
                ip_address=get_client_ip(request),
            )
        except LeaveCreditError as exc:
            return _credit_error(exc)
        return success(
            'Adjustment reversed.' if created else 'This reversal was already applied.',
            {'transaction': serialize_transaction(txn), 'duplicate': not created},
            http_status=status.HTTP_201_CREATED if created else status.HTTP_200_OK,
        )
