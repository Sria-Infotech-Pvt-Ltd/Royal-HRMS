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
