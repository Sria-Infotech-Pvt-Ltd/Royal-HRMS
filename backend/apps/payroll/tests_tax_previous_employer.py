"""UAT-053: tax deducted by a previous employer cannot exceed the income they paid (server rule; no database needed)."""
from django.test import SimpleTestCase

from apps.payroll.tax_declaration_schema import DETAILS_KEY
from apps.payroll.tax_declaration_validation import validate_declared_investments


def _declaration(income, tds):
    return {DETAILS_KEY: {'previous_employer': {'name': 'Earlier Co', 'income': income, 'tds': tds}}}


class PreviousEmployerTdsTests(SimpleTestCase):
    def test_the_reported_case_is_rejected(self):
        with self.assertRaises(ValueError) as caught:
            validate_declared_investments(_declaration('100', '500'))
        self.assertIn('cannot be more than the income', str(caught.exception))

    def test_equal_lower_and_blank_are_accepted(self):
        for income, tds in (('100', '100'), ('50000', '2500'), ('', ''), (0, 0)):
            validate_declared_investments(_declaration(income, tds))  # does not raise

    def test_tds_with_no_income_is_rejected(self):
        with self.assertRaises(ValueError):
            validate_declared_investments(_declaration('', '10'))
