"""
Regression tests for estimate_salary_breakdown()'s CTC reverse-solve —
was previously treating the entered "Annual CTC" as gross earnings and
then ADDING employer PF/EPS/gratuity on top, so the displayed
"Annual cost to company" always exceeded what was actually entered
(e.g. entering 6,00,000 produced 6,48,138) — CTC by definition already
includes those employer contributions.
"""
from __future__ import annotations

from django.test import TestCase

from apps.payroll.services_estimate import estimate_salary_breakdown

# A few paise of floating-point/Decimal rounding across 8 iterations is
# expected and fine; anything beyond a rupee would mean the reverse-solve
# isn't actually converging.
_TOLERANCE = 1.0


class EstimateSalaryBreakdownCtcConvergenceTests(TestCase):
    def test_annual_cost_to_company_matches_entered_ctc_no_structure(self):
        for ctc in (300000, 600000, 1200000, 2400000, 5000000):
            with self.subTest(ctc=ctc):
                result = estimate_salary_breakdown(ctc, None, None, None)
                self.assertAlmostEqual(result['annual_cost_to_company'], ctc, delta=_TOLERANCE)

    def test_gross_earnings_is_less_than_entered_ctc(self):
        # The whole point of the fix: gross must be carved OUT of the CTC
        # ceiling, not equal to it (employer contributions are on top of
        # gross, not on top of CTC).
        result = estimate_salary_breakdown(600000, None, None, None)
        monthly_ctc = 600000 / 12
        self.assertLess(result['gross_earnings'], monthly_ctc)

    def test_monthly_cost_to_company_equals_gross_plus_employer_contributions(self):
        result = estimate_salary_breakdown(600000, None, None, None)
        expected = (
            result['gross_earnings'] + result['employer_pf'] + result['employer_eps']
            + result['gratuity_provision'] + result['employer_esi']
        )
        self.assertAlmostEqual(result['monthly_cost_to_company'], expected, delta=0.01)
