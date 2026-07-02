"""
EmployeeBranchAccess management views.

HR can grant specific employees (HR staff, IT Support, Management,
Regional Managers) the ability to punch in from multiple branches.
"""
from __future__ import annotations

import logging

from django.core.paginator import Paginator
from django.db import IntegrityError, transaction
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView

from core.responses import error, first_error, success

from apps.branch.models import Branch, EmployeeBranchAccess
from apps.branch.serializers import EmployeeBranchAccessSerializer

logger = logging.getLogger(__name__)

_PERM_DENIED = 'You do not have permission to perform this action.'


def _has_perm(user, codename: str) -> bool:
    if not user or not user.role:
        return False
    return user.role.role_permissions.filter(permission__codename=codename).exists()


class EmployeeBranchAccessListCreateView(APIView):
    """
    GET  /api/branch/employee-access/   — list multi-branch access records
    POST /api/branch/employee-access/   — grant a branch to an employee

    Query filters (GET):
      ?employee=<uuid>   — show access records for one employee
      ?branch=<int>      — show employees allowed at one branch
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        if not _has_perm(request.user, 'branches.view'):
            return error(_PERM_DENIED, http_status=403)

        qs = (
            EmployeeBranchAccess.objects
            .select_related('employee', 'branch')
            .order_by('employee__full_name', '-is_primary')
        )

        if employee_id := request.query_params.get('employee'):
            qs = qs.filter(employee_id=employee_id)

        if branch_id := request.query_params.get('branch'):
            try:
                qs = qs.filter(branch_id=int(branch_id))
            except (TypeError, ValueError):
                return error('branch filter must be a valid integer ID.')

        try:
            page_num  = max(1, int(request.query_params.get('page', 1)))
            page_size = min(50, max(1, int(request.query_params.get('page_size', 20))))
        except (TypeError, ValueError):
            page_num, page_size = 1, 20

        paginator = Paginator(qs, page_size)
        page_obj  = paginator.get_page(page_num)

        return success('Access records retrieved.', data={
            'count':       paginator.count,
            'page':        page_obj.number,
            'page_size':   page_size,
            'total_pages': paginator.num_pages,
            'results':     EmployeeBranchAccessSerializer(page_obj.object_list, many=True).data,
        })

    def post(self, request):
        if not _has_perm(request.user, 'branches.edit'):
            return error(_PERM_DENIED, http_status=403)

        ser = EmployeeBranchAccessSerializer(data=request.data)
        if not ser.is_valid():
            return error(first_error(ser.errors), data=ser.errors)

        try:
            with transaction.atomic():
                record = ser.save()
        except IntegrityError:
            return error(
                'This employee already has access to that branch.',
                http_status=409,
            )

        logger.info(
            'Branch access granted: employee=%s branch=%s by %s',
            record.employee_id, record.branch_id, request.user.email,
        )
        return success(
            'Branch access granted.',
            data=EmployeeBranchAccessSerializer(record).data,
            http_status=201,
        )


class EmployeeBranchAccessDetailView(APIView):
    """
    PATCH  /api/branch/employee-access/<uuid:pk>/  — update is_primary flag
    DELETE /api/branch/employee-access/<uuid:pk>/  — revoke access
    """
    permission_classes = [IsAuthenticated]

    def _get_record(self, pk):
        try:
            return (
                EmployeeBranchAccess.objects
                .select_related('employee', 'branch')
                .get(pk=pk)
            )
        except EmployeeBranchAccess.DoesNotExist:
            return None

    def patch(self, request, pk):
        if not _has_perm(request.user, 'branches.edit'):
            return error(_PERM_DENIED, http_status=403)

        record = self._get_record(pk)
        if not record:
            return error('Access record not found.', http_status=404)

        ser = EmployeeBranchAccessSerializer(record, data=request.data, partial=True)
        if not ser.is_valid():
            return error(first_error(ser.errors), data=ser.errors)

        updated = ser.save()
        logger.info(
            'Branch access updated: id=%s is_primary=%s by %s',
            updated.pk, updated.is_primary, request.user.email,
        )
        return success('Access record updated.', data=EmployeeBranchAccessSerializer(updated).data)

    def delete(self, request, pk):
        if not _has_perm(request.user, 'branches.edit'):
            return error(_PERM_DENIED, http_status=403)

        record = self._get_record(pk)
        if not record:
            return error('Access record not found.', http_status=404)

        emp_id  = record.employee_id
        branch_id = record.branch_id
        record.delete()

        logger.info(
            'Branch access revoked: employee=%s branch=%s by %s',
            emp_id, branch_id, request.user.email,
        )
        return success('Branch access revoked.')
