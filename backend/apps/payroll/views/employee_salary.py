import logging
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from django.shortcuts import get_object_or_404

from core.responses import success, error, first_error
from core.pagination import paginate, paginated_data
from apps.payroll.models import EmployeeSalaryConfig
from apps.payroll.serializers import EmployeeSalaryConfigSerializer

logger = logging.getLogger(__name__)

HR_ADMIN_ROLES = frozenset(['system_admin', 'hr_admin'])


def _is_hr_admin(user):
    return user.role and user.role.name in HR_ADMIN_ROLES


class EmployeeSalaryConfigListView(APIView):
    """List active salary configs (all employees) / assign CTC to an employee."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        if not _is_hr_admin(request.user):
            return error('Only HR admin can view salary configurations.', http_status=403)

        configs = EmployeeSalaryConfig.objects.filter(is_active=True).select_related(
            'employee', 'salary_structure',
        ).order_by('employee__full_name')

        page_obj, paginator = paginate(configs, request)
        serializer = EmployeeSalaryConfigSerializer(page_obj.object_list, many=True)
        return success(
            'Employee salary configs retrieved.',
            paginated_data(paginator, page_obj, serializer.data),
        )

    def post(self, request):
        if not _is_hr_admin(request.user):
            return error('Only HR admin can assign salary configs.', http_status=403)

        serializer = EmployeeSalaryConfigSerializer(data=request.data)
        if not serializer.is_valid():
            return error(first_error(serializer.errors))

        employee = serializer.validated_data['employee']
        effective_from = serializer.validated_data['effective_from']

        # Deactivate any existing active config for this employee
        EmployeeSalaryConfig.objects.filter(
            employee=employee, is_active=True,
        ).update(is_active=False)

        config = serializer.save()
        logger.info(
            'Salary config created for %s (CTC ₹%s) by %s',
            employee.full_name, config.annual_ctc, request.user.email,
        )
        return success('Salary config assigned.', EmployeeSalaryConfigSerializer(config).data, http_status=201)


class EmployeeSalaryConfigDetailView(APIView):
    """Retrieve / update a single salary config record."""

    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        if not _is_hr_admin(request.user):
            return error('Only HR admin can view salary configurations.', http_status=403)

        config = get_object_or_404(EmployeeSalaryConfig, pk=pk)
        return success('Salary config retrieved.', EmployeeSalaryConfigSerializer(config).data)

    def put(self, request, pk):
        if not _is_hr_admin(request.user):
            return error('Only HR admin can update salary configs.', http_status=403)

        config = get_object_or_404(EmployeeSalaryConfig, pk=pk)
        serializer = EmployeeSalaryConfigSerializer(config, data=request.data, partial=True)
        if not serializer.is_valid():
            return error(first_error(serializer.errors))

        serializer.save()
        return success('Salary config updated.', serializer.data)


class EmployeeSalaryHistoryView(APIView):
    """All salary config records for a specific employee (history)."""

    permission_classes = [IsAuthenticated]

    def get(self, request, employee_pk):
        if not _is_hr_admin(request.user):
            return error('Only HR admin can view salary history.', http_status=403)

        configs = EmployeeSalaryConfig.objects.filter(
            employee_id=employee_pk,
        ).select_related('salary_structure').order_by('-effective_from')

        serializer = EmployeeSalaryConfigSerializer(configs, many=True)
        return success('Salary history retrieved.', serializer.data)
