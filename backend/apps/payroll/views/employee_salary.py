import logging
import uuid as _uuid_mod

from django.contrib.auth import get_user_model
from django.shortcuts import get_object_or_404
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView

from core.pagination import paginate, paginated_data
from core.permissions import has_perm as _has_perm
from core.responses import error, first_error, get_client_ip, success
from apps.payroll.models import EmployeeSalaryConfig
from apps.payroll.serializers import EmployeeSalaryConfigSerializer
from apps.payroll.services_salary_components import (
    RevisionNotAllowed, parse_components, resolve_template_structure, revision_problem, save_revision,
    specs_for_revision, specs_from_structure, summary,
)
from apps.payroll.views.cycles import _is_admin

User = get_user_model()


def _resolve_employee(identifier):
    """Accept a UUID string or an employee_id display code; return the User or None."""
    try:
        _uuid_mod.UUID(str(identifier))
        return User.objects.filter(pk=identifier, is_active=True).first()
    except (ValueError, AttributeError):
        return User.objects.filter(employee_id=identifier, is_active=True).first()

logger = logging.getLogger(__name__)


class EmployeeSalaryConfigListView(APIView):
    """List active salary configs (all employees) / assign CTC to an employee."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        if not _has_perm(request.user, 'payroll.view'):
            return error('Only HR admin can view salary configurations.', http_status=403)

        configs = EmployeeSalaryConfig.objects.filter(is_active=True).select_related(
            'employee', 'salary_structure', 'template_structure',
        ).prefetch_related('components').order_by('employee__full_name')

        # Matches the scoping already applied to the /employees/ list
        # (EmployeeListCreateView.get()), which this list is zipped against on
        # the frontend — without matching it exactly, IDs never lined up and
        # every row read "Not set".
        #   - A manager (can_manage_team) only sees their own direct reports'
        #     configs, not their whole branch's.
        #   - Everyone else without settings.edit is branch-scoped.
        if not _is_admin(request.user):
            if request.user.role and request.user.role.can_manage_team:
                configs = configs.filter(employee__reporting_manager=request.user)
            elif request.user.branch:
                configs = configs.filter(employee__branch=request.user.branch)
            else:
                return error(
                    'Your account is not assigned to a branch. Contact an administrator.',
                    http_status=400,
                )

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
        if not _is_admin(request.user) and employee.branch != request.user.branch:
            return error('Access denied.', http_status=403)

        data = {k: request.data.get(k) for k in ('annual_ctc', 'salary_structure', 'effective_from')
                if k in request.data}
        data['employee'] = str(employee.id)

        serializer = EmployeeSalaryConfigSerializer(data=data)
        if not serializer.is_valid():
            return error(first_error(serializer.errors))

        vd = serializer.validated_data
        annual_ctc = vd['annual_ctc']
        if annual_ctc <= 0:
            return error('Annual CTC must be greater than zero.')
        override = vd.get('salary_structure')
        template = resolve_template_structure(employee, override)

        # Components: HR's edited list from Assign CTC, or (for callers that
        # don't send any) a copy of the template's current components, so
        # later edits to the shared structure never change this revision.
        if request.data.get('components') is not None:
            specs, errors = parse_components(request.data.get('components'))
            if errors:
                return error(errors[0], data={'errors': errors})
        elif template is not None:
            specs = specs_from_structure(template.components.filter(is_active=True).order_by('order'))
        else:
            specs = []

        problem = revision_problem(employee, vd['effective_from'])
        if problem:
            return error(problem, data={'errors': [problem]})

        if str(request.data.get('dry_run', '')).lower() in ('1', 'true', 'yes'):
            return success('Preview ready. Nothing has been saved.', self._preview(
                employee, annual_ctc, vd['effective_from'], template, specs,
            ))

        try:
            config = save_revision(
                employee=employee, annual_ctc=annual_ctc, effective_from=vd['effective_from'],
                salary_structure=override, template_structure=template, specs=specs,
                user=request.user, ip_address=get_client_ip(request), source='assign_ctc',
            )
        except RevisionNotAllowed as exc:          # changed between the check above and the save
            return error(str(exc), data={'errors': [str(exc)]})
        logger.info(
            'Salary config created for %s (CTC ₹%s, %d components) by %s',
            employee.full_name, config.annual_ctc, len(specs), request.user.email,
        )
        config = EmployeeSalaryConfig.objects.prefetch_related('components').get(pk=config.pk)
        return success('Salary config assigned.', EmployeeSalaryConfigSerializer(config).data, http_status=201)

    @staticmethod
    def _preview(employee, annual_ctc, effective_from, template, specs) -> dict:
        out = {
            'template_structure': {'id': str(template.pk), 'name': template.name} if template else None,
            **summary(specs, annual_ctc),
            'previous': None,
        }
        if template is None and not specs:
            out['warnings'].insert(0, 'No salary structure applies (no employee, branch or company default '
                                      'structure). Add components, or set a structure first.')
        current = (EmployeeSalaryConfig.objects.filter(employee=employee, is_active=True)
                   .select_related('salary_structure', 'template_structure').prefetch_related('components').first())
        if current is not None:
            prev_specs, prev_structure = specs_for_revision(current, employee)
            out['previous'] = {
                'id': str(current.pk), 'annual_ctc': str(current.annual_ctc),
                'effective_from': current.effective_from.isoformat(),
                'structure_name': prev_structure.name if prev_structure else None,
                'is_snapshot': bool(current.components.all()),
                **summary(prev_specs or [], current.annual_ctc),
            }
            if effective_from == current.effective_from:
                out['warnings'].append('Same effective date as the current revision: this revision replaces it.')
        return out


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
        # A revision with its own components is history: its salary terms are
        # changed by saving a new revision (Assign CTC), not edited in place.
        locked_fields = {'annual_ctc', 'effective_from', 'salary_structure', 'components'}
        if 'components' in request.data or (
            config.components.exists() and locked_fields & set(request.data.keys())
        ):
            return error('Salary terms of a saved revision cannot be edited. Assign a new CTC revision instead.')
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
        if not _is_admin(request.user) and employee.branch != request.user.branch:
            return error('Access denied.', http_status=403)

        configs = EmployeeSalaryConfig.objects.filter(
            employee=employee,
        ).select_related('salary_structure', 'template_structure', 'created_by').prefetch_related(
            'components',
        ).order_by('-effective_from', '-created_at')

        serializer = EmployeeSalaryConfigSerializer(configs, many=True)
        return success('Salary history retrieved.', serializer.data)
