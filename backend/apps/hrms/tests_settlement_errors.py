"""Full & Final settlement edits: every rejection names its field, and a negative net payable needs `is_recovery` (UAT-016)."""
import datetime
from decimal import Decimal

from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient

from apps.accounts.factories import make_role, make_user
from apps.hrms.models import SeparationRequest, SeparationSettlement
from apps.hrms.services_settlement import format_inr


class FormatInrTests(TestCase):
    def test_indian_grouping(self):
        self.assertEqual(format_inr(Decimal('150000')), 'Rs 1,50,000')
        self.assertEqual(format_inr(Decimal('999')), 'Rs 999')
        self.assertEqual(format_inr(Decimal('12345678')), 'Rs 1,23,45,678')

    def test_negative_amount_leads_with_the_sign(self):
        self.assertEqual(format_inr(Decimal('-150000')), '-Rs 1,50,000')


class SettlementEditErrorTests(TestCase):
    def setUp(self):
        role = make_role('payroll_settlement_test', permission_codenames=['payroll.edit', 'employees.view'])
        self.finance = make_user('finance-settlement@test.com', role=role)
        self.employee = make_user('leaver-settlement@test.com')
        self.separation = SeparationRequest.objects.create(
            employee=self.employee, separation_type='resignation',
            request_date=datetime.date(2026, 4, 1), proposed_last_working_day=datetime.date(2026, 5, 1),
            created_by=self.finance,
        )
        self.client = APIClient()
        self.client.force_authenticate(user=self.finance)
        self.url = reverse('separation-settlement', kwargs={'request_id': str(self.separation.id)})

    def _patch(self, payload):
        return self.client.patch(self.url, payload, format='json')

    def test_negative_gratuity_is_rejected_with_the_field_named(self):
        response = self._patch({'gratuity_amount': '-1'})
        self.assertEqual(response.status_code, 400)
        body = response.json()
        self.assertEqual(body['message'], 'gratuity_amount: Gratuity cannot be negative.')
        # The form reads this to put the message beside the Gratuity input.
        self.assertEqual(body['data']['gratuity_amount'], ['Gratuity cannot be negative.'])

    def test_negative_net_payable_is_rejected_unless_marked_recovery(self):
        response = self._patch({'advances_recovery_amount': '150000'})
        self.assertEqual(response.status_code, 400)
        body = response.json()
        self.assertIn('-Rs 1,50,000', body['message'])
        self.assertIn('is_recovery', body['data'])
        settlement = SeparationSettlement.objects.get(request=self.separation)
        self.assertEqual(settlement.advances_recovery_amount, Decimal('0'))

    def test_negative_net_payable_saves_when_marked_recovery(self):
        response = self._patch({'advances_recovery_amount': '150000', 'is_recovery': True})
        self.assertEqual(response.status_code, 200)
        data = response.json()['data']
        self.assertEqual(Decimal(data['net_payable_amount']), Decimal('-150000'))
        self.assertTrue(data['is_recovery'])

    def test_finalize_refuses_a_negative_net_that_is_not_a_recovery(self):
        self._patch({'advances_recovery_amount': '150000', 'is_recovery': True})
        SeparationSettlement.objects.filter(request=self.separation).update(is_recovery=False)
        finalize_url = reverse('separation-settlement-finalize', kwargs={'request_id': str(self.separation.id)})
        response = self.client.post(finalize_url, {}, format='json')
        self.assertEqual(response.status_code, 400)
        self.assertIn('-Rs 1,50,000', response.json()['message'])
        self.assertEqual(SeparationSettlement.objects.get(request=self.separation).status, 'draft')

    def test_positive_net_needs_no_flag(self):
        response = self._patch({'gratuity_amount': '50000'})
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.json()['data']['is_recovery'])
