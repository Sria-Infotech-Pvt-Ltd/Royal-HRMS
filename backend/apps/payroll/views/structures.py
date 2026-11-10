import logging
from django.http import HttpResponse
from rest_framework.views import APIView
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.permissions import IsAuthenticated
from django.shortcuts import get_object_or_404

from core.file_utils import _CSV_MIME, _XLSX_MIME, build_sample_csv, build_sample_xlsx
from core.responses import success, error, first_error, get_client_ip
from core.permissions import has_perm as _has_perm
from apps.payroll import services_structure_import as imp
from apps.payroll import services_salary_import as sal_imp
from apps.payroll.audit import log_change, snapshot
from apps.payroll.models import SalaryStructure, SalaryComponent
from apps.payroll.serializers import (
    SalaryStructureSerializer,
    SalaryStructureListSerializer,
    SalaryComponentSerializer,
)

logger = logging.getLogger(__name__)


class SalaryStructureListView(APIView):
    """List all salary structures / create a new one."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        if not _has_perm(request.user, 'payroll.view'):
            return error('Only HR admin can view salary structures.', http_status=403)

        structures = SalaryStructure.objects.filter(is_active=True).order_by('name')
        serializer = SalaryStructureListSerializer(structures, many=True)
        return success('Salary structures retrieved.', serializer.data)

    def post(self, request):
        if not _has_perm(request.user, 'payroll.create'):
            return error('Only HR admin can create salary structures.', http_status=403)

        serializer = SalaryStructureListSerializer(data=request.data)
        if not serializer.is_valid():
            return error(first_error(serializer.errors))

        # Only one default allowed
        if request.data.get('is_default'):
            SalaryStructure.objects.filter(is_default=True).update(is_default=False)

        structure = serializer.save()
        log_change(request, 'salary_structure_created', structure.pk, None, snapshot(structure))
        logger.info('Salary structure "%s" created by %s', structure.name, request.user.email)
        return success('Salary structure created.', SalaryStructureSerializer(structure).data, http_status=201)


class SalaryStructureDetailView(APIView):
    """Retrieve / update / soft-delete a single salary structure."""

    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        if not _has_perm(request.user, 'payroll.view'):
            return error('Only HR admin can view salary structures.', http_status=403)

        structure = get_object_or_404(SalaryStructure, pk=pk)
        serializer = SalaryStructureSerializer(structure)
        return success('Salary structure retrieved.', serializer.data)

    def put(self, request, pk):
        if not _has_perm(request.user, 'payroll.edit'):
            return error('Only HR admin can update salary structures.', http_status=403)

        structure = get_object_or_404(SalaryStructure, pk=pk)
        before = snapshot(structure)
        serializer = SalaryStructureListSerializer(structure, data=request.data, partial=True)
        if not serializer.is_valid():
            return error(first_error(serializer.errors))

        if request.data.get('is_default'):
            SalaryStructure.objects.exclude(pk=pk).filter(is_default=True).update(is_default=False)

        serializer.save()
        log_change(request, 'salary_structure_updated', structure.pk, before, snapshot(structure))
        return success('Salary structure updated.', SalaryStructureSerializer(structure).data)

    def delete(self, request, pk):
        if not _has_perm(request.user, 'payroll.delete'):
            return error('Only HR admin can delete salary structures.', http_status=403)

        structure = get_object_or_404(SalaryStructure, pk=pk)
        if structure.is_default:
            return error('Cannot delete the default salary structure.')
        structure.is_active = False
        structure.save(update_fields=['is_active', 'updated_at'])
        log_change(request, 'salary_structure_deactivated', structure.pk, None, None,
                   extra={'name': structure.name})
        return success('Salary structure deactivated.')


class SalaryComponentListView(APIView):
    """List components in a structure / add a new component."""

    permission_classes = [IsAuthenticated]

    def get(self, request, structure_pk):
        if not _has_perm(request.user, 'payroll.view'):
            return error('Only HR admin can view salary components.', http_status=403)

        structure = get_object_or_404(SalaryStructure, pk=structure_pk)
        components = structure.components.filter(is_active=True)
        serializer = SalaryComponentSerializer(components, many=True)
        return success('Components retrieved.', serializer.data)

    def post(self, request, structure_pk):
        if not _has_perm(request.user, 'payroll.create'):
            return error('Only HR admin can add components.', http_status=403)

        structure = get_object_or_404(SalaryStructure, pk=structure_pk)
        serializer = SalaryComponentSerializer(data=request.data)
        if not serializer.is_valid():
            return error(first_error(serializer.errors))

        component = serializer.save(structure=structure)
        log_change(request, 'salary_component_created', component.pk, None, snapshot(component),
                   extra={'structure': structure.name})
        logger.info(
            'Component "%s" added to structure "%s" by %s',
            component.name, structure.name, request.user.email,
        )
        return success('Component added.', SalaryComponentSerializer(component).data, http_status=201)


class SalaryComponentDetailView(APIView):
    """Update / soft-delete a single component."""

    permission_classes = [IsAuthenticated]

    def put(self, request, structure_pk, pk):
        if not _has_perm(request.user, 'payroll.edit'):
            return error('Only HR admin can update components.', http_status=403)

        component = get_object_or_404(SalaryComponent, pk=pk, structure__pk=structure_pk)
        before = snapshot(component)
        serializer = SalaryComponentSerializer(component, data=request.data, partial=True)
        if not serializer.is_valid():
            return error(first_error(serializer.errors))

        serializer.save()
        log_change(request, 'salary_component_updated', component.pk, before, snapshot(component),
                   extra={'structure': component.structure.name})
        return success('Component updated.', serializer.data)

    def delete(self, request, structure_pk, pk):
        if not _has_perm(request.user, 'payroll.delete'):
            return error('Only HR admin can delete components.', http_status=403)

        component = get_object_or_404(SalaryComponent, pk=pk, structure__pk=structure_pk)
        component.is_active = False
        component.save(update_fields=['is_active', 'updated_at'])
        log_change(request, 'salary_component_deactivated', component.pk, None, None,
                   extra={'name': component.name, 'structure': component.structure.name})
        return success('Component deactivated.')


# ── Imports (Settings → Payroll → Salary Structures) ─────────────────────────

def _flag(request, name) -> bool:
    return str(request.data.get(name, '')).lower() in ('1', 'true', 'yes')


class _SampleMixin:
    """?format=csv|xlsx picks the file type, not a DRF renderer."""

    def perform_content_negotiation(self, request, force=False):
        from rest_framework.renderers import JSONRenderer
        return (JSONRenderer(), 'application/json')

    def sample_response(self, request, headers, rows, sheet, filename):
        if (request.query_params.get('format') or 'csv').lower().strip() == 'xlsx':
            content, mime, ext = build_sample_xlsx(headers, rows, sheet), _XLSX_MIME, 'xlsx'
        else:
            content, mime, ext = build_sample_csv(headers, rows), _CSV_MIME, 'csv'
        response = HttpResponse(content, content_type=mime)
        response['Content-Disposition'] = f'attachment; filename="{filename}.{ext}"'
        return response


class SalaryStructureImportView(APIView):
    """POST multipart: file (.csv/.xlsx), dry_run=true for the preview,
    update_existing=true to allow updating structures that already exist.
    The confirm request re-reads and re-validates the file."""

    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser]

    def post(self, request):
        allow_update = _flag(request, 'update_existing')
        if not _has_perm(request.user, 'payroll.create') or (
            allow_update and not _has_perm(request.user, 'payroll.edit')
        ):
            return error('You do not have permission to import salary structures.', http_status=403)
        uploaded = request.FILES.get('file')
        if not uploaded:
            return error('Attach a CSV or Excel (.xlsx) file.')
        rows, problem = imp.read_rows(uploaded, imp._STRUCTURE_COLUMNS, {
            'structure': 'Structure Name', 'component': 'Component', 'type': 'Type',
            'calculation': 'Calculation', 'value': 'Value',
        })
        if problem:
            return error(problem)
        plan = imp.plan_structures(rows, allow_update=allow_update)
        if _flag(request, 'dry_run'):
            return success('Preview ready. Nothing has been saved yet.',
                           {'summary': imp.summarise(plan), 'structures': imp.public_plan(plan)})
        if any(p['status'] == imp.ERROR for p in plan):
            return error('Fix the errors in the file before importing — nothing was saved.',
                         data={'summary': imp.summarise(plan), 'structures': imp.public_plan(plan)})
        audits = imp.apply_structures(plan)
        for a in audits:
            log_change(request, a['action'], a['object_id'], None, a['changes'])
        summary = imp.summarise(plan) | {'created': sum(p['status'] == 'created' for p in plan),
                                          'updated': sum(p['status'] == 'updated' for p in plan)}
        logger.info('Salary structure import by %s: %s', request.user.email, summary)
        return success('Salary structures imported.', {'summary': summary, 'structures': imp.public_plan(plan)})


class SalaryStructureImportSampleView(_SampleMixin, APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        if not _has_perm(request.user, 'payroll.create'):
            return error('You do not have permission to import salary structures.', http_status=403)
        return self.sample_response(request, imp.STRUCTURE_HEADERS, imp.STRUCTURE_SAMPLE_ROWS,
                                    'Salary Structures', 'salary_structure_import_sample')


class SalaryStructureAssignImportView(APIView):
    """POST multipart: file with Employee ID, Structure Name, Effective From;
    dry_run=true for the preview. Each valid row saves a new salary revision
    (same CTC, the structure's components copied) — existing revisions are
    never edited. Same scope as Assign CTC."""

    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser]

    def post(self, request):
        if not _has_perm(request.user, 'payroll.edit'):
            return error('You do not have permission to assign salary structures.', http_status=403)
        uploaded = request.FILES.get('file')
        if not uploaded:
            return error('Attach a CSV or Excel (.xlsx) file.')
        rows, problem = imp.read_rows(uploaded, imp._ASSIGN_COLUMNS, {
            'employee_id': 'Employee ID', 'structure': 'Structure Name', 'effective_from': 'Effective From',
        })
        if problem:
            return error(problem)
        from apps.payroll.views.cycles import _is_admin
        admin = _is_admin(request.user)
        plan = imp.plan_assignments(rows, in_scope=lambda emp: admin or emp.branch == request.user.branch)
        public = lambda: [{k: v for k, v in p.items() if not k.startswith('_')} for p in plan]
        if _flag(request, 'dry_run'):
            return success('Preview ready. Nothing has been saved yet.',
                           {'summary': imp.summarise_assignments(plan), 'rows': public()})
        saved = imp.apply_assignments(plan, user=request.user, ip_address=get_client_ip(request))
        summary = imp.summarise_assignments(plan) | {'updated': saved}
        log_change(request, 'salary_structure_assignment_import', '', None,
                   {'saved': saved, 'rows': summary['total']})
        return success(f'{saved} salary revision(s) saved.', {'summary': summary, 'rows': public()})


class SalaryStructureAssignSampleView(_SampleMixin, APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        if not _has_perm(request.user, 'payroll.edit'):
            return error('You do not have permission to assign salary structures.', http_status=403)
        return self.sample_response(request, imp.ASSIGN_HEADERS, imp.ASSIGN_SAMPLE_ROWS,
                                    'Assignments', 'salary_structure_assignment_sample')

class SalaryImportView(APIView):
    """POST multipart: file with one row per employee (Employee Code, Effective
    From, one column per component amount, ...); dry_run=true for the preview;
    replace_same_date=true to replace a revision with the same Effective From.
    Each valid row saves a new salary revision (services_salary_import). Same
    scope as Assign CTC. Nothing is saved if any row has an error."""

    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser]

    def post(self, request):
        if not _has_perm(request.user, 'payroll.edit'):
            return error('You do not have permission to import salaries.', http_status=403)
        uploaded = request.FILES.get('file')
        if not uploaded:
            return error('Attach a CSV or Excel (.xlsx) file.')
        rows, problem = imp.read_rows(uploaded, sal_imp.COLUMNS, sal_imp.REQUIRED, keep_other=True)
        if problem:
            return error(problem)
        from apps.payroll.views.cycles import _is_admin
        admin = _is_admin(request.user)
        plan = sal_imp.plan(rows, replace_same_date=_flag(request, 'replace_same_date'),
                            in_scope=lambda emp: admin or (bool(emp.branch) and emp.branch == request.user.branch))
        data = lambda: {'summary': sal_imp.summarise(plan), 'rows': sal_imp.public(plan)}
        if _flag(request, 'dry_run'):
            return success('Preview ready. Nothing has been saved yet.', data())
        bad = sal_imp.summarise(plan)[sal_imp.ERROR]
        if bad:
            return error(f'{bad} of {len(plan)} row(s) have errors. Nothing was saved — fix them and upload '
                         'the file again.', data=data())
        try:
            saved = sal_imp.apply(plan, user=request.user, ip_address=get_client_ip(request))
        except sal_imp.ImportAborted as exc:
            return error(f'{exc} Nothing was saved.', data=data())
        log_change(request, 'salary_import', '', None, {'saved': saved, 'rows': len(plan)})
        logger.info('Salary import by %s: %d revision(s) saved', request.user.email, saved)
        return success(f'{saved} salary revision(s) saved.', data())


class SalaryImportSampleView(_SampleMixin, APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        if not _has_perm(request.user, 'payroll.edit'):
            return error('You do not have permission to import salaries.', http_status=403)
        headers, rows = sal_imp.sample()
        return self.sample_response(request, headers, rows, 'Salaries', 'salary_import_sample')
