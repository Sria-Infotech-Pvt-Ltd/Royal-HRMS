"""
Settings → Notice Period → Import: bulk-update existing employees' notice periods.

  POST /api/employees/notice-period/import/          multipart: file (.csv/.xlsx), dry_run=true for the preview
  GET  /api/employees/notice-period/import/sample/?format=csv|xlsx

Columns: Employee ID, Notice Period (days). Same permission (employees.edit),
scope (Managers: direct reports; others without settings.edit: own branch)
and audit entry as saving one employee on the Notice Period page. Employees
are matched by Employee ID only. A blank notice period skips the row — it
never clears a value. Duplicate IDs, unknown / out-of-scope IDs, inactive
employees and invalid values are row errors; the confirm request re-reads the
file and validates everything again before saving. The employee import
(create-only) is unchanged.
"""
from __future__ import annotations

import logging

from django.db import transaction
from django.db.models.functions import Upper
from django.http import HttpResponse
from rest_framework import status
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView

from apps.accounts.models import AuditLog, User
from apps.accounts.notice_period import parse_notice_period_days
from apps.accounts.views import (
    _EMP_MAX_IMPORT_BYTES, _EMP_MAX_IMPORT_ROWS, _employee_out_of_branch_scope,
    _parse_employee_csv_rows, _parse_employee_xlsx_rows,
)
from core.file_utils import _CSV_MIME, _XLSX_MIME, build_sample_csv, build_sample_xlsx
from core.permissions import has_perm as _has_perm
from core.responses import error, get_client_ip, success

logger = logging.getLogger(__name__)

_NO_PERMISSION = 'You do not have permission to change notice periods.'

HEADERS = ['Employee ID', 'Notice Period (days)']
SAMPLE_ROWS = [['EMP001', '30'], ['EMP002', '60'], ['EMP003', '90']]

_COLUMNS = {
    'employee id': 'employee_id', 'employee_id': 'employee_id', 'emp id': 'employee_id',
    'employee code': 'employee_id',
    'notice period (days)': 'notice', 'notice period': 'notice', 'notice_period': 'notice',
    'notice period days': 'notice', 'notice_period_days': 'notice', 'notice days': 'notice',
}

UPDATE, NO_CHANGE, SKIPPED, ERROR = 'update', 'no_change', 'skipped', 'error'


def _read_rows(uploaded) -> tuple[list[dict] | None, str | None]:
    """Same file checks and parsers as the employee import."""
    if uploaded.size > _EMP_MAX_IMPORT_BYTES:
        return None, 'File too large. Maximum allowed size is 5 MB.'
    name = (uploaded.name or '').lower()
    if name.endswith('.xlsx'):
        rows, parse_error = _parse_employee_xlsx_rows(uploaded)
    elif name.endswith('.csv'):
        rows, parse_error = _parse_employee_csv_rows(uploaded)
    else:
        return None, 'Unsupported file format. Please upload a CSV or XLSX file.'
    if parse_error:
        return None, parse_error
    if not rows:
        return None, 'The file contains no data rows.'
    if len(rows) > _EMP_MAX_IMPORT_ROWS:
        return None, f'File contains {len(rows)} rows. Maximum allowed per import is {_EMP_MAX_IMPORT_ROWS}.'
    normalized = [{_COLUMNS[k.strip().lower()]: (v or '').strip()
                   for k, v in row.items() if k and k.strip().lower() in _COLUMNS} for row in rows]
    if not any('employee_id' in r for r in normalized):
        return None, 'The file needs an "Employee ID" column.'
    if not any('notice' in r for r in normalized):
        return None, 'The file needs a "Notice Period (days)" column.'
    return normalized, None


def plan_rows(rows: list[dict], requester) -> list[dict]:
    """One result per row; 'employee' (internal) is set on update rows."""
    keys = [(r.get('employee_id') or '').upper() for r in rows]
    counts = {k: keys.count(k) for k in keys if k}
    # One query, matched case-insensitively ("dem00027" finds DEM00027).
    employees = {
        u.employee_id.upper(): u
        for u in User.objects.select_related('role').annotate(code_upper=Upper('employee_id'))
        .filter(code_upper__in=[k for k in keys if k])
    }

    plan = []
    for idx, row in enumerate(rows, start=2):
        code = row.get('employee_id') or ''
        out = {'row': idx, 'employee_id': code, 'name': '', 'current': None, 'new': None, 'status': ERROR, 'message': ''}
        plan.append(out)
        if not code:
            out['message'] = 'Employee ID is required.'
            continue
        if counts.get(code.upper(), 0) > 1:
            out['message'] = 'This Employee ID appears more than once in the file.'
            continue
        emp = employees.get(code.upper())
        if emp is None or _employee_out_of_branch_scope(requester, emp):
            out['message'] = 'Employee not found.'
            continue
        out.update(employee_id=emp.employee_id, name=emp.full_name, current=emp.notice_period_days)
        if not emp.is_active:
            out['message'] = 'Employee is inactive.'
            continue
        raw = row.get('notice', '')
        if not raw:
            out.update(status=SKIPPED, message='Blank notice period — left unchanged.')
            continue
        err, days = parse_notice_period_days(raw)
        if err:
            out['message'] = err
            continue
        out['new'] = days
        if days == emp.notice_period_days:
            out.update(status=NO_CHANGE, message='No change.')
            continue
        out.update(status=UPDATE, message='Will be updated.', employee=emp)
    return plan


def _summary(plan) -> dict:
    return {s: sum(1 for p in plan if p['status'] == s) for s in (UPDATE, NO_CHANGE, SKIPPED, ERROR)} | {'total': len(plan)}


def _public(plan) -> list[dict]:
    return [{k: v for k, v in p.items() if k != 'employee'} for p in plan]


class NoticePeriodImportView(APIView):
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser]

    def post(self, request):
        if not _has_perm(request.user, 'employees.edit'):
            return error(_NO_PERMISSION, http_status=status.HTTP_403_FORBIDDEN)
        uploaded = request.FILES.get('file')
        if not uploaded:
            return error('Attach a CSV or Excel (.xlsx) file.')
        rows, problem = _read_rows(uploaded)
        if problem:
            return error(problem)
        # The confirm request re-uploads the file, so it is validated afresh here.
        plan = plan_rows(rows, request.user)

        if str(request.data.get('dry_run', '')).lower() in ('1', 'true', 'yes'):
            return success('Preview ready. Nothing has been saved yet.',
                           {'summary': _summary(plan), 'rows': _public(plan)})

        ip = get_client_ip(request)
        updated = 0
        for p in plan:
            if p['status'] != UPDATE:
                continue
            emp = p['employee']
            with transaction.atomic():
                emp.notice_period_days = p['new']
                emp.save(update_fields=['notice_period_days', 'updated_at'])
                # Same entry as saving one employee (EmployeeDetailView.put).
                AuditLog.objects.create(
                    user=request.user, action='employee_updated', module='employees', object_id=str(emp.id),
                    changes={'employee_id': emp.employee_id, 'full_name': emp.full_name,
                             'notice_period_days': {'from': p['current'], 'to': p['new']},
                             'source': 'notice_period_import'},
                    branch=emp.branch, ip_address=ip,
                )
            p['status'], p['message'] = 'updated', 'Updated.'
            updated += 1
        summary = _summary(plan) | {'updated': updated}
        logger.info('Notice period import by %s: %s', request.user.email, summary)
        return success(f'{updated} notice period(s) updated.', {'summary': summary, 'rows': _public(plan)})


class NoticePeriodImportSampleView(APIView):
    permission_classes = [IsAuthenticated]

    def perform_content_negotiation(self, request, force=False):
        # ?format= picks csv/xlsx, not a DRF renderer (same as the other sample downloads).
        from rest_framework.renderers import JSONRenderer
        return (JSONRenderer(), 'application/json')

    def get(self, request):
        if not _has_perm(request.user, 'employees.edit'):
            return error(_NO_PERMISSION, http_status=status.HTTP_403_FORBIDDEN)
        if (request.query_params.get('format') or 'csv').lower().strip() == 'xlsx':
            content = build_sample_xlsx(HEADERS, SAMPLE_ROWS, 'Notice Period')
            filename, mime = 'notice_period_import_sample.xlsx', _XLSX_MIME
        else:
            content, filename, mime = build_sample_csv(HEADERS, SAMPLE_ROWS), 'notice_period_import_sample.csv', _CSV_MIME
        response = HttpResponse(content, content_type=mime)
        response['Content-Disposition'] = f'attachment; filename="{filename}"'
        return response
