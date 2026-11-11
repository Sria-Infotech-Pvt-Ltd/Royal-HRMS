"""
The Excel files of the bulk employee import: the downloadable template, and the error report.

The template has three sheets: Employees (the one to fill in), Instructions, and Lists (the values behind the dropdowns).
It never contains passwords, keys, bank/PAN/Aadhaar details or face data. The error report repeats only the non-sensitive
columns of the rows that were uploaded, plus one "Import Errors" column.
"""
from __future__ import annotations

import io

from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.datavalidation import DataValidation

from apps.accounts.employment_types import VALID_EMPLOYMENT_TYPES
from django.db.models import Q
from django.utils import timezone

from apps.accounts.models import EmployeeProfile, Placement, Position
from apps.accounts.services_employee_import import COLUMNS, EMPLOYEES_SHEET, RowResult, allowed_branches

XLSX_CONTENT_TYPE = 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
VALIDATION_ROWS = 500
HEADER_FILL = PatternFill('solid', fgColor='4F46E5')
REQUIRED_FILL = PatternFill('solid', fgColor='B91C1C')
ERROR_FILL = PatternFill('solid', fgColor='FEE2E2')
# A spreadsheet cell beginning with one of these is executed as a formula by Excel; never write user text that way.
_FORMULA_PREFIXES = ('=', '+', '-', '@', '\t', '\r')


def safe_cell(value) -> str:
    text = '' if value is None else str(value)
    if text and text[0] in _FORMULA_PREFIXES and not _looks_like_plain_number(text):
        return "'" + text
    return text


def _looks_like_plain_number(text: str) -> bool:
    try:
        float(text.replace('+', '', 1) if text.startswith('+') else text)
        return True
    except ValueError:
        return False


def _header_row(sheet, columns) -> None:
    for index, column in enumerate(columns, start=1):
        cell = sheet.cell(row=1, column=index, value=column.header + (' *' if column.required else ''))
        cell.font = Font(bold=True, color='FFFFFF')
        cell.fill = REQUIRED_FILL if column.required else HEADER_FILL
        cell.alignment = Alignment(wrap_text=True, vertical='center')
        sheet.column_dimensions[get_column_letter(index)].width = max(18, len(column.header) + 6)
    sheet.freeze_panes = 'A2'


def _lists_sheet(workbook, importer):
    """Lists sheet: branches the importer may use, org units, org-unit/position pairs, and fixed choices."""
    sheet = workbook.create_sheet('Lists')
    branches = [b.branch_code or b.branch_name for b in allowed_branches(importer)]
    # Vacant = no placement that is still open today. (Excluding on `placements__effective_to__isnull=True` is wrong: for a seat
    # nobody has ever held it matches the missing placement too, so every never-filled seat would be hidden.)
    still_held = Placement.objects.filter(Q(effective_to__isnull=True) | Q(effective_to__gte=timezone.localdate())).values('position_id')
    positions = list(Position.objects.filter(is_active=True).exclude(pk__in=still_held).select_related('org_unit').order_by('org_unit__name', 'title'))
    units = sorted({p.org_unit.name for p in positions})
    lists = {
        'Company Code': branches, 'Org Unit': units, 'Employment Type': list(VALID_EMPLOYMENT_TYPES),
        'Gender': ['Male', 'Female', 'Other'], 'Blood Group': [value for value, _l in EmployeeProfile.BLOOD_CHOICES],
    }
    positions_column = len(lists) + 2
    ranges = {}
    for index, (title, values) in enumerate(lists.items(), start=1):
        sheet.cell(row=1, column=index, value=title).font = Font(bold=True)
        for offset, value in enumerate(values, start=2):
            sheet.cell(row=offset, column=index, value=safe_cell(value))
        letter = get_column_letter(index)
        ranges[title] = f"Lists!${letter}$2:${letter}${max(len(values), 1) + 1}"
    sheet.cell(row=1, column=positions_column, value='Org Unit').font = Font(bold=True)
    sheet.cell(row=1, column=positions_column + 1, value='Position').font = Font(bold=True)
    for offset, position in enumerate(positions, start=2):
        sheet.cell(row=offset, column=positions_column, value=safe_cell(position.org_unit.name))
        sheet.cell(row=offset, column=positions_column + 1, value=safe_cell(position.title))
    for index in range(1, positions_column + 2):
        sheet.column_dimensions[get_column_letter(index)].width = 26
    return sheet, ranges


def _add_dropdown(sheet, column_index: int, source: str, message: str) -> None:
    letter = get_column_letter(column_index)
    validation = DataValidation(type='list', formula1=f'={source}', allow_blank=True, showErrorMessage=True,
                                errorTitle='Not in the list', error=message)
    sheet.add_data_validation(validation)
    validation.add(f'{letter}2:{letter}{VALIDATION_ROWS + 1}')


def _instructions_sheet(workbook, importer) -> None:
    sheet = workbook.create_sheet('Instructions')
    lines = [
        ('How to import employees', True),
        ('1. Fill in the Employees sheet, one employee per row. Columns marked * are required.', False),
        ('2. Write every date as YYYY-MM-DD, for example 2026-11-10. Format date cells as Text so Excel does not change them.', False),
        ('3. Pick Company Code, Org Unit, Employment Type, Gender and Blood Group from the dropdowns. Position must be a title that exists in that org unit (see the Lists sheet).', False),
        ('4. Upload the file in Employees > Bulk Import. You will see a preview first. Nothing is created until you confirm.', False),
        ('5. If any row has an error, nothing is imported. Download the error file, fix the rows, and upload again.', False),
        ('6. After a successful import every employee gets an activation email to set their own password. Never put passwords in this file.', False),
        ('7. Do not add bank, PAN, Aadhaar, UAN or salary details here. They are collected through onboarding.', False),
        ('8. Employee IDs are generated automatically. Do not add an Employee ID column.', False),
        ('', False),
        ('Your branch access', True),
        ('Branches you may import into: ' + (', '.join(b.branch_name for b in allowed_branches(importer)) or 'none'), False),
        ('The server checks this again on upload. Changing the dropdown cells in the file does not give you access to other branches.', False),
        ('', False),
        ('Columns', True),
    ]
    for column in COLUMNS:
        lines.append((f"{column.header}{' (required)' if column.required else ''}: {column.description} Example: {column.example}", False))
    for row, (text, is_title) in enumerate(lines, start=1):
        cell = sheet.cell(row=row, column=1, value=text)
        cell.alignment = Alignment(wrap_text=True, vertical='top')
        if is_title:
            cell.font = Font(bold=True, size=13)
    sheet.column_dimensions['A'].width = 120


def build_template(importer) -> bytes:
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = EMPLOYEES_SHEET
    _header_row(sheet, COLUMNS)
    # Everything is Text so dates and phone numbers keep their written form.
    for row in sheet.iter_rows(min_row=2, max_row=VALIDATION_ROWS + 1, max_col=len(COLUMNS)):
        for cell in row:
            cell.number_format = '@'
    _lists_sheet_obj, ranges = _lists_sheet(workbook, importer)
    by_key = {column.key: index for index, column in enumerate(COLUMNS, start=1)}
    _add_dropdown(sheet, by_key['branch'], ranges['Company Code'], 'Choose one of the branches in the list.')
    _add_dropdown(sheet, by_key['org_unit'], ranges['Org Unit'], 'Choose an org unit from the list.')
    _add_dropdown(sheet, by_key['employee_type'], ranges['Employment Type'], 'Choose an employment type from the list.')
    _add_dropdown(sheet, by_key['gender'], ranges['Gender'], 'Choose Male, Female or Other.')
    _add_dropdown(sheet, by_key['blood_group'], ranges['Blood Group'], 'Choose a blood group from the list.')
    _instructions_sheet(workbook, importer)
    workbook.move_sheet('Instructions', offset=-1)
    buffer = io.BytesIO()
    workbook.save(buffer)
    return buffer.getvalue()


def build_error_report(results: list[RowResult]) -> bytes:
    """The uploaded rows (non-sensitive columns only) that need fixing, each with its errors; valid rows are left out."""
    columns = [column for column in COLUMNS if column.is_core]
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = 'Import Errors'
    _header_row(sheet, columns)
    error_column = len(columns) + 1
    sheet.cell(row=1, column=error_column, value='Import Errors').font = Font(bold=True, color='FFFFFF')
    sheet.cell(row=1, column=error_column).fill = REQUIRED_FILL
    sheet.column_dimensions[get_column_letter(error_column)].width = 90
    sheet.cell(row=1, column=error_column + 1, value='Original Row').font = Font(bold=True)
    out_row = 2
    for result in results:
        if result.is_valid:
            continue
        for index, column in enumerate(columns, start=1):
            sheet.cell(row=out_row, column=index, value=safe_cell(result.values.get(column.key, '')))
        error_cell = sheet.cell(row=out_row, column=error_column, value=safe_cell('; '.join(result.errors)))
        error_cell.fill = ERROR_FILL
        error_cell.alignment = Alignment(wrap_text=True, vertical='top')
        sheet.cell(row=out_row, column=error_column + 1, value=result.row)
        out_row += 1
    buffer = io.BytesIO()
    workbook.save(buffer)
    return buffer.getvalue()
