"""
Phase 7B Task J follow-up — proves generate_ecr_text_via_template()
reproduces the real apps.payroll.views.ecr output byte-for-byte, and
matches its hard-fail-on-missing-UAN behavior exactly.
"""
import datetime
from decimal import Decimal

from django.core.management import call_command
from django.test import TestCase

from apps.accounts.factories import make_role, make_user
from apps.accounts.models import EmployeeProfile
from apps.payroll.models import EmployeePayslip, PayrollCycle, PayrollSettings, StatutoryFileTemplate
from apps.payroll.services_ecr_template import MissingUanError, generate_ecr_text_via_template
from apps.payroll.views.ecr import _build_ecr_text, _compute_ecr_rows, _ecr_filename


def _make_employee_with_uan(uan='101234567890', aadhar_name='Real Aadhar Name'):
    role = make_role(f'ecr_role_{uan}')
    employee = make_user(f'ecr.{uan}@example.com', role=role, password='TestPass123!')
    EmployeeProfile.objects.create(user=employee, uan_number=uan, name_as_per_aadhar=aadhar_name)
    return employee


def _make_cycle(creator):
    return PayrollCycle.objects.create(
        cycle_start=datetime.date(2026, 3, 25), cycle_end=datetime.date(2026, 4, 24),
        pay_date=datetime.date(2026, 4, 30), created_by=creator,
    )


def _make_payslip(employee, cycle, **overrides):
    defaults = dict(
        annual_ctc=Decimal('600000'), monthly_ctc=Decimal('50000'),
        basic=Decimal('20000'), hra=Decimal('10000'), special_allowance=Decimal('20000'),
        gross_earnings=Decimal('50000'), total_working_days=26, lop_days=Decimal('0'),
        lop_deduction=Decimal('0'), pf_wage_base=Decimal('15000'),
        pf_employee=Decimal('1800'), pf_employer=Decimal('1800'),
    )
    defaults.update(overrides)
    return EmployeePayslip.objects.create(cycle=cycle, employee=employee, **defaults)


class EcrByteIdentityTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command('seed_statutory_file_templates')
        PayrollSettings.objects.get_or_create(defaults={})

    def test_generated_content_matches_real_generator_byte_for_byte(self):
        creator = _make_employee_with_uan('900000000001')
        employee = _make_employee_with_uan('900000000002')
        cycle = _make_cycle(creator)
        _make_payslip(employee, cycle)

        template = StatutoryFileTemplate.objects.get(code='ECR_TEXT_V1')
        generated = generate_ecr_text_via_template(template, cycle, generated_by=creator)

        settings_row = PayrollSettings.objects.first()
        expected_content = _build_ecr_text(_compute_ecr_rows(cycle, settings_row))

        self.assertEqual(generated.content, expected_content)
        self.assertEqual(generated.file_name, _ecr_filename(cycle, 'txt'))
        self.assertIn('#~#', generated.content)
        self.assertTrue(generated.content.endswith('#~#'))  # trailing delimiter, no file-level trailing \r\n (join adds none after the last line)

    def test_row_format_has_trailing_delimiter_and_crlf(self):
        creator = _make_employee_with_uan('900000000003')
        employee = _make_employee_with_uan('900000000004')
        cycle = _make_cycle(creator)
        _make_payslip(employee, cycle)

        template = StatutoryFileTemplate.objects.get(code='ECR_TEXT_V1')
        generated = generate_ecr_text_via_template(template, cycle, generated_by=creator)

        lines = generated.content.split('\r\n')
        data_lines = [l for l in lines if l]
        self.assertTrue(all(l.endswith('#~#') for l in data_lines))
        self.assertNotIn('\n\n', generated.content.replace('\r\n', ''))  # no bare \n row separators

    def test_missing_uan_fails_the_whole_file(self):
        creator = _make_employee_with_uan('900000000005')
        role = make_role('ecr_no_uan_role')
        employee_without_uan = make_user('ecr.nouan@example.com', role=role, password='TestPass123!')
        EmployeeProfile.objects.create(user=employee_without_uan, uan_number='')
        cycle = _make_cycle(creator)
        _make_payslip(employee_without_uan, cycle)

        template = StatutoryFileTemplate.objects.get(code='ECR_TEXT_V1')
        with self.assertRaises(MissingUanError):
            generate_ecr_text_via_template(template, cycle, generated_by=creator)

    def test_name_falls_back_to_full_name_when_aadhar_name_missing(self):
        creator = _make_employee_with_uan('900000000006')
        role = make_role('ecr_fallback_role')
        employee = make_user('ecr.fallback@example.com', role=role, password='TestPass123!', full_name='Fallback Name')
        EmployeeProfile.objects.create(user=employee, uan_number='900000000007', name_as_per_aadhar='')
        cycle = _make_cycle(creator)
        _make_payslip(employee, cycle)

        template = StatutoryFileTemplate.objects.get(code='ECR_TEXT_V1')
        generated = generate_ecr_text_via_template(template, cycle, generated_by=creator)
        self.assertIn('Fallback Name', generated.content)
