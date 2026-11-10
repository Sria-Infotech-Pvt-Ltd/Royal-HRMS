"""
Company Settings → Plan Details (GET /api/settings/company/plan/): what the
logged-in company purchased, module inclusion vs actual access, other public
plans with additional modules and estimates, payment history (confirmed +
awaiting, rejected hidden), permissions (settings.edit only), isolation
between companies, and that the page changes nothing.
"""
from __future__ import annotations

import datetime
from decimal import Decimal

from django.urls import reverse
from django_tenants.utils import schema_context
from rest_framework.test import APIClient

from apps.accounts.factories import make_role, make_user
from apps.tenants.models import (
    Client, CompanySubscription, SubscriptionHistory, SubscriptionPayment, SubscriptionPlan,
)
from apps.tenants.modules import FEATURES
from apps.tenants.tests_saas import TODAY
from apps.tenants.tests_saas_access import AccessBase
from config.test_runner import TEST_COMPANY_CODE

URL = '/api/settings/company/plan/'
INTERNAL_KEYS = {'notes', 'provisioning_error', 'pending_admin_email', 'extra_modules', 'removed_modules',
                 'plan_outdated', 'latest_plan', 'recorded_by_name', 'reviewed_by_name', 'rejection_reason',
                 'receipt_name', 'has_receipt'}


def _keys(obj, found=None):
    found = set() if found is None else found
    if isinstance(obj, dict):
        for k, v in obj.items():
            found.add(k)
            _keys(v, found)
    elif isinstance(obj, list):
        for v in obj:
            _keys(v, found)
    return found


class PlanDetailsBase(AccessBase):
    def setUp(self):
        super().setUp()
        base = {'status': 'active', 'gst_rate': Decimal('18'), 'billing_periods': ['monthly', 'yearly']}
        self.basic = SubscriptionPlan.objects.create(code='pd-basic', name='PD Basic', description='Small teams',
                                                     price_per_employee=Decimal('50'), is_public=True,
                                                     features=['payroll', 'announcements', 'mobile_access'], **base)
        self.pro = SubscriptionPlan.objects.create(code='pd-pro', name='PD Pro', description='Growing teams',
                                                   price_per_employee=Decimal('100'), is_public=True,
                                                   features=['payroll', 'announcements', 'recruitment', 'assets',
                                                             'priority_support'], **base)
        SubscriptionPlan.objects.create(code='pd-private', name='PD Private', price_per_employee=Decimal('10'),
                                        is_public=False, features=['payroll'], **base)

    def details(self, client=None):
        resp = (client or self.web).get(URL)
        self.assertEqual(resp.status_code, 200, getattr(resp, 'data', resp))
        return resp.data['data']

    def assign_basic(self, **extra):
        resp = self.assign(plan=self.basic, employee_count=10, billing_period='monthly', **extra)
        self.assertEqual(resp.status_code, 201, resp.data)

    def pay(self, amount, confirm=True, **extra):
        return self.pa.post(reverse('saas-subscription-payments', kwargs={'client_id': str(self.company.pk)}), {
            'amount': amount, 'method': 'upi', 'paid_on': TODAY.isoformat(), 'confirm': confirm, **extra,
        }, format='multipart')

    def row(self, data, key):
        return next(r for r in data['modules'] if r['key'] == key)


class ScenarioTests(PlanDetailsBase):
    def test_no_plan(self):
        d = self.details()
        self.assertFalse(d['has_plan'])
        self.assertIsNone(d['current'])
        self.assertEqual(sorted(r['key'] for r in d['modules'] if r['enabled']), d['enabled_modules'])
        self.assertEqual({p['code'] for p in d['other_plans']} & {'pd-basic', 'pd-pro', 'pd-private'},
                         {'pd-basic', 'pd-pro'})

    def test_assigned_awaiting_payment(self):
        Client.objects.filter(pk=self.company.pk).update(enabled_modules=['attendance'])
        self.assign_basic()
        d = self.details()
        cur = d['current']
        self.assertEqual((cur['plan_name'], cur['description'], cur['billing_period'], cur['activation'],
                          cur['payment_status'], cur['total_amount'], cur['amount_paid'], cur['amount_outstanding']),
                         ('PD Basic', 'Small teams', 'monthly', 'awaiting_payment', 'pending', '590.00', '0.00',
                          '590.00'))
        payroll = self.row(d, 'payroll')
        self.assertEqual((payroll['included'], payroll['enabled'], payroll['source'], payroll['access']),
                         (True, False, 'plan', 'pending'))
        attendance = self.row(d, 'attendance')
        self.assertEqual((attendance['source'], attendance['access'], attendance['required_by']),
                         ('dependency', 'enabled', ['Payroll, Salary Structures, Payslips, PF / ESI / PT']))
        self.assertEqual(self.row(d, 'recruitment')['source'], 'not_included')

    def test_paid_activates_and_is_shown(self):
        self.assign_basic()
        self.assertEqual(self.pay('590.00').status_code, 201)
        d = self.details()
        self.assertEqual((d['current']['activation'], d['current']['payment_status'], d['current']['amount_outstanding']),
                         ('active', 'paid', '0.00'))
        self.assertEqual(self.row(d, 'payroll')['access'], 'enabled')
        self.assertFalse(self.row(d, 'recruitment')['enabled'])
        self.assertEqual([f['key'] for f in d['current']['features']], ['mobile_access'])

    def test_partial_payment_does_not_activate(self):
        Client.objects.filter(pk=self.company.pk).update(enabled_modules=['attendance'])
        self.assign_basic()
        self.pay('200.00')
        d = self.details()
        self.assertEqual((d['current']['payment_status'], d['current']['activation'], d['current']['amount_outstanding']),
                         ('partially_paid', 'awaiting_payment', '390.00'))
        self.assertEqual(self.row(d, 'payroll')['access'], 'pending')

    def test_upgrade_and_downgrade_keep_history(self):
        self.assign_basic(waive_reason='pilot')
        change = reverse('saas-subscription-change-plan', kwargs={'client_id': str(self.company.pk)})
        self.assertEqual(self.pa.post(change, {'plan': str(self.pro.pk)}, format='json').status_code, 200)
        d = self.details()
        self.assertEqual(d['current']['plan_name'], 'PD Pro')
        self.assertTrue(self.row(d, 'recruitment')['enabled'])
        self.assertNotIn('pd-pro', {p['code'] for p in d['other_plans']})
        self.assertEqual(self.pa.post(change, {'plan': str(self.basic.pk)}, format='json').status_code, 200)
        d = self.details()
        self.assertEqual(d['current']['plan_name'], 'PD Basic')
        self.assertFalse(self.row(d, 'recruitment')['enabled'])

    def test_waived_is_not_shown_as_paid(self):
        self.assign_basic(waive_reason='complimentary')
        cur = self.details()['current']
        self.assertEqual((cur['payment_status'], cur['amount_paid'], cur['amount_outstanding'], cur['activation']),
                         ('waived', '0.00', '0.00', 'active'))

    def test_company_overrides(self):
        self.assign_basic(waive_reason='pilot')
        CompanySubscription.objects.filter(client=self.company).update(extra_modules=['assets'],
                                                                       removed_modules=['announcements'])
        d = self.details()
        self.assertEqual((self.row(d, 'assets')['source'], self.row(d, 'assets')['included']), ('added', True))
        self.assertEqual((self.row(d, 'announcements')['source'], self.row(d, 'announcements')['included']),
                         ('removed', False))

    def test_period_ended_is_a_label_only(self):
        self.assign_basic(waive_reason='pilot', ends_on='2026-11-03')
        CompanySubscription.objects.filter(client=self.company).update(ends_on=datetime.date(2020, 1, 31))
        d = self.details()
        self.assertTrue(d['current']['period_ended'])
        self.assertIsNone(d['current']['days_left'])
        self.assertTrue(self.row(d, 'payroll')['enabled'])          # access unchanged


class PaymentsAndPlansTests(PlanDetailsBase):
    def test_payment_history_confirmed_and_awaiting_only(self):
        self.assign_basic()
        self.pay('100.00', reference='UTR1')
        self.pay('50.00', confirm=False, reference='UTR2')
        rejected = self.pay('25.00', confirm=False, reference='UTR3').data['data']['payment']['id']
        self.pa.post(reverse('saas-subscription-payment-reject', kwargs={'client_id': str(self.company.pk),
                                                                         'payment_id': rejected}),
                     {'reason': 'bounced'}, format='json')
        d = self.details()
        self.assertEqual(sorted((p['reference'], p['status']) for p in d['payments']),
                         [('UTR1', 'confirmed'), ('UTR2', 'awaiting_confirmation')])
        self.assertEqual(d['current']['amount_pending_confirmation'], '50.00')

    def test_other_plans_with_additional_modules_and_estimate(self):
        self.assign_basic(waive_reason='pilot')
        pro = next(p for p in self.details()['other_plans'] if p['code'] == 'pd-pro')
        self.assertEqual(pro['additional_modules'], ['assets', 'recruitment'])
        self.assertEqual(pro['estimate_employee_count'], 10)
        self.assertEqual({(e['billing_period'], e['total']) for e in pro['estimates']},
                         {('monthly', '1180.00'), ('yearly', '14160.00')})
        self.assertEqual([f['key'] for f in pro['features']], ['priority_support'])
        self.assertNotIn('pd-private', {p['code'] for p in self.details()['other_plans']})

    def test_response_has_no_internal_fields_and_changes_nothing(self):
        self.assign_basic()
        self.pay('100.00', reference='UTR9')
        CompanySubscription.objects.filter(client=self.company).update(notes='internal note')
        before = (list(CompanySubscription.objects.values()), SubscriptionHistory.objects.count(),
                  SubscriptionPayment.objects.count(), sorted(Client.objects.get(pk=self.company.pk).enabled_modules))
        d = self.details()
        self.assertFalse(_keys(d) & INTERNAL_KEYS, _keys(d) & INTERNAL_KEYS)
        self.assertNotIn('internal note', str(d))
        after = (list(CompanySubscription.objects.values()), SubscriptionHistory.objects.count(),
                 SubscriptionPayment.objects.count(), sorted(Client.objects.get(pk=self.company.pk).enabled_modules))
        self.assertEqual(before, after)

    def test_every_feature_has_a_description_in_the_catalogue(self):
        self.assertTrue(all(f.get('description') for f in FEATURES))
        served = self.pa.get(reverse('saas-features')).data['data']          # Platform Admin plan editor
        self.assertTrue(served and all(f['description'] for f in served))


class AccessTests(PlanDetailsBase):
    def client_for(self, *perms):
        role = make_role(f'pd_role_{len(perms)}', permission_codenames=list(perms))
        user = make_user(f'pd{len(perms)}@test.com', role=role, full_name='PD User')
        c = APIClient()
        resp = c.post(reverse('login'), {'company_code': TEST_COMPANY_CODE, 'email': user.email,
                                         'password': 'TestPass123!'}, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        return c

    def test_branch_admin_and_employee_refused(self):
        self.assertEqual(self.client_for('settings.view', 'employees.view').get(URL).status_code, 403)
        self.assertEqual(self.client_for().get(URL).status_code, 403)

    def test_only_own_company_is_returned(self):
        other = Client(schema_name='tenant_pdother', company_code='PDOTHER', company_name='PD Other')
        other.auto_create_schema = False
        with schema_context('public'):
            other.save()
            CompanySubscription.objects.create(client=other, plan=self.pro, plan_name='Other Co Secret Plan',
                                               starts_on=TODAY, price_per_employee=Decimal('1'))
        self.assign_basic(waive_reason='pilot')
        d = self.web.get(URL, {'client_id': str(other.pk), 'company_code': 'PDOTHER'}).data['data']
        self.assertEqual(d['current']['plan_name'], 'PD Basic')
        self.assertNotIn('Other Co Secret Plan', str(d))
