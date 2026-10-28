from core.access import can_manage_team
import logging
import uuid as _uuid_mod

from django.contrib.auth import get_user_model
from django.shortcuts import get_object_or_404
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView

from core.pagination import paginate, paginated_data
from core.permissions import has_perm as _has_perm
from core.responses import error, first_error, success
from apps.payroll.models import (
    BranchPayrollConfig,
    EmployeeSalaryConfig,
    SalaryStructure,
)
from apps.payroll.serializers import EmployeeSalaryConfigSerializer
from apps.payroll.views.shared import _is_admin

User = get_user_model()


def _resolve_employee(identifier):
    """Accept a UUID string or an employee_id display code; return the User or None."""
    try:
        _uuid_mod.UUID(str(identifier))
        return User.objects.filter(pk=identifier, is_active=True).first()
    except (ValueError, AttributeError):
        return User.objects.filter(employee_id=identifier, is_active=True).first()

logger = logging.getLogger(__name__)


def _resolve_structure_for_employee(employee):
    branch_structure = BranchPayrollConfig.objects.filter(
        branch__branch_name=employee.branch,
        salary_structure__is_active=True,
    ).values_list('salary_structure_id', flat=True).first()
    if branch_structure:
        return branch_structure
    return SalaryStructure.objects.filter(is_default=True, is_active=True).values_list('id', flat=True).first()


# The values that make one salary record different from another. (effective_from alone does not: the same pay, dated
# differently, is still the same pay.)
_COMPARED_FIELDS = ('annual_ctc', 'salary_structure', 'pay_scale_group', 'pay_scale_level', 'basic_percent', 'earnings_override')


def _is_unchanged(current, validated) -> bool:
    """True when saving `validated` would just repeat `current`. Only fields actually sent are compared."""
    for field in _COMPARED_FIELDS:
        if field not in validated:
            continue
        new_value = validated[field]
        old_value = getattr(current, field)
        if field == 'salary_structure':
            # An omitted/blank structure means "use the default", which is what the record already resolves to.
            if new_value is None:
                continue
            if getattr(new_value, 'pk', new_value) != current.salary_structure_id:
                return False
        elif new_value != old_value:
            return False
    return True


class EmployeeSalaryConfigListView(APIView):
    """List active salary configs (all employees) / assign CTC to an employee."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        if not _has_perm(request.user, 'payroll.view'):
            return error('Only HR admin can view salary configurations.', http_status=403)

        configs = EmployeeSalaryConfig.objects.filter(is_active=True).select_related(
            'employee', 'salary_structure',
        ).order_by('employee__full_name')

        # Matches the scoping already applied to the /employees/ list
        # (EmployeeListCreateView.get()), which this list is zipped against on
        # the frontend — without matching it exactly, IDs never lined up and
        # every row read "Not set".
        #   - A manager (can_manage_team) only sees their own direct reports'
        #     configs, not their whole branch's.
        #   - Everyone else without settings.edit is branch-scoped.
        if not _is_admin(request.user):
            if can_manage_team(request.user):
                configs = configs.filter(employee__reporting_manager=request.user)
            elif request.user.branch:
                configs = configs.filter(employee__branch=request.user.branch)
            else:
                return error(
                    'Your account is not assigned to a branch. Contact an administrator.',
                    http_status=400,
                )

        page_obj, paginator = paginate(configs, request, strict_pages=True)
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
        if not _is_admin(request.user) and employee.branch != request.user.branch:
            return error('Access denied.', http_status=403)

        data = request.data.copy()
        data['employee'] = str(employee.id)
        if not data.get('salary_structure'):
            default_structure_id = _resolve_structure_for_employee(employee)
            if default_structure_id:
                data['salary_structure'] = str(default_structure_id)

        serializer = EmployeeSalaryConfigSerializer(data=data)
        if not serializer.is_valid():
            return error(first_error(serializer.errors))

        employee = serializer.validated_data['employee']

        # Saving the salary the employee already has changes nothing, so it must not add a revision: the history would
        # fill with identical copies of the same record.
        current = EmployeeSalaryConfig.objects.filter(employee=employee, is_active=True).order_by('-effective_from', '-created_at').first()
        if current and _is_unchanged(current, serializer.validated_data):
            return success(
                'No change — this salary is already set, so nothing was saved.',
                {**EmployeeSalaryConfigSerializer(current).data, 'unchanged': True},
            )

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
        if not _is_admin(request.user) and config.employee.branch != request.user.branch:
            return error('Access denied.', http_status=403)
        return success('Salary config retrieved.', EmployeeSalaryConfigSerializer(config).data)

    def put(self, request, pk):
        if not _has_perm(request.user, 'payroll.edit'):
            return error('Only HR admin can update salary configs.', http_status=403)

        config = get_object_or_404(EmployeeSalaryConfig, pk=pk)
        if not _is_admin(request.user) and config.employee.branch != request.user.branch:
            return error('Access denied.', http_status=403)
        serializer = EmployeeSalaryConfigSerializer(config, data=request.data, partial=True)
        if not serializer.is_valid():
            return error(first_error(serializer.errors))

        serializer.save()
        return success('Salary config updated.', serializer.data)


class EmployeeSalaryHistoryView(APIView):
    """All salary config records for a specific employee (history)."""

    permission_classes = [IsAuthenticated]

    def get(self, request, employee_pk):
        employee = _resolve_employee(employee_pk)
        # Everyone may read their OWN pay history (it is on their payslips and
        # in My Profile); anyone else's needs payroll.view.
        is_own_record = bool(employee) and employee.pk == request.user.pk
        if not is_own_record and not _has_perm(request.user, 'payroll.view'):
            return error('Only HR admin can view salary history.', http_status=403)

        if not employee:
            return error('Employee not found.', http_status=404)
        if not is_own_record and not _is_admin(request.user) and employee.branch != request.user.branch:
            return error('Access denied.', http_status=403)

        configs = EmployeeSalaryConfig.objects.filter(
            employee=employee,
        ).select_related('salary_structure').order_by('-effective_from')

        serializer = EmployeeSalaryConfigSerializer(configs, many=True)
        return success('Salary history retrieved.', serializer.data)
