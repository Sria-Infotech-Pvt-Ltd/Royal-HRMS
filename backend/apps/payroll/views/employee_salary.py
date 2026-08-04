import logging
import uuid as _uuid_mod

from django.contrib.auth import get_user_model
from django.shortcuts import get_object_or_404
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView

from core.pagination import paginate, paginated_data
from core.responses import error, first_error, success
from apps.payroll.models import EmployeeSalaryConfig
from apps.payroll.serializers import EmployeeSalaryConfigSerializer

User = get_user_model()


def _resolve_employee(identifier):
    """Accept a UUID string or an employee_id display code; return the User or None."""
    try:
        _uuid_mod.UUID(str(identifier))
        return User.objects.filter(pk=identifier, is_active=True).first()
    except (ValueError, AttributeError):
        return User.objects.filter(employee_id=identifier, is_active=True).first()

logger = logging.getLogger(__name__)


def _has_perm(user, codename: str) -> bool:
    if not user or not user.role:
        return False
    if getattr(user, 'is_superuser', False):
        return True
    return user.role.role_permissions.filter(permission__codename=codename).exists()


class EmployeeSalaryConfigListView(APIView):
    """List active salary configs (all employees) / assign CTC to an employee."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        if not _has_perm(request.user, 'payroll.view'):
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
        if not _has_perm(request.user, 'payroll.edit'):
            return error('Only HR admin can assign salary configs.', http_status=403)

        # Accept UUID or display code (e.g. RSS00017) for the employee field
        employee_identifier = request.data.get('employee', '')
        employee = _resolve_employee(employee_identifier)
        if not employee:
            return error('Employee not found or is inactive.')

        data = request.data.copy()
        data['employee'] = str(employee.id)

        serializer = EmployeeSalaryConfigSerializer(data=data)
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
        if not _has_perm(request.user, 'payroll.view'):
            return error('Only HR admin can view salary configurations.', http_status=403)

        config = get_object_or_404(EmployeeSalaryConfig, pk=pk)
        return success('Salary config retrieved.', EmployeeSalaryConfigSerializer(config).data)

    def put(self, request, pk):
        if not _has_perm(request.user, 'payroll.edit'):
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
        if not _has_perm(request.user, 'payroll.view'):
            return error('Only HR admin can view salary history.', http_status=403)

        employee = _resolve_employee(employee_pk)
        if not employee:
            return error('Employee not found.', http_status=404)

        configs = EmployeeSalaryConfig.objects.filter(
            employee=employee,
        ).select_related('salary_structure').order_by('-effective_from')

        serializer = EmployeeSalaryConfigSerializer(configs, many=True)
        return success('Salary history retrieved.', serializer.data)
