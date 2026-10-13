"""Phase 7A Task H — declared_investments key mapping, windows, proof submissions."""
import datetime
from decimal import Decimal

from django.core.management import call_command
from django.test import TestCase

from apps.accounts.factories import make_role, make_user
from apps.payroll.models import EmployeeTaxDeclaration, TaxDeclarationWindow, TaxProofSubmission
from apps.payroll.services_tax_declaration import map_declared_investments, report_unmapped_keys_across_all_declarations


class MapDeclaredInvestmentsTests(TestCase):
    def setUp(self):
        call_command('seed_tax_year_config')  # seeds the 4 TaxSection rows

    def test_exact_keys_match_cleanly(self):
        result = map_declared_investments({'80C': '150000', '80D': '20000', '80CCD1B': '50000', 'HRA': '60000'})
        self.assertEqual(result['unmapped'], {})
        self.assertEqual(result['matched']['80C'], Decimal('150000'))

    def test_alias_keys_are_recognised(self):
        result = map_declared_investments({'section80c': '100000', '80d': '15000'})
        self.assertEqual(result['matched']['80C'], Decimal('100000'))
        self.assertEqual(result['matched']['80D'], Decimal('15000'))
        self.assertEqual(result['unmapped'], {})

    def test_truly_unknown_key_is_reported(self):
        result = map_declared_investments({'80C': '100000', 'SOME_FUTURE_SECTION': '5000'})
        self.assertIn('SOME_FUTURE_SECTION', result['unmapped'])
        self.assertIn('80C', result['matched'])

    def test_empty_declaration_maps_to_nothing(self):
        result = map_declared_investments({})
        self.assertEqual(result, {'matched': {}, 'unmapped': {}})


class ReportUnmappedAcrossDeclarationsTests(TestCase):
    def setUp(self):
        call_command('seed_tax_year_config')
        self.role = make_role('tax_decl_role')

    def test_report_is_empty_when_everything_maps(self):
        employee = make_user('taxdecl.clean@example.com', role=self.role, password='TestPass123!')
        EmployeeTaxDeclaration.objects.create(
            employee=employee, financial_year_start=2026,
            tax_regime=EmployeeTaxDeclaration.REGIME_OLD, declared_investments={'80C': '100000'},
        )
        self.assertEqual(report_unmapped_keys_across_all_declarations(), {})

    def test_report_flags_unmapped_key(self):
        employee = make_user('taxdecl.dirty@example.com', role=self.role, password='TestPass123!')
        declaration = EmployeeTaxDeclaration.objects.create(
            employee=employee, financial_year_start=2026,
            tax_regime=EmployeeTaxDeclaration.REGIME_OLD, declared_investments={'WEIRD_KEY': '1000'},
        )
        report = report_unmapped_keys_across_all_declarations()
        self.assertIn(str(declaration.id), report)
        self.assertIn('WEIRD_KEY', report[str(declaration.id)]['unmapped'])


class WindowTests(TestCase):
    def test_declaration_and_proof_open_independently(self):
        window = TaxDeclarationWindow.objects.create(
            financial_year_start=2026,
            declaration_open_from=datetime.date(2026, 4, 1), declaration_open_to=datetime.date(2026, 6, 30),
            proof_open_from=datetime.date(2027, 1, 1), proof_open_to=datetime.date(2027, 2, 28),
        )
        self.assertTrue(window.declaration_is_open(datetime.date(2026, 5, 1)))
        self.assertFalse(window.proof_is_open(datetime.date(2026, 5, 1)))
        self.assertTrue(window.proof_is_open(datetime.date(2027, 1, 15)))
        self.assertFalse(window.declaration_is_open(datetime.date(2027, 1, 15)))

    def test_inactive_window_is_always_closed(self):
        window = TaxDeclarationWindow.objects.create(
            financial_year_start=2026, is_active=False,
            declaration_open_from=datetime.date(2026, 4, 1), declaration_open_to=datetime.date(2026, 6, 30),
            proof_open_from=datetime.date(2026, 4, 1), proof_open_to=datetime.date(2026, 6, 30),
        )
        self.assertFalse(window.declaration_is_open(datetime.date(2026, 5, 1)))


class ProofSubmissionTests(TestCase):
    def test_declared_and_approved_amount_can_differ(self):
        role = make_role('tax_proof_role')
        employee = make_user('taxproof.test@example.com', role=role, password='TestPass123!')
        declaration = EmployeeTaxDeclaration.objects.create(
            employee=employee, financial_year_start=2026,
            tax_regime=EmployeeTaxDeclaration.REGIME_OLD, declared_investments={'80C': '150000'},
        )
        proof = TaxProofSubmission.objects.create(
            declaration=declaration, section_code='80C',
            declared_amount=Decimal('150000'), approved_amount=Decimal('120000'),
            status=TaxProofSubmission.STATUS_APPROVED, remarks='Partial proof only.',
        )
        self.assertNotEqual(proof.declared_amount, proof.approved_amount)


# Tax declaration — validation of the declared items and the old-regime deductions they earn.
# Pure functions only, so these need no database.
from decimal import Decimal

from django.test import SimpleTestCase

from apps.payroll.services_income_tax import deduction_breakdown, estimate_monthly_tds
from apps.payroll.tax_declaration_schema import schema_payload
from apps.payroll.tax_declaration_validation import validate_declared_investments


def _rent(**overrides):
    base = {
        'monthly_rent': 20000, 'months': 12, 'metro': True,
        'landlord_name': 'A Landlord', 'landlord_address': '1 Main Road', 'landlord_relationship': 'none',
        'landlord_pan': 'ABCDE1234F',
    }
    base.update(overrides)
    return {'_details': {'hra': base}}


class ValidateDeclaredInvestmentsTests(SimpleTestCase):
    def test_accepts_itemised_declaration(self):
        validate_declared_investments({'80C_PPF': 50000, '80D_SELF_FAMILY': '12000', '24B': 0})

    def test_rejects_unknown_item_negative_and_non_numeric(self):
        for bad in ({'MADE_UP': 5}, {'80C_PPF': -1}, {'80C_PPF': 'abc'}, {'80C_PPF': 10 ** 12}):
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                validate_declared_investments(bad)

    def test_legacy_keys_still_accepted(self):
        validate_declared_investments({'80C': 150000, '80D': 25000, 'HRA': 60000})

    def test_rent_needs_landlord_name_and_address(self):
        for field in ('landlord_name', 'landlord_address'):
            with self.subTest(field=field), self.assertRaises(ValueError):
                validate_declared_investments(_rent(**{field: ''}))

    def test_landlord_pan_required_only_above_one_lakh_a_year(self):
        validate_declared_investments(_rent(monthly_rent=8000, landlord_pan=''))      # 96,000 a year
        with self.assertRaises(ValueError):
            validate_declared_investments(_rent(monthly_rent=9000, landlord_pan=''))  # 1,08,000 a year

    def test_landlord_pan_format_is_checked(self):
        with self.assertRaises(ValueError):
            validate_declared_investments(_rent(landlord_pan='12345'))

    def test_months_of_rent_must_be_1_to_12(self):
        for months in (0, 13):
            with self.subTest(months=months), self.assertRaises(ValueError):
                validate_declared_investments(_rent(months=months))

    def test_home_loan_interest_needs_lender_name_and_pan(self):
        validate_declared_investments({'80C_PPF': 1000})
        for details in ({}, {'home_loan': {'lender_name': 'Bank', 'lender_pan': ''}},
                        {'home_loan': {'lender_name': '', 'lender_pan': 'ABCDE1234F'}},
                        {'home_loan': {'lender_name': 'Bank', 'lender_pan': '123'}}):
            with self.subTest(details=details), self.assertRaises(ValueError):
                validate_declared_investments({'24B': 90000, '_details': details})
        validate_declared_investments({'24B': 90000, '_details': {'home_loan': {'lender_name': 'Bank', 'lender_pan': 'ABCDE1234F'}}})

    def test_senior_flags_must_be_boolean(self):
        with self.assertRaises(ValueError):
            validate_declared_investments({'_details': {'senior_parents': 'yes'}})


class DeductionBreakdownTests(SimpleTestCase):
    def test_80c_items_are_added_then_capped_at_one_and_a_half_lakh(self):
        result = deduction_breakdown({'80C_PPF': 100000, '80C_ELSS': 80000})
        self.assertEqual(result['80C'], Decimal('150000'))

    def test_legacy_80c_adds_to_itemised(self):
        self.assertEqual(deduction_breakdown({'80C': 100000, '80C_PPF': 20000})['80C'], Decimal('120000'))

    def test_80d_limits_depend_on_senior_citizen_answers(self):
        declared = {'80D_SELF_FAMILY': 55000, '80D_PARENTS': 60000}
        self.assertEqual(deduction_breakdown(declared)['80D'], Decimal('50000'))
        seniors = {**declared, '_details': {'senior_self_family': True, 'senior_parents': True}}
        self.assertEqual(deduction_breakdown(seniors)['80D'], Decimal('100000'))

    def test_home_loan_interest_capped_at_two_lakh_and_nps_at_fifty_thousand(self):
        result = deduction_breakdown({'24B': 350000, '80CCD1B': 90000})
        self.assertEqual(result['24B'], Decimal('200000'))
        self.assertEqual(result['80CCD1B'], Decimal('50000'))

    def test_hra_is_the_lowest_of_the_three_rules(self):
        # basic 40,000, HRA received 20,000, rent 25,000 in a metro:
        # min(20,000, 25,000 - 4,000, 50% x 40,000) = 20,000 a month.
        declared = _rent(monthly_rent=25000)
        self.assertEqual(deduction_breakdown(declared, Decimal('40000'), Decimal('20000'))['HRA'], Decimal('240000'))
        # rent 12,000: min(20,000, 12,000 - 4,000, 20,000) = 8,000 a month.
        declared = _rent(monthly_rent=12000)
        self.assertEqual(deduction_breakdown(declared, Decimal('40000'), Decimal('20000'))['HRA'], Decimal('96000'))

    def test_hra_uses_forty_percent_of_basic_outside_metros(self):
        declared = _rent(monthly_rent=30000, metro=False)
        self.assertEqual(deduction_breakdown(declared, Decimal('40000'), Decimal('30000'))['HRA'], Decimal('192000'))

    def test_hra_follows_months_of_rent_and_never_goes_negative(self):
        declared = _rent(monthly_rent=12000, months=6)
        self.assertEqual(deduction_breakdown(declared, Decimal('40000'), Decimal('20000'))['HRA'], Decimal('48000'))
        low_rent = _rent(monthly_rent=3000)
        self.assertEqual(deduction_breakdown(low_rent, Decimal('40000'), Decimal('20000'))['HRA'], Decimal('0'))

    def test_hra_falls_back_to_legacy_amount_without_rent_details(self):
        self.assertEqual(deduction_breakdown({'HRA': 60000})['HRA'], Decimal('60000'))


class EstimateMonthlyTdsTests(SimpleTestCase):
    def test_new_regime_ignores_declared_deductions(self):
        base = estimate_monthly_tds(Decimal('150000'), 'new', {})
        self.assertEqual(estimate_monthly_tds(Decimal('150000'), 'new', {'80C_PPF': 150000}), base)

    def test_old_regime_tax_drops_when_deductions_are_declared(self):
        without = estimate_monthly_tds(Decimal('150000'), 'old', {})
        with_deductions = estimate_monthly_tds(Decimal('150000'), 'old', {'80C_PPF': 150000, '80D_SELF_FAMILY': 25000})
        self.assertLess(with_deductions, without)

    def test_schema_lists_every_group_with_fields(self):
        payload = schema_payload()
        self.assertEqual(payload['groups'][0]['cap'], 150000)
        self.assertTrue(all(group['fields'] for group in payload['groups']))
