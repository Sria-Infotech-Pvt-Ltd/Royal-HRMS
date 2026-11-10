"""
Subscription end date (calendar months) and the Record Payment flow:
  * end date = one billing period from the start (same day, or the last day
    of a shorter month — never +30 days); an explicit date or "no end date"
    is kept; website sign-ups use the same rule;
  * the subscription amount is calculated on the server when it isn't given,
    so a full payment needs only the payment amount and leaves 0 outstanding;
  * outstanding / awaiting confirmation / overpaid come from the server;
  * a payment above the outstanding balance is refused until confirmed.
"""
from __future__ import annotations

import datetime
from decimal import Decimal

from django.urls import reverse

from apps.tenants import registrations
from apps.tenants.models import CompanySubscription, SubscriptionHistory, SubscriptionPayment
from apps.tenants.pricing import add_months, period_end
from apps.tenants.tests_saas import TODAY, SaasFixture

D = datetime.date


class CalendarMonthTests(SaasFixture):
    def test_examples(self):
        for start, months, end in [
            (D(2027, 1, 15), 1, D(2027, 2, 15)),
            (D(2027, 1, 31), 1, D(2027, 2, 28)),
            (D(2028, 1, 31), 1, D(2028, 2, 29)),       # leap year
            (D(2027, 3, 31), 1, D(2027, 4, 30)),
            (D(2027, 4, 30), 1, D(2027, 5, 30)),
            (D(2027, 5, 31), 1, D(2027, 6, 30)),
            (D(2026, 12, 31), 1, D(2027, 1, 31)),      # year rollover
            (D(2028, 2, 29), 12, D(2029, 2, 28)),      # leap day + 1 year
            (D(2027, 8, 31), 6, D(2028, 2, 29)),
        ]:
            self.assertEqual(add_months(start, months), end, (start, months))

    def test_period_end(self):
        self.assertEqual(period_end(D(2027, 1, 31), 'monthly'), D(2027, 2, 28))
        self.assertEqual(period_end(D(2027, 1, 31), 'yearly'), D(2028, 1, 31))
        self.assertIsNone(period_end(D(2027, 1, 31), ''))

    def test_website_signups_use_the_same_rule(self):
        self.assertIs(registrations._add_months, add_months)


class AssignEndDateTests(SaasFixture):
    def sub(self):
        return CompanySubscription.objects.get(client=self.company)

    def test_monthly_without_end_date_field_is_one_month(self):
        self.assertEqual(self.assign(billing_period='monthly').status_code, 201)
        self.assertEqual(self.sub().ends_on, add_months(TODAY, 1))

    def test_yearly_without_end_date_field_is_one_year(self):
        self.starter.billing_periods = ['monthly', 'yearly']
        self.starter.save(update_fields=['billing_periods'])
        self.assertEqual(self.assign(billing_period='yearly').status_code, 201)
        self.assertEqual(self.sub().ends_on, add_months(TODAY, 12))

    def test_explicit_no_end_date_is_kept(self):
        self.assertEqual(self.assign(billing_period='monthly', ends_on=None).status_code, 201)
        self.assertIsNone(self.sub().ends_on)

    def test_explicit_date_is_kept(self):
        self.assertEqual(self.assign(billing_period='monthly', ends_on='2027-03-15').status_code, 201)
        self.assertEqual(self.sub().ends_on, D(2027, 3, 15))

    def test_no_billing_period_no_end_date(self):
        self.assertEqual(self.assign().status_code, 201)
        self.assertIsNone(self.sub().ends_on)


class PaymentFlowTests(SaasFixture):
    """Starter: 49 per employee per month + 18% GST → 10 employees = 578.20."""

    def setUp(self):
        super().setUp()
        self.assertEqual(self.assign(employee_count=10, billing_period='monthly').status_code, 201)

    def url(self, name, **kw):
        return reverse(name, kwargs={'client_id': str(self.company.pk), **kw})

    def pay(self, amount, confirm=True, **extra):
        return self.pa.post(self.url('saas-subscription-payments'), {
            'amount': amount, 'method': 'upi', 'paid_on': TODAY.isoformat(), 'confirm': confirm, **extra,
        }, format='multipart')

    def sub(self):
        return CompanySubscription.objects.get(client=self.company)

    def test_subscription_amount_calculated_on_assignment(self):
        self.assertEqual(self.sub().amount_due, Decimal('578.20'))

    def test_full_payment_needs_only_the_payment_amount(self):
        resp = self.pay('578.20')
        self.assertEqual(resp.status_code, 201, resp.data)
        s = resp.data['data']['subscription']
        self.assertEqual((s['payment_status'], s['amount_outstanding'], s['amount_received']), ('paid', '0.00', '578.20'))

    def test_partial_payment_outstanding(self):
        s = self.pay('200.00').data['data']['subscription']
        self.assertEqual((s['payment_status'], s['amount_outstanding']), ('partially_paid', '378.20'))
        s = self.pay('378.20').data['data']['subscription']
        self.assertEqual((s['payment_status'], s['amount_outstanding']), ('paid', '0.00'))

    def test_unconfirmed_payment_shown_as_awaiting_confirmation(self):
        s = self.pay('578.20', confirm=False).data['data']['subscription']
        self.assertEqual((s['amount_pending_confirmation'], s['amount_outstanding'], s['payment_status']),
                         ('578.20', '578.20', 'pending'))
        payment = SubscriptionPayment.objects.get(subscription__client=self.company)
        resp = self.pa.post(self.url('saas-subscription-payment-verify', payment_id=payment.pk))
        self.assertEqual(resp.data['data']['subscription']['amount_outstanding'], '0.00')

    def test_missing_amount_is_calculated_when_confirming(self):
        CompanySubscription.objects.filter(client=self.company).update(amount_due=None)
        resp = self.pay('578.20')
        self.assertEqual(resp.status_code, 201, resp.data)
        self.assertEqual((self.sub().amount_due, self.sub().payment_status), (Decimal('578.20'), 'paid'))
        self.assertTrue(SubscriptionHistory.objects.filter(subscription=self.sub(), event='amount_due_changed',
                                                           note__contains='calculated from 10 employees').exists())

    def test_without_employee_count_the_amount_is_asked_once(self):
        CompanySubscription.objects.filter(client=self.company).update(amount_due=None, employee_count=None)
        resp = self.pay('500.00')
        self.assertEqual(resp.status_code, 400)
        self.assertIn('Set the subscription amount', resp.data['message'])
        self.assertEqual(self.pay('500.00', confirm=False).status_code, 201)     # recording without confirm is fine

    def test_overpayment_needs_confirmation(self):
        resp = self.pay('600.00')
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(resp.data['data']['requires_confirmation'], 'overpayment')
        self.assertIn('more than the outstanding balance (578.20 INR)', resp.data['message'])
        self.assertFalse(SubscriptionPayment.objects.filter(subscription__client=self.company).exists())
        ok = self.pay('600.00', allow_overpayment=True)
        self.assertEqual(ok.status_code, 201, ok.data)
        s = ok.data['data']['subscription']
        self.assertEqual((s['payment_status'], s['amount_outstanding'], s['amount_overpaid']), ('paid', '0.00', '21.80'))

    def test_overpayment_counts_payments_awaiting_confirmation(self):
        self.assertEqual(self.pay('578.20', confirm=False).status_code, 201)
        resp = self.pay('100.00')
        self.assertEqual(resp.status_code, 400)
        self.assertIn('awaiting confirmation', resp.data['message'])

    def test_waived_subscription_warns(self):
        self.pa.post(self.url('saas-subscription-waiver'), {'waive': True, 'reason': 'pilot'}, format='json')
        resp = self.pay('100.00')
        self.assertEqual(resp.data['data']['requires_confirmation'], 'overpayment')
        self.assertEqual(self.sub().payment_status, 'waived')
        self.assertEqual(resp.data['message'].split('.')[0], 'Payment is waived for this subscription, so nothing is outstanding')

    def test_exact_outstanding_is_not_a_warning(self):
        self.assertEqual(self.pay('300.00').status_code, 201)
        self.assertEqual(self.pay('278.20').status_code, 201)
        self.assertEqual(self.sub().payment_status, 'paid')
