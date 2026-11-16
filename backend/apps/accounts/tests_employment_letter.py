"""The employment verification letter PDF: professional layout, real data only, and no "not on record" filler."""
from __future__ import annotations

import datetime
import struct
import zlib
from io import BytesIO
from types import SimpleNamespace
from unittest import mock

from django.core.cache import cache
from django.test import TestCase
from pypdf import PdfReader

from apps.accounts.factories import make_role, make_user
from apps.accounts.models import Company
from apps.accounts.services_employment_letter import (
    _company_letterhead_lines, _read_logo, letter_detail_rows, letter_reference, render_employment_letter_pdf, signatory_for,
)


def tiny_png() -> bytes:
    """A valid 1x1 PNG, built by hand so the test needs no image library."""
    def chunk(kind: bytes, data: bytes) -> bytes:
        body = kind + data
        return struct.pack('>I', len(data)) + body + struct.pack('>I', zlib.crc32(body) & 0xFFFFFFFF)
    header = struct.pack('>IIBBBBB', 1, 1, 8, 2, 0, 0, 0)
    signature = bytes([0x89]) + b'PNG' + bytes([0x0D, 0x0A, 0x1A, 0x0A])
    pixel = bytes([0x00, 0xFF, 0xFF, 0xFF])   # filter byte + one white RGB pixel
    return signature + chunk(b'IHDR', header) + chunk(b'IDAT', zlib.compress(pixel)) + chunk(b'IEND', b'')


class FakeLogo:
    """A stand-in for Company.logo: `remote=True` behaves like ImageKit storage, which cannot be opened (no file is ever stored)."""

    def __init__(self, url: str = '', content: bytes = b'', remote: bool = False):
        self.url, self._content, self._remote = url, content, remote

    def __bool__(self) -> bool:
        return True

    def open(self, mode: str = 'rb'):
        if self._remote:
            raise NotImplementedError('ImageKitStorage does not support reading files back into Django - use .url() to fetch them.')
        return BytesIO(self._content)


class FakeResponse:
    def __init__(self, content: bytes):
        self.content = content

    def raise_for_status(self) -> None:
        return None


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

    def test_the_letterhead_and_signature_come_from_the_company_settings(self):
        self.company.primary_email = 'hr@acme.test'
        self.company.cin = 'U12345TG2020PTC000001'
        self.company.signatory_full_name = 'Ravi Kumar'
        self.company.signatory_designation = 'Director'
        self.company.save()
        text = pdf_text(render_employment_letter_pdf(self.employee))
        for expected in ('hr@acme.test', 'CIN: U12345TG2020PTC000001', 'Ravi Kumar', 'Director'):
            self.assertIn(expected, text)
        self.assertNotIn('HR Operations', text)

    def test_without_a_configured_signatory_the_letter_is_signed_by_hr_operations(self):
        signatory = signatory_for(self.company)
        self.assertEqual((signatory.name, signatory.designation), ('Authorised Signatory', 'HR Operations'))
        self.company.signatory_full_name = 'Ravi Kumar'
        self.assertEqual(signatory_for(self.company).designation, 'Authorised Signatory')

    def test_a_logo_on_remote_storage_is_fetched_from_its_url(self):
        logo = FakeLogo(url='https://cdn.example.test/company/logo.png', remote=True)
        with mock.patch('apps.accounts.services_employment_letter.requests.get', return_value=FakeResponse(tiny_png())) as get:
            self.assertEqual(_read_logo(SimpleNamespace(logo=logo)), tiny_png())
        get.assert_called_once()
        self.assertEqual(get.call_args.args[0], 'https://cdn.example.test/company/logo.png')

    def test_a_logo_on_local_storage_is_read_directly(self):
        self.assertEqual(_read_logo(SimpleNamespace(logo=FakeLogo(content=tiny_png()))), tiny_png())

    def test_a_logo_that_cannot_be_fetched_or_is_not_an_image_is_skipped(self):
        remote = FakeLogo(url='https://cdn.example.test/company/logo.png', remote=True)
        with mock.patch('apps.accounts.services_employment_letter.requests.get', side_effect=OSError('offline')):
            self.assertIsNone(_read_logo(SimpleNamespace(logo=remote)))
        with mock.patch('apps.accounts.services_employment_letter.requests.get', return_value=FakeResponse(b'not an image')):
            self.assertIsNone(_read_logo(SimpleNamespace(logo=remote)))
        self.assertIsNone(_read_logo(None))

    def test_the_letter_is_issued_with_a_logo_and_without_one(self):
        with mock.patch('apps.accounts.services_employment_letter._read_logo', return_value=tiny_png()):
            self.assertTrue(render_employment_letter_pdf(self.employee).startswith(b'%PDF'))
        with mock.patch('apps.accounts.services_employment_letter._read_logo', return_value=None):
            self.assertTrue(render_employment_letter_pdf(self.employee).startswith(b'%PDF'))

    def test_the_letter_is_still_issued_when_no_company_is_configured(self):
        Company.objects.all().delete()
        self.assertIn('This company', pdf_text(render_employment_letter_pdf(self.employee)))
