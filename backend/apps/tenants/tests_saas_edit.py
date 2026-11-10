"""
Edit Subscription (Platform Admin) and automatic subscription amounts.

- A subscription assigned without an employee count ("Not set") gets its
  amount calculated once the count is added: price x employees x months + GST.
- Plan changes (Starter -> Growth -> Enterprise), employee count and billing
  period changes recalculate the amount from the plan's configured price;
  GST inclusive / additional; old -> new shown in the preview.
- Manual amounts need a reason and are kept through later edits.
- Payments are never changed; Paid / Partially paid / Pending follow the
  confirmed payments; awaiting-confirmation payments are not counted; waived
  stays waived; overpaid is reported.
- History + audit, validation, and access (Platform Admin only).
"""
from __future__ import annotations

import datetime
from decimal import Decimal

from django.urls import reverse
from rest_framework.test import APIClient

from apps.tenants.models import (
    CompanySubscription, PlatformAdminAuditLog, SubscriptionHistory, SubscriptionPayment, SubscriptionPlan,
)
from apps.tenants.tests_saas import TODAY
from apps.tenants.tests_saas_access import AccessBase


class EditBase(AccessBase):
    def setUp(self):
        super().setUp()
        base = {'status': 'active', 'currency': 'INR', 'gst_rate': Decimal('18'), 'gst_inclusive': False,
                'billing_periods': ['monthly', 'yearly']}
        self.basic = SubscriptionPlan.objects.create(code='ed-starter', name='Ed Starter', price_per_employee=Decimal('49'),
                                                     features=['leave'], **base)
        self.mid = SubscriptionPlan.objects.create(code='ed-growth', name='Ed Growth', price_per_employee=Decimal('99'),
                                                   features=['leave', 'payroll'], **base)
        self.top = SubscriptionPlan.objects.create(code='ed-enterprise', name='Ed Enterprise',
                                                   price_per_employee=Decimal('149'),
                                                   features=['leave', 'payroll', 'assets'], **base)
        self.incl = SubscriptionPlan.objects.create(
            code='ed-incl', name='Ed Inclusive', price_per_employee=Decimal('118'),
            **{**base, 'gst_inclusive': True}, features=['leave'])
        self.small = SubscriptionPlan.objects.create(code='ed-small', name='Ed Small', price_per_employee=Decimal('10'),
                                                     max_employees=15, features=['leave'], **base)

    def edit(self, dry_run=False, **body):
        url = reverse('saas-subscription-edit', kwargs={'client_id': str(self.company.pk)})
        return self.pa.post(url, {**body, **({'dry_run': True} if dry_run else {})}, format='json')

    def pay(self, amount, confirm=True):
        url = reverse('saas-subscription-payments', kwargs={'client_id': str(self.company.pk)})
        resp = self.pa.post(url, {'amount': amount, 'method': 'upi', 'paid_on': TODAY.isoformat(), 'confirm': confirm},
                            format='multipart')
        self.assertEqual(resp.status_code, 201, resp.data)

    def sub(self):
        return CompanySubscription.objects.get(client=self.company)

    def payments(self):
        return list(SubscriptionPayment.objects.filter(subscription__client=self.company)
                    .order_by('created_at').values_list('amount', 'status'))


class AutomaticAmountTests(EditBase):
    def test_not_set_amount_is_calculated_when_employee_count_is_added(self):
        """The screenshot case: Growth, no employee count, amount "Not set"."""
        self.assertEqual(self.assign(plan=self.mid, billing_period='monthly').status_code, 201)
        self.assertIsNone(self.sub().amount_due)
        preview = self.edit(dry_run=True, employee_count=20)
        self.assertEqual(preview.status_code, 200, preview.data)
        p = preview.data['data']
        self.assertEqual((p['amount']['from'], p['amount']['to'], p['amount']['mode']), (None, '2336.40', 'auto'))
        calc = p['amount']['calculated']
        self.assertEqual((calc['subtotal'], calc['gst_amount'], calc['total']), ('1980.00', '356.40', '2336.40'))
        self.assertIsNone(self.sub().amount_due)                     # preview saves nothing
        self.assertFalse(SubscriptionHistory.objects.filter(event='edited').exists())

        resp = self.edit(employee_count=20)
        self.assertEqual(resp.status_code, 200, resp.data)
        s = resp.data['data']
        self.assertEqual((s['employee_count'], s['amount_due'], s['amount_outstanding'], s['payment_status']),
                         (20, '2336.40', '2336.40', 'pending'))
        h = SubscriptionHistory.objects.get(event='edited')
        self.assertIn('Employees: — → 20', h.note)
        self.assertIn('Subscription amount: not set → 2,336.40 INR (calculated: 20 × 99.00 × 1 month(s) + GST 18%)', h.note)
        self.assertTrue(PlatformAdminAuditLog.objects.filter(action='saas_subscription_edited').exists())

    def test_assignment_calculates_the_amount(self):
        self.assign(plan=self.mid, employee_count=20, billing_period='monthly')
        self.assertEqual(self.sub().amount_due, Decimal('2336.40'))
        self.assertFalse(SubscriptionHistory.objects.filter(event='amount_due_changed').exists())

    def test_manual_amount_on_assignment_is_recorded(self):
        self.assign(plan=self.mid, employee_count=20, billing_period='monthly', amount_due='2000.00',
                    amount_reason='Launch discount')
        self.assertEqual(self.sub().amount_due, Decimal('2000.00'))
        h = SubscriptionHistory.objects.get(event='amount_due_changed')
        self.assertIn('Set manually: 2,000.00 INR (calculated: 2,336.40) — Launch discount', h.note)

    def test_gst_inclusive_plan(self):
        self.assign(plan=self.incl, employee_count=10, billing_period='monthly')
        self.assertEqual(self.sub().amount_due, Decimal('1180.00'))          # GST inside the price
        p = self.edit(dry_run=True, employee_count=5).data['data']['amount']['calculated']
        self.assertEqual((p['subtotal'], p['gst_amount'], p['total']), ('590.00', '90.00', '590.00'))


class PlanChangeTests(EditBase):
    def setUp(self):
        super().setUp()
        self.assign(plan=self.basic, employee_count=10, billing_period='monthly')
        self.assertEqual(self.sub().amount_due, Decimal('578.20'))

    def test_starter_to_growth_after_full_payment(self):
        self.pay('578.20')
        self.assertEqual(self.sub().payment_status, 'paid')
        before = self.payments()
        p = self.edit(dry_run=True, plan=str(self.mid.pk)).data['data']
        self.assertEqual((p['amount']['from'], p['amount']['to']), ('578.20', '1168.20'))
        self.assertEqual((p['payment_status']['from'], p['payment_status']['to']), ('paid', 'partially_paid'))
        self.assertEqual((p['payments']['outstanding_before'], p['payments']['outstanding_after']), ('0.00', '590.00'))
        self.assertTrue(any('Paid to Partially paid' in w for w in p['warnings']))

        s = self.edit(plan=str(self.mid.pk)).data['data']
        self.assertEqual((s['plan_name'], s['price_per_employee'], s['amount_due'], s['payment_status'],
                          s['amount_received'], s['amount_outstanding']),
                         ('Ed Growth', '99.00', '1168.20', 'partially_paid', '578.20', '590.00'))
        self.assertEqual(self.payments(), before)                      # payments untouched
        self.assertNotIn('Ed Starter', s['plan_name'])

    def test_growth_to_enterprise(self):
        self.edit(plan=str(self.mid.pk))
        s = self.edit(plan=str(self.top.pk)).data['data']
        self.assertEqual((s['plan_name'], s['amount_due']), ('Ed Enterprise', '1758.20'))   # 10 × 149 + 18%

    def test_employee_count_change(self):
        s = self.edit(employee_count=25).data['data']
        self.assertEqual(s['amount_due'], '1445.50')                    # 25 × 49 = 1225 + 220.50

    def test_monthly_to_yearly(self):
        ends = datetime.date(2027, 11, 3).isoformat()
        s = self.edit(billing_period='yearly', ends_on=ends).data['data']
        self.assertEqual((s['billing_period'], s['amount_due'], s['ends_on']), ('yearly', '6938.40', ends))

    def test_awaiting_payment_plan_change_waits_for_payment(self):
        modules_before = sorted(self.company.__class__.objects.get(pk=self.company.pk).enabled_modules)
        p = self.edit(dry_run=True, plan=str(self.top.pk)).data['data']
        self.assertTrue(any('applied once it is confirmed' in w for w in p['warnings']))
        self.edit(plan=str(self.top.pk))
        self.assertEqual(sorted(self.company.__class__.objects.get(pk=self.company.pk).enabled_modules), modules_before)

    def test_paid_plan_change_applies_modules(self):
        self.edit(amount_mode='manual', amount_due='100.00', amount_reason='test')
        self.pay('100.00')
        self.assertEqual(self.sub().provisioning_status, 'success')
        self.edit(plan=str(self.top.pk), amount_mode='manual', amount_due='100.00', amount_reason='same price agreed')
        self.assertIn('assets', self.sub().client.__class__.objects.get(pk=self.company.pk).enabled_modules)

    def test_plan_must_fit_employee_count(self):
        self.edit(employee_count=20)
        resp = self.edit(plan=str(self.small.pk))
        self.assertEqual(resp.status_code, 400)
        self.assertIn('at most 15 employees', resp.data['message'])


class ManualAmountAndPaymentTests(EditBase):
    def setUp(self):
        super().setUp()
        self.assign(plan=self.basic, employee_count=10, billing_period='monthly')

    def test_manual_amount_needs_a_reason_and_is_kept(self):
        resp = self.edit(amount_mode='manual', amount_due='500.00')
        self.assertEqual(resp.status_code, 400)
        self.assertIn('amount_reason', resp.data['data'])
        s = self.edit(amount_mode='manual', amount_due='500.00', amount_reason='Negotiated price').data['data']
        self.assertEqual(s['amount_due'], '500.00')
        h = SubscriptionHistory.objects.filter(event='edited').first()
        self.assertIn('manual — Negotiated price', h.note)
        # Editing notes or dates keeps the manual amount.
        self.edit(notes='Renewal call booked', ends_on='2026-12-31')
        self.assertEqual(self.sub().amount_due, Decimal('500.00'))
        # Back to automatic recalculates.
        self.assertEqual(self.edit(amount_mode='auto').data['data']['amount_due'], '578.20')

    def test_awaiting_confirmation_is_not_counted(self):
        self.pay('578.20', confirm=False)
        p = self.edit(dry_run=True, employee_count=12).data['data']
        self.assertEqual((p['payments']['pending'], p['payment_status']['to']), ('578.20', 'pending'))
        self.assertTrue(any('awaiting confirmation is not counted' in w for w in p['warnings']))
        s = self.edit(employee_count=12).data['data']
        self.assertEqual((s['payment_status'], s['amount_outstanding']), ('pending', '693.84'))
        self.assertEqual(self.payments(), [(Decimal('578.20'), 'recorded')])

    def test_reducing_below_confirmed_payments_reports_overpaid(self):
        self.pay('578.20')
        p = self.edit(dry_run=True, employee_count=5).data['data']
        self.assertEqual(p['payments']['overpaid_after'], '289.10')
        self.assertTrue(any('overpaid' in w for w in p['warnings']))
        s = self.edit(employee_count=5).data['data']
        self.assertEqual((s['payment_status'], s['amount_overpaid']), ('paid', '289.10'))

    def test_partial_payment_becomes_paid_when_amount_is_lowered(self):
        self.pay('300.00')
        p = self.edit(dry_run=True, amount_mode='manual', amount_due='300.00', amount_reason='Discount').data['data']
        self.assertTrue(any('becomes Paid and its modules are applied' in w for w in p['warnings']))
        self.edit(amount_mode='manual', amount_due='300.00', amount_reason='Discount')
        self.assertEqual((self.sub().payment_status, self.sub().provisioning_status), ('paid', 'success'))

    def test_waived_stays_waived(self):
        url = reverse('saas-subscription-waiver', kwargs={'client_id': str(self.company.pk)})
        self.pa.post(url, {'waive': True, 'reason': 'Pilot'}, format='json')
        s = self.edit(employee_count=20).data['data']
        self.assertEqual((s['payment_status'], s['amount_due'], s['amount_outstanding']), ('waived', '1156.40', '0.00'))


class ValidationAndAccessTests(EditBase):
    def setUp(self):
        super().setUp()
        self.assign(plan=self.basic, employee_count=10, billing_period='monthly')

    def test_invalid_inputs(self):
        for body, field in [({'employee_count': 0}, 'employee_count'), ({'employee_count': 'ten'}, 'employee_count'),
                            ({'employee_count': 100001}, 'employee_count'),
                            ({'billing_period': 'weekly'}, 'billing_period'),
                            ({'ends_on': '2026-02-30'}, 'ends_on'), ({'starts_on': 'soon'}, 'starts_on'),
                            ({'amount_mode': 'manual', 'amount_due': '-5', 'amount_reason': 'x'}, 'amount_due'),
                            ({'amount_mode': 'free'}, 'amount_mode'), ({'plan': 'not-a-uuid'}, 'plan')]:
            resp = self.edit(**body)
            self.assertEqual(resp.status_code, 400, body)
            self.assertIn(field, resp.data['data'], body)
        self.assertEqual(self.sub().amount_due, Decimal('578.20'))

    def test_business_rule_refusals(self):
        self.assertIn('before the start date', self.edit(ends_on='2026-01-01').data['message'])
        self.assertIn('Nothing to change', self.edit(employee_count=10).data['message'])
        self.mid.status = 'inactive'
        self.mid.save()
        self.assertIn('active plan', self.edit(plan=str(self.mid.pk)).data['message'])
        CompanySubscription.objects.filter(client=self.company).update(employee_count=None)
        self.assertIn('Enter the employee count', self.edit(amount_mode='auto').data['message'])
        self.assertFalse(SubscriptionHistory.objects.filter(event='edited').exists())

    def test_only_platform_admins(self):
        url = reverse('saas-subscription-edit', kwargs={'client_id': str(self.company.pk)})
        self.assertIn(APIClient().post(url, {'employee_count': 50}, format='json').status_code, (401, 403))
        self.assertIn(self.web.post(url, {'employee_count': 50}, format='json').status_code, (401, 403, 404))
        self.assertEqual(self.sub().employee_count, 10)

    def test_unknown_company(self):
        import uuid
        url = reverse('saas-subscription-edit', kwargs={'client_id': str(uuid.uuid4())})
        self.assertEqual(self.pa.post(url, {'employee_count': 5}, format='json').status_code, 404)
