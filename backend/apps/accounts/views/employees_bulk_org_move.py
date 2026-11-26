"""POST /employees/bulk-move-org-unit/ — HR moves several employees to seats in another org unit in one go.

An employee's org unit is not stored on them: it follows the position they hold. Moving someone to another unit therefore means giving
them a vacant position in that unit. `assign_position` ends their old placement, so the old seat shows as vacant from the effective date.
Each move is checked and saved on its own: one that cannot be done is skipped with a reason and the rest still go through.
"""
from __future__ import annotations

from datetime import date

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView

from apps.accounts.models import AuditLog, Position
from apps.accounts.services_access_guards import assignment_refusal
from apps.accounts.services_placement import assign_position, current_placement
from apps.accounts.views.shared import _employee_out_of_branch_scope, _get_employee
from core.permissions import has_perm as _has_perm
from core.responses import error, get_client_ip, success

MAX_BULK = 200
MAX_REASON_LENGTH = 500


def _parse_date(raw) -> date | None:
    try:
        return date.fromisoformat(str(raw)) if raw else timezone.localdate()
    except ValueError:
        return None


class EmployeeBulkMoveOrgUnitView(APIView):
    """Body: {"moves": [{"employee_id": "EMP001", "position_id": "<uuid>"}, ...], "effective_date": "YYYY-MM-DD", "reason": "..."}."""

    permission_classes = [IsAuthenticated]

    def post(self, request):
        if not _has_perm(request.user, 'employees.edit'):
            return error('You do not have permission to perform this action.', http_status=status.HTTP_403_FORBIDDEN)

        moves = request.data.get('moves') or []
        if not isinstance(moves, list) or not moves:
            return error('Select at least one employee.', data={'moves': 'Select at least one employee.'})
        if len(moves) > MAX_BULK:
            return error(f'Move at most {MAX_BULK} employees at a time.', data={'moves': f'At most {MAX_BULK}.'})
        effective_date = _parse_date(request.data.get('effective_date'))
        if effective_date is None:
            return error('Enter the effective date as YYYY-MM-DD.', data={'effective_date': 'Invalid date.'})
        if effective_date < timezone.localdate():
            return error('The effective date cannot be in the past.', data={'effective_date': 'Choose today or a later date.'})
        reason = str(request.data.get('reason') or '').strip()[:MAX_REASON_LENGTH]

        moved, skipped, seats_used = [], [], set()
        for move in moves:
            outcome = self._move_one(request, move, effective_date, reason, seats_used)
            (moved if outcome['ok'] else skipped).append(outcome['row'])

        message = f'{len(moved)} employee(s) moved.' + (f' {len(skipped)} skipped.' if skipped else '')
        return success(message, data={'moved': moved, 'skipped': skipped})

    def _move_one(self, request, move, effective_date, reason, seats_used) -> dict:
        reference = str(move.get('employee_id') or '') if isinstance(move, dict) else ''

        def skip(why: str) -> dict:
            return {'ok': False, 'row': {'employee_id': reference, 'reason': why}}

        employee = _get_employee(reference) if reference else None
        if employee is None or _employee_out_of_branch_scope(request.user, employee):
            return skip('Employee not found.')
        position_id = str(move.get('position_id') or '')
        try:
            position = Position.objects.select_related('org_unit').get(pk=position_id, is_active=True)
        except (Position.DoesNotExist, ValueError, ValidationError):
            return skip('Choose an active position.')
        if position.pk in seats_used:
            return skip(f'"{position.title}" is already taken by another employee in this move.')
        holder = current_placement(position, effective_date)
        if holder is not None and holder.employee_id == employee.pk:
            return skip('Already in this position.')
        if holder is not None:
            return skip(f'"{position.title}" is not vacant.')
        refusal = assignment_refusal(request.user, employee, position)
        if refusal:
            return skip(refusal.message)

        old_unit, old_title = _current_seat(employee)
        try:
            with transaction.atomic():
                assign_position(employee, position, effective_from=effective_date, created_by=request.user, note=reason)
                AuditLog.objects.create(
                    user=request.user, action='employee_updated', module='employees', object_id=str(employee.id),
                    changes={
                        'employee_id': employee.employee_id, 'full_name': employee.full_name,
                        'org_unit': {'from': old_unit, 'to': position.org_unit.name},
                        'position': {'from': old_title, 'to': position.title},
                        'effective_date': effective_date.isoformat(), 'reason': reason, 'via': 'bulk_move_org_unit',
                    },
                    branch=employee.branch, ip_address=get_client_ip(request),
                )
        except ValidationError as exc:
            return skip('; '.join(exc.messages))
        seats_used.add(position.pk)
        return {'ok': True, 'row': {'employee_id': employee.employee_id, 'org_unit': position.org_unit.name, 'position': position.title}}


def _current_seat(employee) -> tuple[str, str]:
    from apps.accounts.models import Placement

    placement = (
        Placement.objects.filter(employee=employee, effective_to__isnull=True)
        .select_related('position', 'position__org_unit').first()
    )
    return (placement.position.org_unit.name, placement.position.title) if placement else ('', '')
