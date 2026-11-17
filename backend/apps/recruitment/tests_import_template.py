"""The candidate import sample files: real drop-downs in the Excel one, real example values in both (no database needed)."""
import io
from unittest import mock

import openpyxl
from django.test import SimpleTestCase

from apps.recruitment import services_import_template as svc

PATCH = 'apps.recruitment.services_import_template.'


def build(positions, branches):
    with mock.patch(PATCH + 'position_titles', return_value=positions), mock.patch(PATCH + 'branch_names', return_value=branches):
        return openpyxl.load_workbook(io.BytesIO(svc.build_import_sample_xlsx()))


class ImportSampleXlsxTests(SimpleTestCase):
    def test_the_sheet_people_fill_in_comes_first_so_the_importer_reads_it(self):
        workbook = build(['Engineer'], ['Hyderabad'])
        self.assertEqual(workbook.sheetnames, [svc.SHEET_NAME, svc.LISTS_SHEET_NAME])
        self.assertEqual(workbook.active.title, svc.SHEET_NAME)
        self.assertEqual([cell.value for cell in workbook.active[1]], svc.HEADERS)

    def test_position_company_code_and_mode_get_dropdowns_over_every_row_the_importer_accepts(self):
        sheet = build(['Engineer', 'Recruiter'], ['Hyderabad']).active
        ranges = {str(validation.sqref): validation.formula1 for validation in sheet.data_validations.dataValidation}
        self.assertEqual(set(ranges), {f'D2:D{svc.DROPDOWN_LAST_ROW}', f'E2:E{svc.DROPDOWN_LAST_ROW}', f'G2:G{svc.DROPDOWN_LAST_ROW}'})
        self.assertIn("'Lists'!$A$2:$A$3", ranges[f'D2:D{svc.DROPDOWN_LAST_ROW}'])

    def test_the_lists_sheet_holds_the_companys_own_values(self):
        lists = build(['Engineer', 'Recruiter'], ['Hyderabad', 'Pune'])[svc.LISTS_SHEET_NAME]
        self.assertEqual([lists[f'A{row}'].value for row in (1, 2, 3)], ['Positions', 'Engineer', 'Recruiter'])
        self.assertEqual([lists[f'B{row}'].value for row in (1, 2, 3)], ['Company Codes', 'Hyderabad', 'Pune'])
        self.assertEqual([lists[f'C{row}'].value for row in (2, 3, 4)], ['In-Person', 'Video Call', 'Phone'])

    def test_a_typed_value_outside_the_list_only_warns_because_a_new_position_may_not_be_listed_yet(self):
        sheet = build(['Engineer'], ['Hyderabad']).active
        for validation in sheet.data_validations.dataValidation:
            self.assertEqual(validation.errorStyle, 'warning')

    def test_a_column_with_nothing_to_offer_is_left_free_text_instead_of_an_empty_list(self):
        sheet = build([], []).active
        self.assertEqual([str(validation.sqref) for validation in sheet.data_validations.dataValidation], [f'G2:G{svc.DROPDOWN_LAST_ROW}'])


class ImportSampleRowsTests(SimpleTestCase):
    def test_example_rows_use_real_values_and_valid_modes(self):
        rows = svc.sample_rows(['Engineer', 'Recruiter'], ['Hyderabad', 'Pune'], svc.mode_labels())
        self.assertEqual([rows[0][3], rows[0][4]], ['Engineer', 'Hyderabad'])
        self.assertEqual([rows[1][3], rows[1][4]], ['Recruiter', 'Pune'])
        self.assertEqual([rows[0][6], rows[1][6]], ['In-Person', 'Video Call'])

    def test_a_company_with_one_position_reuses_it_and_one_with_none_leaves_the_cell_empty(self):
        self.assertEqual(svc.sample_rows(['Engineer'], ['Pune'], ['Phone'])[1][3], 'Engineer')
        self.assertEqual(svc.sample_rows([], [], [])[0][3:5], ['', ''])

    def test_the_csv_has_the_same_headings_as_the_excel_file(self):
        with mock.patch(PATCH + 'position_titles', return_value=['Engineer']), mock.patch(PATCH + 'branch_names', return_value=['Pune']):
            first_line = svc.build_import_sample_csv().decode('utf-8-sig').splitlines()[0]
        self.assertEqual(first_line.split(','), svc.HEADERS)
