import logging
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from django.shortcuts import get_object_or_404

from core.responses import success, error, first_error
from core.permissions import has_perm as _has_perm
from apps.payroll.models import BranchPayrollConfig
from apps.payroll.serializers import BranchPayrollConfigSerializer
from apps.branch.models import Branch

logger = logging.getLogger(__name__)


class BranchPayrollConfigListView(APIView):
    """List all branch payroll configs / create one for a branch."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        if not _has_perm(request.user, 'payroll.view'):
            return error('Only HR admin can view branch payroll configs.', http_status=403)

        configs = BranchPayrollConfig.objects.select_related(
            'branch', 'branch__state', 'salary_structure',
        ).order_by('branch__branch_name')
        serializer = BranchPayrollConfigSerializer(configs, many=True)
        return success('Branch payroll configs retrieved.', serializer.data)

    def post(self, request):
        if not _has_perm(request.user, 'payroll.create'):
            return error('Only HR admin can create branch payroll configs.', http_status=403)

        branch_id = request.data.get('branch')
        if BranchPayrollConfig.objects.filter(branch_id=branch_id).exists():
            return error('Payroll config for this branch already exists. Use PUT to update.')

        serializer = BranchPayrollConfigSerializer(data=request.data)
        if not serializer.is_valid():
            return error(first_error(serializer.errors))

        config = serializer.save()
        logger.info(
            'BranchPayrollConfig created for branch %s by %s',
            config.branch.branch_name, request.user.email,
        )
        return success('Branch config created.', BranchPayrollConfigSerializer(config).data, http_status=201)


class BranchPayrollConfigDetailView(APIView):
    """Retrieve / update payroll config for a specific branch."""

    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        if not _has_perm(request.user, 'payroll.view'):
            return error('Only HR admin can view branch payroll configs.', http_status=403)

        config = get_object_or_404(
            BranchPayrollConfig.objects.select_related('branch', 'branch__state', 'salary_structure'),
            pk=pk,
        )
        return success('Branch payroll config retrieved.', BranchPayrollConfigSerializer(config).data)

    def put(self, request, pk):
        if not _has_perm(request.user, 'payroll.edit'):
            return error('Only HR admin can update branch payroll configs.', http_status=403)

        config = get_object_or_404(BranchPayrollConfig, pk=pk)
        serializer = BranchPayrollConfigSerializer(config, data=request.data, partial=True)
        if not serializer.is_valid():
            return error(first_error(serializer.errors))

        serializer.save()
        logger.info(
            'BranchPayrollConfig for %s updated by %s',
            config.branch.branch_name, request.user.email,
        )
        return success('Branch config updated.', serializer.data)

    def delete(self, request, pk):
        if not _has_perm(request.user, 'payroll.delete'):
            return error('Only HR admin can remove branch payroll configs.', http_status=403)

        config = get_object_or_404(BranchPayrollConfig, pk=pk)
        branch_name = config.branch.branch_name
        config.delete()
        logger.info(
            'BranchPayrollConfig for %s removed by %s — reverting to system defaults',
            branch_name, request.user.email,
        )
        return success('Branch config removed. Branch will use system defaults.')


class BranchPayrollConfigByBranchView(APIView):
    """GET payroll config by Branch ID."""

    permission_classes = [IsAuthenticated]

    def get(self, request, branch_pk):
        if not _has_perm(request.user, 'payroll.view'):
            return error('Only HR admin can view branch payroll configs.', http_status=403)

        branch = get_object_or_404(Branch, pk=branch_pk)
        config = BranchPayrollConfig.objects.filter(branch=branch).select_related(
            'branch', 'branch__state', 'salary_structure',
        ).first()
        if config is None:
            return error('No payroll config exists for this branch yet.', http_status=404)
        return success('Branch payroll config retrieved.', BranchPayrollConfigSerializer(config).data)
