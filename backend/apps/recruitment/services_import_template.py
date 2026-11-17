"""The candidate bulk-import sample files, filled in from the company's own data.

The Excel sample gets real drop-down lists (Position Applied, Company Code, Interview Mode) so people pick instead of typing.
A CSV file cannot hold drop-downs, so the CSV keeps its plain layout, with example rows that use real values.
"""
import io

from apps.accounts.models import Position
from apps.branch.models import Branch

from .models import Candidate

HEADERS = [
    'Candidate Name', 'Email', 'Mobile Number', 'Position Applied',
    'Company Code', 'Interview Date', 'Interview Mode', 'Notes',
]
SHEET_NAME = 'Candidate Import'
LISTS_SHEET_NAME = 'Lists'
# Drop-downs cover this many data rows (the importer accepts at most 1000).
DROPDOWN_LAST_ROW = 1001

# column letter in the sample -> (heading on the Lists sheet, column letter on the Lists sheet)
_DROPDOWNS = {'D': ('Positions', 'A'), 'E': ('Company Codes', 'B'), 'G': ('Interview Modes', 'C')}


def position_titles() -> list:
    """Every active position's title, once each (several seats can share a title), A to Z."""
    titles = {title.strip() for title in Position.objects.filter(is_active=True).values_list('title', flat=True) if title and title.strip()}
    return sorted(titles, key=str.lower)


def branch_names() -> list:
    """Active Company Code names, A to Z. The importer accepts either the name or the code."""
    names = Branch.objects.filter(status='active').values_list('branch_name', flat=True)
    return sorted({name.strip() for name in names if name and name.strip()}, key=str.lower)


def mode_labels() -> list:
    return [label for _value, label in Candidate.MODE_CHOICES]


def sample_rows(positions: list, branches: list, modes: list) -> list:
    """Two example rows built from real values, so a row copied as-is is valid. Empty cells where the company has no data yet."""
    def pick(options: list, index: int) -> str:
        return options[index % len(options)] if options else ''
    return [
        ['Rahul Sharma', 'rahul.sharma@email.com', '9876543210', pick(positions, 0), pick(branches, 0), '2026-07-25', pick(modes, 0), ''],
        ['Priya Patel', 'priya.patel@email.com', '9123456789', pick(positions, 1), pick(branches, 1), '2026-07-26', pick(modes, 1), 'Strong candidate'],
    ]


def build_import_sample_csv() -> bytes:
    from core.file_utils import build_sample_csv
    return build_sample_csv(HEADERS, sample_rows(position_titles(), branch_names(), mode_labels()))


def build_import_sample_xlsx() -> bytes:
    """The sample workbook: the sheet people fill in (first, so it is what the importer reads) plus a Lists sheet feeding the drop-downs."""
    import openpyxl
    from openpyxl.styles import Alignment, Font, PatternFill
    from openpyxl.utils import get_column_letter
    from openpyxl.worksheet.datavalidation import DataValidation

    positions, branches, modes = position_titles(), branch_names(), mode_labels()
    workbook = openpyxl.Workbook()
    sheet = workbook.active
    sheet.title = SHEET_NAME
    lists = workbook.create_sheet(LISTS_SHEET_NAME)

    header_style = dict(font=Font(bold=True, color='FFFFFF'), fill=PatternFill(fill_type='solid', fgColor='4472C4'), alignment=Alignment(horizontal='center'))
    for column, text in enumerate(HEADERS, 1):
        cell = sheet.cell(row=1, column=column, value=text)
        cell.font, cell.fill, cell.alignment = header_style['font'], header_style['fill'], header_style['alignment']
        sheet.column_dimensions[get_column_letter(column)].width = max(len(text) + 6, 18)
    sheet.column_dimensions['D'].width = 32
    sheet.column_dimensions['E'].width = 26
    for row_index, row in enumerate(sample_rows(positions, branches, modes), 2):
        for column, value in enumerate(row, 1):
            sheet.cell(row=row_index, column=column, value=value)
    sheet.freeze_panes = 'A2'

    values = {'A': positions, 'B': branches, 'C': modes}
    for letter, options in values.items():
        heading = next(name for name, target in _DROPDOWNS.values() if target == letter)
        lists[f'{letter}1'] = heading
        lists[f'{letter}1'].font = Font(bold=True)
        for offset, option in enumerate(options, 2):
            lists[f'{letter}{offset}'] = option
        lists.column_dimensions[letter].width = 34

    for sample_letter, (_heading, list_letter) in _DROPDOWNS.items():
        options = values[list_letter]
        if not options:
            continue  # nothing to offer yet: leave the column free-text rather than an empty list
        validation = DataValidation(
            type='list', formula1=f"='{LISTS_SHEET_NAME}'!${list_letter}$2:${list_letter}${len(options) + 1}",
            allow_blank=True, showDropDown=False,  # openpyxl: False means "show the arrow"
        )
        # A warning, not a hard stop: a position that is not in the list yet can still be typed (the importer accepts any text).
        validation.errorStyle = 'warning'
        validation.errorTitle = 'Not in the list'
        validation.error = 'This value is not in the list. Keep it anyway?'
        validation.promptTitle = 'Pick from the list'
        validation.prompt = 'Click the arrow to choose.'
        validation.showErrorMessage = True
        validation.showInputMessage = True
        validation.add(f'{sample_letter}2:{sample_letter}{DROPDOWN_LAST_ROW}')
        sheet.add_data_validation(validation)

    buffer = io.BytesIO()
    workbook.save(buffer)
    return buffer.getvalue()
