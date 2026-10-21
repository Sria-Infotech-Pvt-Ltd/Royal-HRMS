"""
Bulk asset assignment (CSV / Excel) for Settings → Assets → Bulk Assign.

One row = one existing asset (Asset Tag) to one employee (Employee ID).
Every row is checked against the database and the uploader's scope, then
validated by the existing AssignAssetSerializer (same date / condition
rules as the single Assign Asset form). Confirmed rows are saved one at a
time through services_assignment.assign_asset — the same row lock, status
update, assignment-history row and audit entry as single assignment — so a
failed row never affects the others.

Nothing is ever reassigned: an asset that is already assigned is reported
as "already assigned" and left alone (return it first, then assign again).
Re-uploading the same file is therefore safe — rows assigned the first
time come back as "already assigned".

File reading, size / row limits and date formats are shared with the asset
master import (services_import).
"""
from __future__ import annotations

import base64
import csv
import io

from django.db.models.functions import Lower

from apps.accounts.models import User
from apps.assets.models import Asset, AssetAssignment
from apps.assets.services_import import MAX_ROWS, ImportFileError, _parse_date, _read_rows

# (header, field, required, notes)
COLUMNS = [
    ('Asset Tag',               'asset_tag',               True,  'An existing asset, e.g. AST-0101'),
    ('Employee ID',             'employee_id',             True,  'The employee\'s Employee ID, e.g. EMP0012'),
    ('Assigned Date',           'assigned_date',           True,  'YYYY-MM-DD or DD-MM-YYYY'),
    ('Condition at Assignment', 'condition_at_assignment', True,  'new, good, fair or damaged'),
    ('Expected Return Date',    'expected_return_date',    False, 'Not before the Assigned Date'),
    ('Remarks',                 'remarks',                 False, ''),
]
HEADERS = [c[0] for c in COLUMNS]
_FIELD_BY_HEADER = {c[0].lower(): c[1] for c in COLUMNS}
_HEADER_BY_FIELD = {c[1]: c[0] for c in COLUMNS}
_REQUIRED = [c[0] for c in COLUMNS if c[2]]
_CONDITIONS = {value: value for value, _ in Asset.CONDITION_CHOICES}
_CONDITIONS.update({label.lower(): value for value, label in Asset.CONDITION_CHOICES})

# Row statuses: ready → assigned on confirm; already_assigned and error are never saved.
READY, ASSIGNED, ALREADY, ERROR = 'ready', 'assigned', 'already_assigned', 'error'


def parse_file(uploaded) -> list[dict]:
    """[{'row': n, <field>: text, ...}] with n = spreadsheet row number. Raises ImportFileError."""
    raw = [r for r in _read_rows(uploaded) if any(c for c in r)]
    if not raw:
        raise ImportFileError('The file is empty.')
    headers = [h.strip() for h in raw[0]]
    unknown = [h for h in headers if h and h.lower() not in _FIELD_BY_HEADER]
    if unknown:
        raise ImportFileError(f'Unknown column(s): {", ".join(unknown)}. Use the sample template headers.')
    present = {h.lower() for h in headers if h}
    missing = [h for h in _REQUIRED if h.lower() not in present]
    if missing:
        raise ImportFileError(f'Missing required column(s): {", ".join(missing)}.')
    body = raw[1:]
    if not body:
        raise ImportFileError('The file has no data rows.')
    if len(body) > MAX_ROWS:
        raise ImportFileError(f'The file has {len(body)} rows; import at most {MAX_ROWS} at a time.')
    rows = []
    for offset, values in enumerate(body, start=2):
        row = {'row': offset}
        for i, header in enumerate(headers):
            if header:
                row[_FIELD_BY_HEADER[header.lower()]] = (values[i] if i < len(values) else '').strip()
        rows.append(row)
    return rows


# ─── Validation ───────────────────────────────────────────────────────────────

def _err(column: str, message: str) -> dict:
    return {'column': column, 'message': message}


def _group_by_lower(objects, attr):
    out: dict[str, list] = {}
    for obj in objects:
        out.setdefault(getattr(obj, attr).lower(), []).append(obj)
    return out


def _asset_for(tag: str, assets_by_tag: dict, *, is_admin: bool, user_branch):
    """(asset, error message). Assets outside the uploader's branch look the same as unknown ones."""
    matches = assets_by_tag.get(tag.lower(), [])
    if not is_admin:
        matches = [a for a in matches if user_branch is not None and a.branch_id == user_branch.pk]
    if not matches:
        where = '' if is_admin else ' in your branch'
        return None, f'No asset with Asset Tag "{tag}" found{where}.'
    if len(matches) > 1:
        return None, f'Asset Tag "{tag}" matches more than one asset; fix the Asset Tags first.'
    return matches[0], None


def _employee_for(code: str, employees_by_code: dict, *, user, is_admin: bool):
    """(employee, error message). Case-insensitive, but only when exactly one employee has that ID."""
    from apps.assets.views import _employee_out_of_scope

    matches = employees_by_code.get(code.lower(), [])
    if len(matches) > 1:
        return None, f'Employee ID "{code}" matches more than one employee; it can\'t be used to assign.'
    employee = matches[0] if matches else None
    if employee is None or (not is_admin and _employee_out_of_scope(user, employee)):
        return None, f'No employee with Employee ID "{code}" found.'
    if not employee.is_active:
        return None, 'This employee is inactive.'
    if employee.onboarding_status != User.ONBOARDING_COMPLETE:
        return None, 'This employee has not completed onboarding yet.'
    return employee, None


def _first_errors(errors: dict) -> list[dict]:
    out = []
    for field, messages in errors.items():
        message = messages[0] if isinstance(messages, list) and messages else messages
        out.append(_err(_HEADER_BY_FIELD.get(field, 'Asset Tag' if field == 'asset' else field), str(message)))
    return out


def plan_assignments(rows: list[dict], *, user, is_admin: bool, user_branch) -> dict:
    """Validate every row without saving. Status per row: ready / already_assigned / error."""
    from apps.assets.serializers import AssignAssetSerializer

    tag_counts: dict[str, int] = {}
    for row in rows:
        key = (row.get('asset_tag') or '').lower()
        if key:
            tag_counts[key] = tag_counts.get(key, 0) + 1
    # One query each for assets, employees and current holders — not one per row.
    codes = {(r.get('employee_id') or '').lower() for r in rows} - {''}
    assets_by_tag = _group_by_lower(
        Asset.objects.select_related('branch').annotate(tag_l=Lower('asset_tag')).filter(tag_l__in=list(tag_counts)),
        'asset_tag')
    employees_by_code = _group_by_lower(
        User.objects.select_related('role').exclude(employee_id='')
        .annotate(code_l=Lower('employee_id')).filter(code_l__in=list(codes)),
        'employee_id')
    holder_by_asset = dict(AssetAssignment.objects.filter(
        status=AssetAssignment.STATUS_ASSIGNED,
        asset__in=[a for group in assets_by_tag.values() for a in group],
    ).values_list('asset_id', 'employee_id'))

    planned = []
    for row in rows:
        tag, code = row.get('asset_tag') or '', row.get('employee_id') or ''
        out = {'row': row['row'], 'asset_tag': tag, 'asset_name': '', 'employee_id': code, 'employee_name': '',
               'status': ERROR, 'errors': [], '_data': None}
        planned.append(out)
        errors = out['errors']

        if not tag:
            errors.append(_err('Asset Tag', 'Asset Tag is required.'))
        elif tag_counts[tag.lower()] > 1:
            # Which row was meant is unclear, so none of them is used.
            errors.append(_err('Asset Tag', 'This Asset Tag appears in more than one row; list each asset once.'))
        if not code:
            errors.append(_err('Employee ID', 'Employee ID is required.'))

        dates = {}
        for field in ('assigned_date', 'expected_return_date'):
            text = row.get(field) or ''
            if not text:
                if field == 'assigned_date':
                    errors.append(_err('Assigned Date', 'Assigned Date is required.'))
                dates[field] = None
                continue
            parsed = _parse_date(text)
            if parsed is None:
                errors.append(_err(_HEADER_BY_FIELD[field], f'"{text}" is not a valid date (use YYYY-MM-DD).'))
            dates[field] = parsed
        condition_text = (row.get('condition_at_assignment') or '').lower()
        condition = _CONDITIONS.get(condition_text)
        if not condition_text:
            errors.append(_err('Condition at Assignment', 'Condition at Assignment is required.'))
        elif condition is None:
            errors.append(_err('Condition at Assignment',
                               f'"{row.get("condition_at_assignment")}" is not one of new, good, fair, damaged.'))

        asset = employee = None
        if tag and tag_counts[tag.lower()] == 1:
            asset, message = _asset_for(tag, assets_by_tag, is_admin=is_admin, user_branch=user_branch)
            if message:
                errors.append(_err('Asset Tag', message))
            else:
                out['asset_tag'], out['asset_name'] = asset.asset_tag, asset.asset_name
        if code:
            employee, message = _employee_for(code, employees_by_code, user=user, is_admin=is_admin)
            if message:
                errors.append(_err('Employee ID', message))
            else:
                out['employee_id'], out['employee_name'] = employee.employee_id, employee.full_name

        if asset is not None and asset.status == Asset.STATUS_ASSIGNED:
            if employee is not None and holder_by_asset.get(asset.pk) == employee.pk:
                note = 'Already assigned to this employee.'
            else:
                note = 'Already assigned to another employee. Return it first to reassign.'
            out['status'] = ALREADY if not errors else ERROR
            errors.insert(0, _err('Asset Tag', note))
            continue
        if asset is not None and asset.status != Asset.STATUS_AVAILABLE:
            errors.append(_err('Asset Tag', f'"{asset.asset_tag}" is not available — '
                                            f'current status: {asset.get_status_display()}.'))
        if errors:
            continue

        data = {
            'asset': str(asset.pk),
            'assigned_date': dates['assigned_date'].isoformat(),
            'condition_at_assignment': condition,
            'expected_return_date': dates['expected_return_date'].isoformat() if dates['expected_return_date'] else None,
            'remarks': row.get('remarks') or '',
        }
        serializer = AssignAssetSerializer(data=data)
        if not serializer.is_valid():
            errors.extend(_first_errors(serializer.errors))
            continue
        out['status'] = READY
        out['_data'] = {**serializer.validated_data, 'employee': employee}

    return {'rows': planned, 'counts': _counts(planned, (READY, ALREADY, ERROR))}


def _counts(rows, statuses):
    return {s: sum(1 for r in rows if r['status'] == s) for s in statuses}


def apply_assignments(plan: dict, *, user, ip_address=None) -> dict:
    """Assign every 'ready' row through the shared assign_asset (locks the asset; never reassigns)."""
    from apps.assets.services_assignment import AssetAssignConflict, AssetNotAvailable, assign_asset

    for row in plan['rows']:
        data = row.pop('_data', None)
        if row['status'] != READY:
            continue
        try:
            assign_asset(
                asset=data['asset'], employee=data['employee'],
                assigned_date=data['assigned_date'],
                condition_at_assignment=data['condition_at_assignment'],
                expected_return_date=data.get('expected_return_date'),
                remarks=data.get('remarks', ''),
                assigned_by=user, ip_address=ip_address, source='bulk_import',
            )
        except AssetAssignConflict:
            row['status'] = ALREADY
            row['errors'] = [_err('Asset Tag', 'Was just assigned by someone else; not reassigned.')]
            continue
        except AssetNotAvailable as exc:
            if exc.asset.status == Asset.STATUS_ASSIGNED:
                row['status'] = ALREADY
                row['errors'] = [_err('Asset Tag', 'Was just assigned by someone else; not reassigned.')]
            else:
                row['status'] = ERROR
                row['errors'] = [_err('Asset Tag', str(exc))]
            continue
        row['status'] = ASSIGNED
    counts = _counts(plan['rows'], (ASSIGNED, ALREADY, ERROR))
    summary = {'total': len(plan['rows']), 'assigned': counts[ASSIGNED],
               'already_assigned': counts[ALREADY], 'failed': counts[ERROR]}
    summary['skipped'] = summary['total'] - summary['assigned'] - summary['already_assigned'] - summary['failed']
    return {'rows': plan['rows'], 'summary': summary, 'error_report_csv': error_report_csv(plan['rows'])}


def strip_internal(plan: dict) -> dict:
    for row in plan['rows']:
        row.pop('_data', None)
    plan['error_report_csv'] = error_report_csv(plan['rows'])
    return plan


def _cell(value) -> str:
    text = str(value)
    return "'" + text if text[:1] in ('=', '+', '-', '@') else text   # no spreadsheet formulas


def error_report_csv(rows: list[dict]) -> str | None:
    """Base64 CSV of rows that weren't assigned (row, asset tag, employee id, column, reason) — no internal details."""
    problems = [r for r in rows if r['status'] in (ERROR, ALREADY)]
    if not problems:
        return None
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(['Row', 'Asset Tag', 'Employee ID', 'Status', 'Column', 'Reason'])
    for r in problems:
        status = 'already assigned' if r['status'] == ALREADY else 'error'
        for e in r['errors'] or [_err('', '')]:
            writer.writerow([r['row'], _cell(r['asset_tag']), _cell(r['employee_id']), status,
                             e['column'], _cell(e['message'])])
    return base64.b64encode(buf.getvalue().encode('utf-8-sig')).decode('ascii')


# ─── Sample templates ─────────────────────────────────────────────────────────

# Placeholders, not real records: a template must never assign a real asset by accident.
SAMPLE_ROWS = [
    ['EXAMPLE-AST-001', 'EXAMPLE-EMP-001', '2026-01-15', 'new', '2027-01-14', 'Example row: replace or delete'],
    ['EXAMPLE-AST-002', 'EXAMPLE-EMP-002', '2026-01-15', 'good', '', ''],
]


def sample_xlsx() -> bytes:
    import openpyxl
    from openpyxl.styles import Font

    from core.file_utils import build_sample_xlsx
    wb = openpyxl.load_workbook(io.BytesIO(build_sample_xlsx(HEADERS, SAMPLE_ROWS, 'Assignments')))
    info = wb.create_sheet('Instructions')
    info.append(['Column', 'Required', 'Notes'])
    for cell in info[1]:
        cell.font = Font(bold=True)
    for header, _field, required, notes in COLUMNS:
        info.append([header, 'Yes' if required else 'No', notes])
    info.append([])
    info.append(['Replace the EXAMPLE rows with real Asset Tags and Employee IDs. One asset per row; '
                 f'each asset at most once; up to {MAX_ROWS} rows per file.'])
    info.append(['Only Available assets can be assigned. Assets that are already assigned are reported, '
                 'never reassigned — return them first.'])
    info.column_dimensions['A'].width = 26
    info.column_dimensions['B'].width = 10
    info.column_dimensions['C'].width = 60
    out = io.BytesIO()
    wb.save(out)
    return out.getvalue()
