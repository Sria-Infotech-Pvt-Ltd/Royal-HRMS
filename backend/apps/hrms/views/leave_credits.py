"""
Employee-wise leave credit management (Phase 1) — Employee Profile → Leave tab.

  GET  /api/leave/credits/<employee_id>/?year=&leave_type=      yearly + monthly summary and history
  POST /api/leave/credits/<employee_id>/adjust/                  signed adjustment
  POST /api/leave/credits/<employee_id>/transactions/<id>/reverse/  compensating reversal

Access: leave.approve plus _can_manage_leave_credits (no self, managers →
direct reports only, branch-restricted users → own branch).
"""
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView

from core.permissions import has_perm as _has_perm
from core.responses import error, get_client_ip, success

from ..models import LEAVE_LWP, LeavePolicy
from ..services_leave_credit import (
    LeaveCreditConflict, LeaveCreditError,
    apply_adjustment, current_calendar_year, leave_type_label, monthly_summary,
    reverse_transaction, serialize_transaction, transaction_history, yearly_summary,
)
from .leave import _can_manage_leave_credits


def _resolve_employee(request, employee_id: str):
    if not _has_perm(request.user, 'leave.approve'):
        return None, error('Permission denied.', http_status=status.HTTP_403_FORBIDDEN)
    from apps.accounts.models import User
    employee = User.objects.filter(employee_id=employee_id).exclude(employee_id='').first()
    if employee is None or not _can_manage_leave_credits(request.user, employee):
        return None, error('Employee not found.', http_status=status.HTTP_404_NOT_FOUND)
    return employee, None


def _credit_error(exc: LeaveCreditError):
    code = status.HTTP_409_CONFLICT if isinstance(exc, LeaveCreditConflict) else status.HTTP_400_BAD_REQUEST
    return error(str(exc), http_status=code)


class LeaveCreditOverviewView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, employee_id: str):
        employee, err = _resolve_employee(request, employee_id)
        if err:
            return err
        try:
            year = int(request.query_params.get('year') or current_calendar_year())
        except (TypeError, ValueError):
            return error('year must be a valid integer.')

        summaries = yearly_summary(employee, year)
        leave_type = (request.query_params.get('leave_type') or '').strip()
        if not leave_type and summaries:
            leave_type = summaries[0]['leave_type']

        assignable = [
            {'value': p.leave_type, 'label': leave_type_label(p.leave_type, p)}
            for p in LeavePolicy.objects.filter(is_active=True).exclude(leave_type=LEAVE_LWP).order_by('leave_type')
        ]
        return success('Leave credits retrieved.', {
            'employee':               {'employee_id': employee.employee_id, 'full_name': employee.full_name},
            'year':                   year,
            'current_year':           current_calendar_year(),
            'summaries':              summaries,
            'leave_type':             leave_type or None,
            'monthly':                monthly_summary(employee, leave_type, year) if leave_type else None,
            'transactions':           transaction_history(employee, year, leave_type or None),
            'assignable_leave_types': assignable,
        })


class LeaveCreditAdjustView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, employee_id: str):
        employee, err = _resolve_employee(request, employee_id)
        if err:
            return err
        data = request.data
        try:
            txn, created = apply_adjustment(
                employee=employee, leave_type=data.get('leave_type'), year=data.get('year'),
                amount=data.get('amount'), reason=data.get('reason'), actor=request.user,
                idempotency_key=data.get('idempotency_key'), ip_address=get_client_ip(request),
            )
        except LeaveCreditError as exc:
            return _credit_error(exc)
        return success(
            'Leave credits adjusted.' if created else 'This adjustment was already applied.',
            {'transaction': serialize_transaction(txn), 'duplicate': not created},
            http_status=status.HTTP_201_CREATED if created else status.HTTP_200_OK,
        )


class LeaveCreditReverseView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, employee_id: str, txn_id):
        employee, err = _resolve_employee(request, employee_id)
        if err:
            return err
        try:
            txn, created = reverse_transaction(
                employee=employee, txn_id=txn_id, reason=request.data.get('reason'),
                actor=request.user, idempotency_key=request.data.get('idempotency_key'),
                ip_address=get_client_ip(request),
            )
        except LeaveCreditError as exc:
            return _credit_error(exc)
        return success(
            'Adjustment reversed.' if created else 'This reversal was already applied.',
            {'transaction': serialize_transaction(txn), 'duplicate': not created},
            http_status=status.HTTP_201_CREATED if created else status.HTTP_200_OK,
        )


# ─── Monthly Leave Management (Settings → Leave Management) ──────────────────
#
#   GET  /api/leave/monthly-credits/?employee_id=&year=&month=   current monthly credits + balances
#   POST /api/leave/monthly-credits/                              add / update one monthly credit
#   POST /api/leave/monthly-credits/import/                       preview (dry_run=true) or import
#   GET  /api/leave/monthly-credits/import/sample/?format=csv|xlsx
#
# Same access as Leave Credits: leave.approve, plus per-employee scope.

_IMPORT_LOCK_SECONDS = 600


def _year_month(data):
    from ..services_leave_credit import _clean_year, clean_month
    return _clean_year(data.get('year')), clean_month(data.get('month'))


def _monthly_rows(employee, year: int, month: int) -> list[dict]:
    from ..models import LeaveBalance
    from ..services_leave_credit import monthly_credit_value, pending_days
    balances = {b.leave_type: b for b in LeaveBalance.objects.filter(employee=employee, year=year)}
    rows = []
    for p in LeavePolicy.objects.filter(is_active=True).exclude(leave_type=LEAVE_LWP).order_by('leave_type'):
        b = balances.get(p.leave_type)
        pending = pending_days(employee, p.leave_type, year) if b else 0
        rows.append({
            'leave_type':       p.leave_type,
            'leave_type_label': leave_type_label(p.leave_type, p),
            'annual_days':      float(p.annual_days),
            'monthly_credit':   float(monthly_credit_value(employee, p.leave_type, year, month)),
            'balance': {
                'total':     float(b.total_days),
                'used':      float(b.used_days),
                'pending':   float(pending),
                'available': float(b.total_days - b.used_days),
            } if b else None,
        })
    return rows


class MonthlyLeaveCreditView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        employee, err = _resolve_employee(request, (request.query_params.get('employee_id') or '').strip())
        if err:
            return err
        try:
            year, month = _year_month(request.query_params)
        except LeaveCreditError as exc:
            return _credit_error(exc)
        return success('Monthly leave credits retrieved.', {
            'employee': {'employee_id': employee.employee_id, 'full_name': employee.full_name},
            'year': year, 'month': month, 'leave_types': _monthly_rows(employee, year, month),
        })

    def post(self, request):
        from ..services_leave_credit import set_monthly_credit
        employee, err = _resolve_employee(request, (request.data.get('employee_id') or '').strip())
        if err:
            return err
        try:
            year, month = _year_month(request.data)
            result = set_monthly_credit(
                employee=employee, leave_type=request.data.get('leave_type'), year=year, month=month,
                value=request.data.get('credit'), actor=request.user, source='manual',
                ip_address=get_client_ip(request),
            )
        except LeaveCreditError as exc:
            return _credit_error(exc)
        messages = {
            'created':   'Monthly leave credit added.',
            'updated':   'Monthly leave credit updated.',
            'unchanged': 'No change: the monthly credit already has this value.',
        }
        return success(messages[result['status']], {
            'status':      result['status'],
            'previous':    float(result['previous']),
            'value':       float(result['value']),
            'delta':       float(result['delta']),
            'leave_types': _monthly_rows(employee, year, month),
        })


class MonthlyLeaveImportView(APIView):
    """multipart: file (.csv/.xlsx), year, month, dry_run=true for the preview."""
    permission_classes = [IsAuthenticated]

    def post(self, request):
        from django.core.cache import cache
        from ..services_monthly_leave import apply_import, normalize_rows, plan_import, strip_internal
        from .leave import _LEAVE_IMPORT_MAX_BYTES, _parse_leave_import_csv, _parse_leave_import_xlsx

        if not _has_perm(request.user, 'leave.approve'):
            return error('Permission denied.', http_status=status.HTTP_403_FORBIDDEN)
        try:
            year, month = _year_month(request.data)
        except LeaveCreditError as exc:
            return _credit_error(exc)
        uploaded = request.FILES.get('file')
        if not uploaded:
            return error('Attach a CSV or Excel (.xlsx) file.')
        if uploaded.size > _LEAVE_IMPORT_MAX_BYTES:
            return error('File must not exceed 5 MB.')
        name = uploaded.name.lower()
        if name.endswith('.xlsx'):
            raw_rows, parse_err = _parse_leave_import_xlsx(uploaded)
        elif name.endswith('.csv'):
            raw_rows, parse_err = _parse_leave_import_csv(uploaded)
        else:
            return error('Unsupported file type. Upload a .csv or .xlsx file.')
        if parse_err:
            return error(parse_err)
        rows, norm_err = normalize_rows(raw_rows)
        if norm_err:
            return error(norm_err)

        dry_run = str(request.data.get('dry_run', '')).lower() in ('1', 'true', 'yes')
        if dry_run:
            plan = plan_import(rows, actor=request.user, year=year, month=month)
            return success('Preview ready. Nothing has been saved yet.', strip_internal(plan))

        # One import per month at a time (cache keys are tenant-scoped); each row
        # is also protected by the balance-row lock in set_monthly_credit().
        lock_key = f'leave:monthly_import:{year}:{month}'
        if not cache.add(lock_key, str(request.user.pk), _IMPORT_LOCK_SECONDS):
            return error('Another import for this month is in progress. Try again in a moment.',
                         http_status=status.HTTP_409_CONFLICT)
        try:
            plan = plan_import(rows, actor=request.user, year=year, month=month)
            result = apply_import(plan, actor=request.user, ip_address=get_client_ip(request))
        finally:
            cache.delete(lock_key)
        summary = result['summary']
        return success(
            f"Import finished: {summary['created']} added, {summary['updated']} updated, "
            f"{summary['skipped']} skipped, {summary['failed']} failed.",
            result,
        )


class MonthlyLeaveImportSampleView(APIView):
    permission_classes = [IsAuthenticated]

    def perform_content_negotiation(self, request, force=False):
        # ?format= picks the file type, not a DRF renderer (same as the opening-balance sample).
        from rest_framework.renderers import JSONRenderer
        return (JSONRenderer(), 'application/json')

    def get(self, request):
        from django.http import HttpResponse
        from core.file_utils import _CSV_MIME, _XLSX_MIME, build_sample_csv, build_sample_xlsx
        from ..services_monthly_leave import SAMPLE_HEADERS, SAMPLE_ROWS

        if not _has_perm(request.user, 'leave.approve'):
            return error('Permission denied.', http_status=status.HTTP_403_FORBIDDEN)
        if (request.query_params.get('format') or 'csv').lower().strip() == 'xlsx':
            content = build_sample_xlsx(SAMPLE_HEADERS, SAMPLE_ROWS, 'Monthly Leave')
            filename, mime = 'monthly_leave_credit_sample.xlsx', _XLSX_MIME
        else:
            content = build_sample_csv(SAMPLE_HEADERS, SAMPLE_ROWS)
            filename, mime = 'monthly_leave_credit_sample.csv', _CSV_MIME
        response = HttpResponse(content, content_type=mime)
        response['Content-Disposition'] = f'attachment; filename="{filename}"'
        return response
