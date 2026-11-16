"""The employment verification letter PDF: professional layout, real data only, and no "not on record" filler."""
from __future__ import annotations

import datetime
from io import BytesIO

from django.core.cache import cache
from django.test import TestCase
from pypdf import PdfReader

from apps.accounts.factories import make_role, make_user
from apps.accounts.models import Company
from apps.accounts.services_employment_letter import (
    _company_letterhead_lines, letter_detail_rows, letter_reference, render_employment_letter_pdf,
)


def pdf_text(pdf: bytes) -> str:
    return '\n'.join(page.extract_text() for page in PdfReader(BytesIO(pdf)).pages)


class EmploymentLetterTests(TestCase):
    def setUp(self):
        cache.clear()
        Company.objects.all().delete()
        self.company = Company.objects.create(company_name='Acme Staffing', address='Hyderabad, Telangana', city='Hyderabad')
        self.employee = make_user(
            'letter-emp@test.com', role=make_role('letter_emp', permission_codenames=[]), employee_id='10000777', full_name='Asha Rao',
            designation='Lead', department='Engineering', branch='Kondapur', date_of_joining=datetime.date(2025, 3, 2),
        )

    def test_the_letter_is_a_single_page_pdf_with_the_real_details(self):
        pdf = render_employment_letter_pdf(self.employee)
        self.assertTrue(pdf.startswith(b'%PDF'))
        self.assertEqual(len(PdfReader(BytesIO(pdf)).pages), 1)
        text = pdf_text(pdf)
        for expected in ('Acme Staffing', 'EMPLOYMENT VERIFICATION LETTER', 'Asha Rao', '10000777', 'Lead', 'Engineering', '02 March 2025',
                         'Kondapur', 'Authorised Signatory', 'Company seal / stamp', 'Ref: EVL/'):
            self.assertIn(expected, text)

    def test_a_missing_detail_is_left_out_instead_of_printed_as_not_on_record(self):
        self.employee.designation = ''
        self.employee.department = ''
        self.employee.date_of_joining = None
        self.employee.save()
        text = pdf_text(render_employment_letter_pdf(self.employee))
        self.assertNotIn('not on record', text.lower())
        self.assertNotIn('Designation', text)
        self.assertNotIn('Department', text)
        self.assertNotIn('Date of joining', text)
        self.assertIn('Asha Rao', text)

    def test_the_detail_rows_only_contain_what_the_record_holds(self):
        labels = [label for label, _value in letter_detail_rows(self.employee)]
        self.assertEqual(labels, ['Employee name', 'Employee ID', 'Designation', 'Department', 'Date of joining', 'Employment status', 'Work location'])
        self.employee.department = ''
        self.assertNotIn('Department', [label for label, _value in letter_detail_rows(self.employee)])

    def test_a_place_name_repeated_in_the_address_and_city_prints_once(self):
        self.assertEqual(_company_letterhead_lines(self.company)[0], 'Hyderabad, Telangana')

    def test_the_letterhead_includes_the_contact_line_only_when_there_is_one(self):
        self.assertEqual(len(_company_letterhead_lines(self.company)), 1)
        self.company.primary_email = 'hr@acme.test'
        self.company.official_phone = '040 1234 5678'
        self.assertEqual(_company_letterhead_lines(self.company)[1], '040 1234 5678 | hr@acme.test')

    def test_an_inactive_employee_is_described_as_no_longer_active(self):
        self.employee.is_active = False
        self.employee.save()
        text = pdf_text(render_employment_letter_pdf(self.employee)).replace('\n', ' ')
        self.assertIn('no longer an active employee', text)

    def test_the_reference_number_names_the_year_employee_and_date(self):
        self.assertEqual(letter_reference(self.employee, datetime.date(2026, 11, 16)), 'EVL/2026/10000777/161126')

    def test_the_letter_is_still_issued_when_no_company_is_configured(self):
        Company.objects.all().delete()
        self.assertIn('This company', pdf_text(render_employment_letter_pdf(self.employee)))
