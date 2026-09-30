import logging

from django.db import IntegrityError, transaction
from django.db.models import Q
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView

from core.pagination import paginate, paginated_data
from core.permissions import has_perm as _has_perm
from core.responses import error, first_error, get_client_ip, success

from apps.accounts.models import AuditLog, User
from apps.assets.models import Asset, AssetAssignment
from apps.assets.serializers import (
    AssetAssignmentSerializer,
    AssetSerializer,
    AssignAssetSerializer,
    ReturnAssetSerializer,
)
from apps.branch.models import Branch

logger = logging.getLogger(__name__)


# ── Branch scoping — same local-helper convention every other branch-scoped
# view module uses (see apps/payroll/views/cycles.py:537-546); not imported
# from payroll, matching the house pattern of one small private pair per
# view module rather than a shared core utility. ──────────────────────────

def _is_admin(user) -> bool:
    """Settings-level admin: unrestricted access across all branches."""
    return getattr(user, 'is_superuser', False) or _has_perm(user, 'settings.edit')


def _resolve_user_branch(user):
    """Return the Branch object for a user's assigned branch, or None."""
    if not user.branch:
        return None
    return Branch.objects.filter(branch_name=user.branch, status=Branch.STATUS_ACTIVE).first()


def _employee_out_of_scope(requesting_user, employee) -> bool:
    """
    Mirrors apps.accounts.views._employee_out_of_branch_scope's exact rule
    (used by EmployeePromotionHistoryView) — managers restricted to direct
    reports, everyone else without settings.edit restricted to their own
    branch. Viewing your OWN assets is always allowed regardless (checked
    separately by callers before reaching this).
    """
    if _is_admin(requesting_user):
        return False
    role = requesting_user.role
    if role and getattr(role, 'can_manage_team', False):
        return employee.reporting_manager_id != requesting_user.id
    return (employee.branch or '') != (requesting_user.branch or '')


class AssetListCreateView(APIView):
    """GET /assets/  — list, filtered/paginated. POST /assets/ — create."""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        if not _has_perm(request.user, 'assets.view'):
            return error('You do not have permission to view assets.', http_status=403)

        qs = Asset.objects.select_related('branch', 'created_by')

        if not _is_admin(request.user):
            branch_obj = _resolve_user_branch(request.user)
            qs = qs.filter(branch=branch_obj) if branch_obj else qs.none()

        search = (request.query_params.get('search') or '').strip()
        if search:
            qs = qs.filter(
                Q(asset_tag__icontains=search)
                | Q(asset_name__icontains=search)
                | Q(serial_number__icontains=search)
            )

        status_param = (request.query_params.get('status') or '').strip()
        if status_param:
            qs = qs.filter(status=status_param)

        category = (request.query_params.get('category') or '').strip()
        if category:
            qs = qs.filter(category__iexact=category)

        asset_type = (request.query_params.get('asset_type') or '').strip()
        if asset_type:
            qs = qs.filter(asset_type__iexact=asset_type)

        brand = (request.query_params.get('brand') or '').strip()
        if brand:
            qs = qs.filter(brand__iexact=brand)

        branch_param = (request.query_params.get('branch') or '').strip()
        if branch_param:
            qs = qs.filter(branch_id=branch_param)

        # Assets currently assigned to a given employee — joins to the ONE
        # active assignment row per asset (see the partial unique constraint
        # on AssetAssignment), so this never fans out into duplicate rows.
        employee_param = (request.query_params.get('assigned_to') or '').strip()
        if employee_param:
            qs = qs.filter(
                assignments__employee_id=employee_param,
                assignments__status=AssetAssignment.STATUS_ASSIGNED,
            )

        qs = qs.order_by('-created_at')
        page_obj, paginator = paginate(qs, request, default_page_size=20)
        return success(
            'Assets retrieved successfully.',
            data=paginated_data(paginator, page_obj, AssetSerializer(page_obj.object_list, many=True).data),
        )

    def post(self, request):
        if not _has_perm(request.user, 'assets.create'):
            return error('You do not have permission to create assets.', http_status=403)

        serializer = AssetSerializer(data=request.data)
        if not serializer.is_valid():
            return error(first_error(serializer.errors), data=serializer.errors)

        branch = serializer.validated_data.get('branch')
        if not _is_admin(request.user):
            user_branch = _resolve_user_branch(request.user)
            if not user_branch or branch is None or branch.pk != user_branch.pk:
                return error('You can only create assets for your own branch.', http_status=403)

        try:
            with transaction.atomic():
                asset = serializer.save(created_by=request.user)
        except IntegrityError:
            return error(
                f"Asset Tag \"{serializer.validated_data.get('asset_tag', '')}\" already exists.",
                http_status=409,
            )

        AuditLog.objects.create(
            user=request.user, action='asset_created', module='assets',
            object_id=str(asset.pk), changes={'asset_tag': asset.asset_tag, 'asset_name': asset.asset_name},
            branch=asset.branch.branch_name, ip_address=get_client_ip(request),
        )
        return success('Asset created successfully.', data=AssetSerializer(asset).data, http_status=201)


class AssetDetailView(APIView):
    """GET/PUT/PATCH/DELETE /assets/<uuid:pk>/"""
    permission_classes = [IsAuthenticated]

    def _get(self, request, pk):
        try:
            asset = Asset.objects.select_related('branch', 'created_by').get(pk=pk)
        except Asset.DoesNotExist:
            return None, error('Asset not found.', http_status=404)
        if not _is_admin(request.user):
            user_branch = _resolve_user_branch(request.user)
            if not user_branch or asset.branch_id != user_branch.pk:
                return None, error('You do not have access to this asset.', http_status=403)
        return asset, None

    def get(self, request, pk):
        if not _has_perm(request.user, 'assets.view'):
            return error('You do not have permission to view assets.', http_status=403)
        asset, err = self._get(request, pk)
        if err:
            return err
        return success('Asset retrieved.', data=AssetSerializer(asset).data)

    def _update(self, request, pk, partial: bool):
        if not _has_perm(request.user, 'assets.edit'):
            return error('You do not have permission to edit assets.', http_status=403)
        asset, err = self._get(request, pk)
        if err:
            return err
        serializer = AssetSerializer(asset, data=request.data, partial=partial)
        if not serializer.is_valid():
            return error(first_error(serializer.errors), data=serializer.errors)
        try:
            updated = serializer.save()
        except IntegrityError:
            return error(
                f"Asset Tag \"{serializer.validated_data.get('asset_tag', asset.asset_tag)}\" already exists.",
                http_status=409,
            )
        AuditLog.objects.create(
            user=request.user, action='asset_updated', module='assets',
            object_id=str(updated.pk), changes={'asset_tag': updated.asset_tag},
            branch=updated.branch.branch_name, ip_address=get_client_ip(request),
        )
        return success('Asset updated successfully.', data=AssetSerializer(updated).data)

    def put(self, request, pk):
        return self._update(request, pk, partial=False)

    def patch(self, request, pk):
        return self._update(request, pk, partial=True)

    def delete(self, request, pk):
        if not _has_perm(request.user, 'assets.delete'):
            return error('You do not have permission to delete assets.', http_status=403)
        asset, err = self._get(request, pk)
        if err:
            return err

        if asset.status == Asset.STATUS_ASSIGNED:
            return error(
                f'Cannot delete "{asset.asset_tag}" — it is currently assigned to an employee. '
                'Return it first.',
                http_status=409,
            )

        AuditLog.objects.create(
            user=request.user, action='asset_deleted', module='assets',
            object_id=str(asset.pk), changes={'asset_tag': asset.asset_tag, 'asset_name': asset.asset_name},
            branch=asset.branch.branch_name, ip_address=get_client_ip(request),
        )
        asset.delete()
        return success('Asset deleted successfully.')


class EmployeeAssetsView(APIView):
    """
    GET /assets/employees/<uuid:employee_id>/ — current + history for one
    employee. Self-view is always allowed (own profile); viewing someone
    else's requires assets.view AND the same branch/manager scoping
    EmployeePromotionHistoryView already uses.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request, employee_id):
        try:
            employee = User.objects.get(pk=employee_id)
        except User.DoesNotExist:
            return error('Employee not found.', http_status=404)

        is_self = str(request.user.pk) == str(employee_id)
        if not is_self:
            if not _has_perm(request.user, 'assets.view'):
                return error('You do not have permission to view assets.', http_status=403)
            if _employee_out_of_scope(request.user, employee):
                return error('Employee not found.', http_status=404)

        qs = (
            AssetAssignment.objects
            .filter(employee=employee)
            .select_related('asset', 'asset__branch', 'employee', 'assigned_by', 'returned_by')
        )
        current = qs.filter(status=AssetAssignment.STATUS_ASSIGNED)
        history = qs.filter(status=AssetAssignment.STATUS_RETURNED)

        return success('Employee assets retrieved.', data={
            'current': AssetAssignmentSerializer(current, many=True).data,
            'history': AssetAssignmentSerializer(history, many=True).data,
        })


class AssignAssetView(APIView):
    """POST /assets/employees/<uuid:employee_id>/assign/"""
    permission_classes = [IsAuthenticated]

    def post(self, request, employee_id):
        if not _has_perm(request.user, 'assets.edit'):
            return error('You do not have permission to assign assets.', http_status=403)

        try:
            employee = User.objects.get(pk=employee_id)
        except User.DoesNotExist:
            return error('Employee not found.', http_status=404)

        if not _is_admin(request.user) and _employee_out_of_scope(request.user, employee):
            return error('Employee not found.', http_status=404)

        serializer = AssignAssetSerializer(data=request.data)
        if not serializer.is_valid():
            return error(first_error(serializer.errors), data=serializer.errors)

        asset = serializer.validated_data['asset']

        try:
            with transaction.atomic():
                # Re-check status inside the transaction (SELECT ... FOR
                # UPDATE) — the partial unique constraint on AssetAssignment
                # is the ultimate DB-level guard against a race here, but
                # locking the Asset row too keeps the "already assigned"
                # error message accurate rather than surfacing a raw
                # IntegrityError to the caller under concurrent requests.
                asset = Asset.objects.select_for_update().get(pk=asset.pk)
                if asset.status != Asset.STATUS_AVAILABLE:
                    return error(
                        f'"{asset.asset_tag}" is not available — current status: {asset.get_status_display()}.',
                        http_status=409,
                    )

                assignment = AssetAssignment.objects.create(
                    asset=asset,
                    employee=employee,
                    assigned_date=serializer.validated_data['assigned_date'],
                    condition_at_assignment=serializer.validated_data['condition_at_assignment'],
                    expected_return_date=serializer.validated_data.get('expected_return_date'),
                    assign_remarks=serializer.validated_data.get('remarks', ''),
                    assigned_by=request.user,
                )
                asset.status = Asset.STATUS_ASSIGNED
                asset.condition = serializer.validated_data['condition_at_assignment']
                asset.save(update_fields=['status', 'condition', 'updated_at'])
        except IntegrityError:
            return error(
                f'"{asset.asset_tag}" was just assigned to someone else — please refresh and try again.',
                http_status=409,
            )

        AuditLog.objects.create(
            user=request.user, action='asset_assigned', module='assets',
            object_id=str(assignment.pk),
            changes={'asset_tag': asset.asset_tag, 'employee': employee.full_name},
            branch=asset.branch.branch_name, ip_address=get_client_ip(request),
        )
        logger.info('Asset %s assigned to %s by %s', asset.asset_tag, employee.email, request.user.email)
        return success(
            'Asset assigned successfully.',
            data=AssetAssignmentSerializer(assignment).data,
            http_status=201,
        )


class ReturnAssetView(APIView):
    """POST /assets/assignments/<uuid:assignment_id>/return/"""
    permission_classes = [IsAuthenticated]

    def post(self, request, assignment_id):
        if not _has_perm(request.user, 'assets.edit'):
            return error('You do not have permission to return assets.', http_status=403)

        try:
            assignment = (
                AssetAssignment.objects
                .select_related('asset', 'employee', 'asset__branch')
                .get(pk=assignment_id, status=AssetAssignment.STATUS_ASSIGNED)
            )
        except AssetAssignment.DoesNotExist:
            return error('Active assignment not found.', http_status=404)

        if not _is_admin(request.user) and _employee_out_of_scope(request.user, assignment.employee):
            return error('Active assignment not found.', http_status=404)

        serializer = ReturnAssetSerializer(data=request.data, context={'assignment': assignment})
        if not serializer.is_valid():
            return error(first_error(serializer.errors), data=serializer.errors)

        return_condition = serializer.validated_data['return_condition']
        # Damaged-on-return routes the asset to 'damaged' for HR follow-up;
        # any other returned condition goes straight back to 'available'.
        new_status = Asset.STATUS_DAMAGED if return_condition == Asset.CONDITION_DAMAGED else Asset.STATUS_AVAILABLE

        with transaction.atomic():
            assignment.status = AssetAssignment.STATUS_RETURNED
            assignment.return_date = serializer.validated_data['return_date']
            assignment.return_condition = return_condition
            assignment.return_reason = serializer.validated_data['return_reason']
            assignment.return_remarks = serializer.validated_data.get('remarks', '')
            assignment.returned_by = request.user
            assignment.save(update_fields=[
                'status', 'return_date', 'return_condition', 'return_reason',
                'return_remarks', 'returned_by', 'updated_at',
            ])

            asset = assignment.asset
            asset.status = new_status
            asset.condition = return_condition
            asset.save(update_fields=['status', 'condition', 'updated_at'])

        AuditLog.objects.create(
            user=request.user, action='asset_returned', module='assets',
            object_id=str(assignment.pk),
            changes={'asset_tag': asset.asset_tag, 'employee': assignment.employee.full_name, 'new_status': new_status},
            branch=asset.branch.branch_name, ip_address=get_client_ip(request),
        )
        logger.info('Asset %s returned by %s (assignment %s)', asset.asset_tag, request.user.email, assignment.pk)
        return success('Asset returned successfully.', data=AssetAssignmentSerializer(assignment).data)
