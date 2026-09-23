import base64
import csv
import io
import logging
import time
from datetime import date, timedelta
from decimal import Decimal, InvalidOperation
from typing import TYPE_CHECKING

from django.db import transaction
from django.db.models import Count, F, Q, Sum
from django.http import HttpResponse
from django.utils import timezone
from rest_framework import status
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView

from core.pagination import paginate, paginated_data
from core.permissions import has_perm as _has_perm
from core.responses import error, first_error, get_client_ip, success

from ..models import (
    APPROVAL_APPROVED, APPROVAL_REJECTED,
    CARRY_FORWARD_UNLIMITED, CARRY_FORWARD_MANUAL,
    DURATION_FULL,
    LEAVE_LWP, LEAVE_TYPE_CHOICES,
    REQ_APPROVED, REQ_CANCELLED, REQ_L2_PENDING, REQ_PENDING, REQ_REJECTED,
    CarryForwardLog, LeaveBalance, LeavePolicy, LeaveRequest,
)
from ..serializers import (
    CarryForwardInputSerializer,
    CarryForwardLogSerializer,
    LeaveBalanceSerializer,
    LeavePolicyCreateSerializer,
    LeavePolicySerializer,
    LeavePolicyUpdateSerializer,
    LeaveRequestCreateSerializer,
    LeaveRequestSerializer,
)

if TYPE_CHECKING:
    from apps.accounts.models import User

logger = logging.getLogger(__name__)

from apps.hrms.views.leave_shared import *  # noqa: F401,F403

# ─── Leave Opening Balance Import ─────────────────────────────────────────────

_LEAVE_IMPORT_BATCH_SIZE    = 500
_LEAVE_IMPORT_MAX_BYTES     = 5 * 1024 * 1024  # 5 MB

_LEAVE_IMPORT_COL_MAP = {
    'employee id': 'employee_id',         'employee_id': 'employee_id',
    'employee code': 'employee_id',       'employee_code': 'employee_id',
    'emp id': 'employee_id',              'emp_id': 'employee_id',
    'emp code': 'employee_id',            'emp_code': 'employee_id',
    'leave type': 'leave_type',           'leave_type': 'leave_type',
    'financial year': 'financial_year',   'financial_year': 'financial_year',
    'fy': 'financial_year',               'year': 'financial_year',
    'fy year': 'financial_year',
    'opening balance': 'opening_balance', 'opening_balance': 'opening_balance',
    'opening': 'opening_balance',
    'leave allocated': 'allocated',       'leave_allocated': 'allocated',
    'allocated': 'allocated',             'allocation': 'allocated',
    'leave availed': 'availed',           'leave_availed': 'availed',
    'availed': 'availed',                 'used': 'availed',
    'used days': 'availed',               'leaves used': 'availed',
    'carry forward': 'carry_forward',         'carry_forward': 'carry_forward',
    'carry forward days': 'carry_forward',    'carry_forward_days': 'carry_forward',
    'cf days': 'carry_forward',               'cf_days': 'carry_forward',
    'carried forward': 'carry_forward',       'carried_forward': 'carry_forward',
    'leave balance': 'balance',           'leave_balance': 'balance',
    'balance': 'balance',                 'closing balance': 'balance',
    'lop days': 'lop_days',               'lop_days': 'lop_days',
    'lop': 'lop_days',
    # History row date columns
    'from date': 'from_date',             'from_date': 'from_date',
    'start date': 'from_date',            'start_date': 'from_date',
    'leave from': 'from_date',            'leave from date': 'from_date',
    'to date': 'to_date',                 'to_date': 'to_date',
    'end date': 'to_date',                'end_date': 'to_date',
    'leave to': 'to_date',                'leave to date': 'to_date',
    'total days': 'days',                 'total_days': 'days',
    'days': 'days',                       'no of days': 'days',
    'leave days': 'days',                 'no. of days': 'days',
    'duration': 'days',
    'remarks': 'remarks',                 'notes': 'remarks',
    'comments': 'remarks',
}

_LEAVE_IMPORT_SAMPLE_HEADERS = [
    'Employee ID', 'Leave Type', 'Financial Year',
    'Opening Balance', 'Leave Allocated', 'Leave Availed',
    'Leave Balance', 'Carry Forward Days',
    'From Date', 'To Date', 'Total Days',
    'Remarks',
]

_LEAVE_IMPORT_SAMPLE_ROWS = [
    # Balance rows — set annual opening numbers (leave From Date / To Date empty)
    ['RSS00001', 'Casual Leave', 'FY 2026-27', '6',  '6',  '2', '10', '0', '', '', '', 'Opening migration'],
    ['RSS00001', 'Earned Leave', 'FY 2026-27', '15', '15', '5', '30', '5', '', '', '', ''],
    ['RSS00002', 'Casual Leave', 'FY 2026-27', '6',  '6',  '0', '12', '0', '', '', '', ''],
    # History rows — individual leave dates (leave balance columns empty)
    ['RSS00001', 'Casual Leave', 'FY 2026-27', '', '', '', '', '', '05-Apr-2025', '06-Apr-2025', '2', 'Annual leave'],
    ['RSS00001', 'Casual Leave', 'FY 2026-27', '', '', '', '', '', '15-May-2025', '15-May-2025', '1', ''],
]
























# ── Leave history import helpers ───────────────────────────────────────────────



















class LeaveOpeningBalanceImportView(APIView):
    """POST /api/leave/balance/import/ — bulk import opening leave balances (migration tool)."""
    permission_classes = [IsAuthenticated]
    parser_classes     = [MultiPartParser, FormParser]

    def post(self, request):
        if not _has_perm(request.user, 'leave.approve'):
            return error('Only System Admin, HR Admin, and HR can import leave balances.', http_status=status.HTTP_403_FORBIDDEN)

        uploaded = request.FILES.get('file')
        if not uploaded:
            return error('Attach a CSV or XLSX file as "file".')
        if uploaded.size > _LEAVE_IMPORT_MAX_BYTES:
            return error('File must not exceed 5 MB.')

        fname = uploaded.name.lower()
        if fname.endswith('.xlsx'):
            rows, parse_err = _parse_leave_import_xlsx(uploaded)
        elif fname.endswith('.csv'):
            rows, parse_err = _parse_leave_import_csv(uploaded)
        else:
            return error('Unsupported file type. Upload a .csv or .xlsx file.')
        if parse_err:
            return error(parse_err)
        if not rows:
            return error('The file contains no data rows.')

        normalized = _normalize_and_index_rows(rows)
        emp_ids = {r.get('employee_id', '') for r in normalized} - {''}
        emp_map, valid_lt, existing_balances = _load_leave_ref_data(emp_ids)
        existing_requests = _load_existing_requests(emp_map)

        balance_rows = [r for r in normalized if not _is_history_row(r)]
        history_rows  = [r for r in normalized if _is_history_row(r)]

        start_ts = time.monotonic()
        bal_to_create, bal_errors, bal_fail, bal_skip = _validate_leave_rows(balance_rows, emp_map, valid_lt, existing_balances)
        req_to_create, req_errors, req_fail, req_skip = _validate_leave_history_rows(history_rows, emp_map, valid_lt, existing_requests)

        all_errors = bal_errors + req_errors
        fail_count = bal_fail + req_fail
        skip_count = bal_skip + req_skip

        bal_created, bal_batch_err = _bulk_insert_leave_balances(bal_to_create)
        req_created, req_batch_err = _bulk_insert_leave_requests(req_to_create)
        fail_count += bal_batch_err + req_batch_err

        if bal_created > 0:
            from django.core.cache import cache as _cache
            _cache.delete_many(list({
                f'dashboard:employee:leave_balance:{lb.employee_id}:{lb.year}'
                for lb in bal_to_create
            }))

        from apps.accounts.models import AuditLog
        AuditLog.objects.create(
            user=request.user, action='leave_opening_balance_import', module='leave',
            changes={
                'file': uploaded.name, 'total': len(rows),
                'balances_created': bal_created, 'history_imported': req_created,
                'failed': fail_count, 'skipped': skip_count,
            },
            ip_address=get_client_ip(request),
        )
        logger.info(
            'Leave import by %s: %d balances / %d history / %d failed / %d skipped (%.1fs)',
            request.user.email, bal_created, req_created, fail_count, skip_count,
            time.monotonic() - start_ts,
        )

        result = {
            'total_records':    len(rows),
            'balances_created': bal_created,
            'history_imported': req_created,
            'successful':       bal_created + req_created,
            'failed':           fail_count,
            'skipped':          skip_count,
            'errors':           all_errors[:100],
            'error_report_csv': _build_leave_error_csv(all_errors) if all_errors else None,
        }
        return success('Leave import completed.', result)


class LeaveOpeningBalanceSampleView(APIView):
    """GET /api/leave/balance/import/sample/?format=csv|xlsx — download import template."""
    permission_classes = [IsAuthenticated]

    def perform_content_negotiation(self, request, force=False):
        # ?format= selects csv/xlsx file type, not DRF response renderer.
        # Bypass DRF's renderer filtering to prevent Http404 on unknown formats.
        from rest_framework.renderers import JSONRenderer
        return (JSONRenderer(), 'application/json')

    def get(self, request):
        if not _has_perm(request.user, 'leave.approve'):
            return error('Only System Admin, HR Admin, and HR can download the leave balance import template.', http_status=status.HTTP_403_FORBIDDEN)

        from core.file_utils import _CSV_MIME, _XLSX_MIME, build_sample_csv, build_sample_xlsx
        fmt = (request.query_params.get('format') or 'csv').lower().strip()
        if fmt == 'xlsx':
            content  = build_sample_xlsx(_LEAVE_IMPORT_SAMPLE_HEADERS, _LEAVE_IMPORT_SAMPLE_ROWS, 'Leave Opening Balance')
            filename = 'leave_opening_balance_sample.xlsx'
            mime     = _XLSX_MIME
        else:
            content  = build_sample_csv(_LEAVE_IMPORT_SAMPLE_HEADERS, _LEAVE_IMPORT_SAMPLE_ROWS)
            filename = 'leave_opening_balance_sample.csv'
            mime     = _CSV_MIME

        response = HttpResponse(content, content_type=mime)
        response['Content-Disposition'] = f'attachment; filename="{filename}"'
        return response


class LeaveOpeningBalanceValidateView(APIView):
    """POST /api/leave/balance/import/validate/ — validate file and return row-by-row preview without saving."""
    permission_classes = [IsAuthenticated]
    parser_classes     = [MultiPartParser, FormParser]

    def post(self, request):
        if not _has_perm(request.user, 'leave.approve'):
            return error('Only System Admin, HR Admin, and HR can validate import files.', http_status=status.HTTP_403_FORBIDDEN)

        uploaded = request.FILES.get('file')
        if not uploaded:
            return error('Attach a CSV or XLSX file as "file".')
        if uploaded.size > _LEAVE_IMPORT_MAX_BYTES:
            return error('File must not exceed 5 MB.')

        rows, parse_err = _parse_and_validate_file(uploaded)
        if parse_err:
            return error(parse_err)
        if not rows:
            return error('The file contains no data rows.')

        normalized = _normalize_and_index_rows(rows)
        emp_ids = {r.get('employee_id', '') for r in normalized} - {''}
        emp_map, valid_lt, existing_balances = _load_leave_ref_data(emp_ids)
        existing_requests = _load_existing_requests(emp_map)

        balance_rows = [r for r in normalized if not _is_history_row(r)]
        history_rows  = [r for r in normalized if _is_history_row(r)]

        _, bal_errors, _, _ = _validate_leave_rows(balance_rows, emp_map, valid_lt, existing_balances)
        _, req_errors, _, _ = _validate_leave_history_rows(history_rows, emp_map, valid_lt, existing_requests)

        error_by_row = {e['row']: e for e in (bal_errors + req_errors)}

        preview = []
        for row in normalized:
            row_num = row['__row__']
            is_hist = _is_history_row(row)
            err     = error_by_row.get(row_num)
            preview.append({
                'row':            row_num,
                'row_type':       'history' if is_hist else 'balance',
                'employee_id':    row.get('employee_id', ''),
                'leave_type':     row.get('leave_type', ''),
                'financial_year': row.get('financial_year', ''),
                'from_date':      row.get('from_date') or None,
                'to_date':        row.get('to_date') or None,
                'days':           row.get('days') or None,
                'valid':          err is None,
                'error':          err['reason'] if err else None,
            })

        valid_count = sum(1 for p in preview if p['valid'])
        return success('File validated.', {
            'total_rows':   len(rows),
            'valid_rows':   valid_count,
            'error_rows':   len(rows) - valid_count,
            'balance_rows': len(balance_rows),
            'history_rows': len(history_rows),
            'preview':      preview,
        })
