import logging
from datetime import date
from decimal import Decimal

from django.db.models import Q, Sum
from django.shortcuts import get_object_or_404
from rest_framework.views import APIView
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.permissions import IsAuthenticated

from core.responses import success, error, first_error
from core.pagination import paginate, paginated_data
from core.permissions import has_perm as _has_perm
from apps.payroll.models import PayrollAdjustment
from apps.payroll.serializers import PayrollAdjustmentSerializer
from apps.accounts.models import User
from apps.payroll import services_adjustment_import as adj_imp
from apps.payroll.audit import log_change
from apps.payroll.services_structure_import import read_rows
from apps.payroll.views.structures import _SampleMixin

logger = logging.getLogger(__name__)

_ALLOWED_TYPES = {PayrollAdjustment.ADDITION, PayrollAdjustment.DEDUCTION, PayrollAdjustment.ARREAR}


def _parse_month(value) -> date | None:
    """Parse YYYY-MM or YYYY-MM-DD string to the first of that month."""
    if not value:
        return None
    try:
        parts = str(value).split('-')
        return date(int(parts[0]), int(parts[1]), 1)
    except (IndexError, ValueError, TypeError):
        return None


def _branch_scope(user):
    """(scope, error response). Company-wide payroll users (settings.edit /
    superuser) see every adjustment; everyone else only their own branch's
    employees — the same rule as payroll cycles and the salary list."""
    from apps.payroll.views.cycles import _is_admin
    if _is_admin(user):
        return None, None
    if not user.branch:
        return None, error('Your account is not assigned to a branch. Contact an administrator.', http_status=400)
    return user.branch, None


def _in_scope(qs, user):
    branch, problem = _branch_scope(user)
    if problem:
        return None, problem
    return (qs if branch is None else qs.filter(employee__branch=branch)), None


class PayrollAdjustmentListCreateView(APIView):
    """
    GET  /payroll/adjustments/?month=2026-07  — list adjustments for a month
    POST /payroll/adjustments/                — create a single adjustment
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        if not _has_perm(request.user, 'payroll.view'):
            return error('Access denied.', http_status=403)
        month = _parse_month(request.query_params.get('month'))
        qs = PayrollAdjustment.objects.select_related('employee', 'created_by').order_by(
            'month', 'employee__full_name', 'type',
        )
        if month:
            qs = qs.filter(month=month)
        qs, problem = _in_scope(qs, request.user)
        if problem:
            return problem

        # Month-level totals across ALL matching rows (not just the current
        # page) — one DB-side aggregate query, not a Python sum over fetched
        # rows, so it stays correct and cheap regardless of how many
        # adjustments exist for the month.
        totals = qs.aggregate(
            total_additions=Sum(
                'amount',
                filter=Q(type__in=[PayrollAdjustment.ADDITION, PayrollAdjustment.ARREAR]),
            ),
            total_deductions=Sum('amount', filter=Q(type=PayrollAdjustment.DEDUCTION)),
        )

        # 10/page default for this screen specifically — core.pagination's
        # own default (20) is untouched for every other endpoint using it.
        page_obj, paginator = paginate(qs, request, default_page_size=10)
        serializer = PayrollAdjustmentSerializer(page_obj.object_list, many=True)

        data = paginated_data(paginator, page_obj, serializer.data)
        data['total_additions'] = totals['total_additions'] or Decimal('0')
        data['total_deductions'] = totals['total_deductions'] or Decimal('0')
        return success('Adjustments retrieved.', data)

    def post(self, request):
        if not _has_perm(request.user, 'payroll.edit'):
            return error('Only HR admin can add payroll adjustments.', http_status=403)

        data = request.data.copy()
        employee_code = data.get('employee_code')
        if employee_code and not data.get('employee'):
            # Same resolution the bulk-import path already uses — the
            # "Add Adjustment" UI form only collects an employee code
            # (like the bulk-import CSV), not a raw employee id.
            try:
                employee = User.objects.get(employee_id__iexact=str(employee_code).strip(), is_active=True)
            except User.DoesNotExist:
                return error(f'No active employee found with code "{employee_code}".')
            except User.MultipleObjectsReturned:
                return error(f'Multiple employees matched code "{employee_code}".')
            data['employee'] = str(employee.id)

        # The "Add Adjustment" UI form sends month as "YYYY-MM" (same shape
        # the GET list/bulk-import query param already accepts via
        # _parse_month() below) — DRF's plain DateField only accepts strict
        # YYYY-MM-DD, so normalise here before validation using the same
        # helper rather than duplicating date-parsing logic.
        month_raw = data.get('month')
        if month_raw:
            parsed_month = _parse_month(month_raw)
            if parsed_month:
                data['month'] = parsed_month.isoformat()

        serializer = PayrollAdjustmentSerializer(data=data)
        if not serializer.is_valid():
            return error(first_error(serializer.errors))
        branch, problem = _branch_scope(request.user)
        if problem:
            return problem
        employee = serializer.validated_data['employee']
        if branch is not None and employee.branch != branch:
            return error('You can only add adjustments for employees in your branch.', http_status=403)
        adjustment = serializer.save(created_by=request.user)
        logger.info('PayrollAdjustment %s created by %s', adjustment.id, request.user.email)
        return success('Adjustment added.', PayrollAdjustmentSerializer(adjustment).data, http_status=201)


class PayrollAdjustmentDeleteView(APIView):
    """DELETE /payroll/adjustments/<pk>/"""
    permission_classes = [IsAuthenticated]

    def delete(self, request, pk):
        if not _has_perm(request.user, 'payroll.edit'):
            return error('Only HR admin can delete payroll adjustments.', http_status=403)
        # Out-of-branch adjustments answer 404, the same as missing ones.
        qs, problem = _in_scope(PayrollAdjustment.objects.all(), request.user)
        if problem:
            return problem
        adjustment = get_object_or_404(qs, pk=pk)
        adjustment.delete()
        logger.info('PayrollAdjustment %s deleted by %s', pk, request.user.email)
        return success('Adjustment deleted.')


class PayrollAdjustmentBulkImportView(APIView):
    """
    POST /payroll/adjustments/bulk-import/?month=2026-07 (multipart "file", .csv/.xlsx)
    Columns: Employee Code, Type (addition/deduction/arrear), Label, Amount.
    dry_run=true returns the preview and saves nothing. The confirm request
    re-reads and re-validates the whole file and saves nothing if any row has
    an error (services_adjustment_import).
    """
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser]

    def post(self, request):
        if not _has_perm(request.user, 'payroll.edit'):
            return error('Only HR admin can bulk-import adjustments.', http_status=403)

        month = _parse_month(request.query_params.get('month') or request.data.get('month'))
        if not month:
            return error('Choose the payroll month (YYYY-MM, e.g. 2026-07).')

        uploaded = request.FILES.get('file')
        if not uploaded:
            return error('Attach a CSV or Excel (.xlsx) file.')
        rows, problem = read_rows(uploaded, adj_imp.COLUMNS, adj_imp.REQUIRED)
        if problem:
            return error(problem)

        from apps.payroll.views.cycles import _is_admin
        admin = _is_admin(request.user)
        plan = adj_imp.plan(rows, month=month,
                            in_scope=lambda emp: admin or (bool(emp.branch) and emp.branch == request.user.branch))
        data = lambda: {'month': month.strftime('%Y-%m'), 'summary': adj_imp.summarise(plan),
                        'rows': adj_imp.public(plan)}
        if str(request.data.get('dry_run', '')).lower() in ('1', 'true', 'yes'):
            return success('Preview ready. Nothing has been saved yet.', data())

        bad = adj_imp.summarise(plan)[adj_imp.ERROR]
        if bad:
            return error(f'{bad} of {len(plan)} row(s) have errors. Nothing was imported — fix them and '
                         'upload the file again.', data=data())
        imported = adj_imp.apply(plan, month=month, user=request.user)
        log_change(request, 'payroll_adjustments_imported', '', None, {
            'month': month.strftime('%Y-%m'), 'imported': imported,
            'employees': sorted({r['employee_code'] for r in plan if r['status'] == 'created'}),
        })
        logger.info('Bulk import: %d adjustments created for month %s by %s', imported, month, request.user.email)
        return success(f'{imported} adjustment(s) imported.', {'imported': imported, 'row_errors': [], **data()},
                       http_status=201)


class PayrollAdjustmentImportSampleView(_SampleMixin, APIView):
    """GET ?format=csv|xlsx — template for the adjustments import."""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        if not _has_perm(request.user, 'payroll.edit'):
            return error('Only HR admin can bulk-import adjustments.', http_status=403)
        return self.sample_response(request, adj_imp.HEADERS, adj_imp.SAMPLE_ROWS,
                                    'Adjustments', 'payroll_adjustments_import_sample')
