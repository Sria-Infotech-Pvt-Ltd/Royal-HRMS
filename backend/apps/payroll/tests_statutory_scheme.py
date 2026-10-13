"""Phase 7A Task F — seed_statutory_schemes idempotency and value fidelity."""
from decimal import Decimal

from django.core.management import call_command
from django.test import TestCase

from apps.payroll.models import PayrollSettings, StatutoryConfig, StatutoryRate, StatutoryScheme
from apps.branch.models import State


class SeedStatutorySchemesTests(TestCase):
    def setUp(self):
        self.state = State.objects.create(name='TestState', code='TS')
        StatutoryConfig.objects.create(
            state=self.state, pt_applicable=True, pt_slabs=[{'min': 0, 'max': None, 'amount': 150}],
            esi_applicable=True, esi_wage_ceiling=Decimal('21000.00'),
            esi_employee_rate=Decimal('0.75'), esi_employer_rate=Decimal('3.25'),
            lwf_applicable=True, lwf_employee_amount=Decimal('10'), lwf_employer_amount=Decimal('30'),
        )
        PayrollSettings.objects.get_or_create(defaults={})

    def test_seed_creates_expected_schemes_and_rates(self):
        call_command('seed_statutory_schemes')

        self.assertEqual(StatutoryScheme.objects.count(), 8)
        pt_rate = StatutoryRate.objects.get(scheme__code='PT', state=self.state)
        self.assertEqual(pt_rate.parameters['slabs'][0]['amount'], 150)
        esi_rate = StatutoryRate.objects.get(scheme__code='ESI', state=self.state)
        self.assertEqual(esi_rate.parameters['wage_ceiling'], '21000.00')
        lwf_rate = StatutoryRate.objects.get(scheme__code='LWF', state=self.state)
        self.assertEqual(lwf_rate.parameters['employee_amount'], '10.00')

    def test_seed_is_idempotent(self):
        call_command('seed_statutory_schemes')
        first_rate_count = StatutoryRate.objects.count()
        first_scheme_count = StatutoryScheme.objects.count()

        call_command('seed_statutory_schemes')
        self.assertEqual(StatutoryRate.objects.count(), first_rate_count)
        self.assertEqual(StatutoryScheme.objects.count(), first_scheme_count)

    def test_every_rate_has_a_source_citation(self):
        call_command('seed_statutory_schemes')
        uncited = StatutoryRate.objects.filter(source_citation='')
        self.assertEqual(uncited.count(), 0)
