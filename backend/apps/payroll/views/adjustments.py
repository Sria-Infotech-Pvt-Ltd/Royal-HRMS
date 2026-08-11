import logging
from datetime import date
from decimal import Decimal, InvalidOperation

from django.db import transaction
from django.db.models import Q, Sum
from django.shortcuts import get_object_or_404
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated

from core.responses import success, error, first_error
from core.pagination import paginate, paginated_data
from core.permissions import has_perm as _has_perm
from apps.payroll.models import PayrollAdjustment
from apps.payroll.serializers import PayrollAdjustmentSerializer
from apps.accounts.models import User

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
        adjustment = serializer.save(created_by=request.user)
        logger.info('PayrollAdjustment %s created by %s', adjustment.id, request.user.email)
        return success('Adjustment added.', PayrollAdjustmentSerializer(adjustment).data, http_status=201)


class PayrollAdjustmentDeleteView(APIView):
    """DELETE /payroll/adjustments/<pk>/"""
    permission_classes = [IsAuthenticated]

    def delete(self, request, pk):
        if not _has_perm(request.user, 'payroll.edit'):
            return error('Only HR admin can delete payroll adjustments.', http_status=403)
        adjustment = get_object_or_404(PayrollAdjustment, pk=pk)
        adjustment.delete()
        logger.info('PayrollAdjustment %s deleted by %s', pk, request.user.email)
        return success('Adjustment deleted.')


class PayrollAdjustmentBulkImportView(APIView):
    """
    POST /payroll/adjustments/bulk-import/
    Accepts an Excel file with columns:
      employee_code, type (addition/deduction/arrear), label, amount
    Query param: ?month=2026-07
    """
    permission_classes = [IsAuthenticated]

    def post(self, request):
        if not _has_perm(request.user, 'payroll.edit'):
            return error('Only HR admin can bulk-import adjustments.', http_status=403)

        month = _parse_month(request.query_params.get('month') or request.data.get('month'))
        if not month:
            return error('month query parameter is required (e.g. ?month=2026-07).')

        uploaded = request.FILES.get('file')
        if not uploaded:
            return error('No file uploaded. Send the Excel file as multipart field "file".')

        # Validate file type
        name = uploaded.name.lower()
        if not (name.endswith('.xlsx') or name.endswith('.xls') or name.endswith('.csv')):
            return error('Only .xlsx, .xls, or .csv files are accepted.')

        try:
            rows = _parse_file(uploaded)
        except Exception as exc:
            logger.exception('Bulk import parse error')
            return error(f'Could not read file: {exc}')

        if not rows:
            return error('The file appears to be empty or has no data rows.')

        errors = []
        valid_rows = []

        for idx, row in enumerate(rows, start=2):  # row 1 = header
            code   = str(row.get('employee_code', '')).strip()
            rtype  = str(row.get('type', '')).strip().lower()
            label  = str(row.get('label', '')).strip()
            amount_raw = str(row.get('amount', '')).strip()

            if not code:
                errors.append({'row': idx, 'error': 'employee_code is missing'})
                continue
            if rtype not in _ALLOWED_TYPES:
                errors.append({'row': idx, 'error': f'type must be addition, deduction, or arrear (got "{rtype}")'})
                continue
            if not label:
                errors.append({'row': idx, 'error': 'label is missing'})
                continue
            try:
                amount = Decimal(amount_raw)
                if amount <= 0:
                    raise ValueError
            except (InvalidOperation, ValueError):
                errors.append({'row': idx, 'error': f'amount must be a positive number (got "{amount_raw}")'})
                continue

            try:
                employee = User.objects.get(employee_id__iexact=code, is_active=True)
            except User.DoesNotExist:
                errors.append({'row': idx, 'error': f'No active employee found with code "{code}"'})
                continue
            except User.MultipleObjectsReturned:
                errors.append({'row': idx, 'error': f'Multiple employees matched code "{code}"'})
                continue

            valid_rows.append({
                'employee': employee,
                'month': month,
                'type': rtype,
                'label': label,
                'amount': amount,
                'created_by': request.user,
            })

        if errors and not valid_rows:
            return error('All rows failed validation.', {'row_errors': errors})

        with transaction.atomic():
            created = PayrollAdjustment.objects.bulk_create([
                PayrollAdjustment(**r) for r in valid_rows
            ])

        logger.info(
            'Bulk import: %d adjustments created for month %s by %s (%d rows had errors)',
            len(created), month, request.user.email, len(errors),
        )
        return success(
            f'{len(created)} adjustment(s) imported successfully.',
            {'imported': len(created), 'row_errors': errors},
            http_status=201,
        )


def _parse_file(uploaded_file) -> list[dict]:
    """Parse .xlsx/.xls/.csv into a list of dicts keyed by header row."""
    name = uploaded_file.name.lower()
    if name.endswith('.csv'):
        import csv, io
        text = uploaded_file.read().decode('utf-8-sig')
        reader = csv.DictReader(io.StringIO(text))
        return [_normalise_keys(row) for row in reader]
    else:
        try:
            import openpyxl
            wb = openpyxl.load_workbook(uploaded_file, read_only=True, data_only=True)
            ws = wb.active
            rows = list(ws.iter_rows(values_only=True))
        except Exception:
            import xlrd
            wb = xlrd.open_workbook(file_contents=uploaded_file.read())
            ws = wb.sheet_by_index(0)
            rows = [ws.row_values(i) for i in range(ws.nrows)]

        if not rows:
            return []
        headers = [str(h).strip().lower().replace(' ', '_') if h else '' for h in rows[0]]
        result = []
        for row in rows[1:]:
            if all(cell is None or str(cell).strip() == '' for cell in row):
                continue
            result.append({headers[i]: (row[i] if i < len(row) else '') for i in range(len(headers))})
        return result


def _normalise_keys(row: dict) -> dict:
    return {k.strip().lower().replace(' ', '_'): v for k, v in row.items()}
