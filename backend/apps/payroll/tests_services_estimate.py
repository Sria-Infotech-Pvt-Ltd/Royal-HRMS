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

from apps.branch.models import Branch, City, State
from apps.payroll.models import StatutoryConfig
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

    def test_employer_pf_and_eps_together_never_exceed_the_statutory_employer_rate(self):
        # QA report #47 — Employer PF and EPS used to each be computed at
        # their own full rate independently (12% + 8.33%), double-counting
        # EPS since it's statutorily carved OUT of the employer's 12% PF
        # share, not paid on top of it.
        result = estimate_salary_breakdown(600000, None, None, None)
        pf_wage_base = min(result['basic'], 15000.0)
        expected_total = pf_wage_base * 12 / 100
        self.assertAlmostEqual(result['employer_pf'] + result['employer_eps'], expected_total, delta=0.01)


class ProfessionalTaxTests(TestCase):
    def test_telangana_pt_applies_at_50k_monthly_gross(self):
        # QA report #48 — PT always showed Rs 0 regardless of gross salary.
        # Root cause: zero StatutoryConfig rows existed in the database at
        # all (not a formula bug) — see migration
        # 0024_seed_telangana_statutory_config.
        state, _ = State.objects.get_or_create(code='TG', defaults={'name': 'Telangana'})
        city, _ = City.objects.get_or_create(name='Hyderabad', state=state)
        branch = Branch.objects.create(branch_code='PTTEST', branch_name='PT Test Branch', state=state, city=city)
        statutory = StatutoryConfig.objects.get(state=state)
        self.assertTrue(statutory.pt_applicable)

        result = estimate_salary_breakdown(600000, None, branch, statutory)
        # 6,00,000 / 12 with the flat-split default structure lands gross
        # comfortably above the Rs 20,000 slab boundary, so PT must be the
        # top Telangana slab amount (Rs 200).
        self.assertEqual(result['pt_deduction'], 200.0)
